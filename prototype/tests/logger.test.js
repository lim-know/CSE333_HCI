// logger.js 를 브라우저 없이 확인한다. 실행: node --test prototype/tests/logger.test.js
// 가짜 포인터 이벤트로 C3 블록 하나를 흉내 내고, 기록된 CSV를 검사한다.
// CT_LOG_OUT 환경 변수에 폴더를 주면 분석 코드(validate_log.py)로 점검할 수 있는 데이터 폴더를 만든다.
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const LOGGER = path.join(__dirname, "..", "js", "logger.js");

function loadLogger() {
  let clock = 1000;
  const listeners = {};
  const storage = {};
  Object.defineProperties(storage, {
    setItem: { value: (key, value) => { storage[key] = String(value); } },
    getItem: { value: (key) => (key in storage ? storage[key] : null) },
  });
  const context = {
    window: { addEventListener: (type, fn) => { (listeners[type] ||= []).push(fn); } },
    performance: { now: () => clock },
    requestAnimationFrame: (callback) => setTimeout(() => { clock += 8; callback(); }, 0),
    location: { search: "" },
    localStorage: storage,
    console,
    setTimeout,
    URLSearchParams,
    Date,
    Math,
    Number,
    String,
    Object,
    Map,
    Set,
    Promise,
    Error,
  };
  vm.createContext(context);
  const logger = vm.runInContext(`${fs.readFileSync(LOGGER, "utf8")}\nLogger;`, context);
  logger.configure({ download: false, build: "test" });

  const canvas = { closest: (selector) => (selector === ".desk" ? canvas : null) };
  const toolbar = { closest: () => null };
  const fire = (type, fields) => {
    const event = {
      type, width: 1, height: 1, buttons: type === "pointerup" ? 0 : 1, target: canvas,
      timeStamp: clock, ...fields,
    };
    for (const fn of listeners[type] || []) fn(event);
  };
  return {
    logger,
    storage,
    canvas,
    toolbar,
    fire,
    now: () => clock,
    wait: (ms) => { clock += ms; },
  };
}

const META = {
  session_id: "P90-1", participant: "P90", block: 1, condition: "C3",
  phase: "main", exp: "exp2", script_id: "logtest",
};

function parseCsv(csv) {
  const [header, ...lines] = csv.trim().split("\n");
  const columns = header.split(",");
  return lines.map((line) => Object.fromEntries(line.split(",").map((value, i) => [columns[i], value])));
}

// C3 블록: s01 전환 + 굵기 단계, s02 따라쓰기 단계
async function runBlock(env) {
  const { logger, fire, wait, toolbar } = env;
  const pen = (type, x, y, extra = {}) => fire(type, { pointerId: 1, pointerType: "pen", clientX: x, clientY: y, ...extra });
  const ink = (slot, size) => {
    pen("pointerdown", 400, 300);
    logger.log("ink_start", { source: "pen", slot, size });
    for (let i = 1; i <= 3; i += 1) { wait(8); pen("pointermove", 400 + 10 * i, 300); }
    pen("pointerup", 430, 300);
    logger.log("ink_end", { source: "pen", slot, size });
  };
  const done = () => {
    wait(300);
    pen("pointerdown", 1200, 40, { target: toolbar });
    pen("pointerup", 1200, 40, { target: toolbar });
  };

  logger.startBlock(META);
  await logger.cueShown("s01", { slot: 1, size: 3 });
  wait(400);
  fire("pointerdown", { pointerId: 11, pointerType: "touch", clientX: 900, clientY: 500, width: 30, height: 30 });
  fire("pointerdown", { pointerId: 12, pointerType: "touch", clientX: 940, clientY: 500, width: 30, height: 30 });
  wait(200);
  pen("pointerdown", 400, 300);
  logger.log("activation", { source: "gesture", slot: 1, size: 3, rec_state: "TUNING" });
  logger.log("slot_change", { source: "gesture", slot: 2, size: 3 });
  wait(100);
  const sample = (x, t) => ({ pointerId: 1, pointerType: "pen", clientX: x, clientY: 300, width: 1, height: 1, buttons: 1, timeStamp: t });
  pen("pointermove", 450, 300, { getCoalescedEvents: () => [sample(425, env.now() - 4), sample(450, env.now())] });
  logger.log("size_change", { source: "gesture", slot: 2, size: 5 });
  pen("pointerup", 450, 300);
  logger.log("gesture_commit", { source: "gesture", slot: 2, size: 5 });
  fire("pointerup", { pointerId: 11, pointerType: "touch", clientX: 900, clientY: 500 });
  fire("pointerup", { pointerId: 12, pointerType: "touch", clientX: 940, clientY: 500 });
  wait(250);
  ink(2, 5);
  done();
  logger.stepEnd("completed", { slot: 2, size: 5 });

  await logger.cueShown("s02", { slot: 2, size: 5 });
  for (let i = 0; i < 3; i += 1) { wait(150); ink(2, 5); }
  done();
  logger.stepEnd("completed", { slot: 2, size: 5 });
  return logger.endBlock();
}

test("블록 하나를 형식 v1.1 컬럼 순서대로 기록한다", async () => {
  const env = loadLogger();
  const { csv, name } = await runBlock(env);
  assert.equal(name, "events_P90-1_b01.csv");
  assert.equal(csv.split("\n")[0], env.logger.COLUMNS.join(","));
  const rows = parseCsv(csv);
  assert.equal(rows[0].event, "block_start");
  assert.equal(rows.at(-1).event, "block_end");
  assert.deepEqual(rows.map((r) => Number(r.seq)), rows.map((_, i) => i + 1));
  assert.ok(rows.every((r) => r.schema_version === "1.1" && r.session_id === "P90-1"));
  assert.match(rows[0].detail, /build=test;still_px=12;still_ms=120;touch_to_pen_ms=none;epoch_ms=\d+/);
});

test("펜이 닿은 채 움직이면 중간 점(coalesced)까지 남긴다", async () => {
  const env = loadLogger();
  const rows = parseCsv((await runBlock(env)).csv);
  const xs = rows.filter((r) => r.event === "pointermove" && r.pointer_type === "pen").map((r) => r.x);
  assert.ok(xs.includes("425") && xs.includes("450"), xs.join(" "));
});

test("펜 다운에 source 와 정지 손가락 수를 붙인다", async () => {
  const env = loadLogger();
  const rows = parseCsv((await runBlock(env)).csv);
  const penDowns = rows.filter((r) => r.event === "pointerdown" && r.pointer_type === "pen");
  const gestureDown = penDowns[0];
  assert.equal(gestureDown.source, "canvas");
  assert.equal(gestureDown.n_touch, "2");
  assert.equal(gestureDown.n_still, "2");
  assert.ok(penDowns.some((r) => r.source === "ui"), "완료 버튼 탭은 ui");
  const activation = rows.find((r) => r.event === "activation");
  assert.equal(activation.n_touch, "2", "activation 에 손가락 수를 자동으로 채운다");
});

test("움직인 손가락은 정지로 세지 않는다", async () => {
  const env = loadLogger();
  const { logger, fire, wait } = env;
  logger.startBlock(META);
  fire("pointerdown", { pointerId: 11, pointerType: "touch", clientX: 0, clientY: 0 });
  fire("pointermove", { pointerId: 11, pointerType: "touch", clientX: 30, clientY: 0 });
  wait(300);
  fire("pointerdown", { pointerId: 1, pointerType: "pen", clientX: 400, clientY: 300 });
  const penDown = parseCsv(logger.endBlock().csv).find((r) => r.event === "pointerdown" && r.pointer_type === "pen");
  assert.equal(penDown.n_touch, "1");
  assert.equal(penDown.n_still, "0");
});

test("cue_shown 은 두 프레임 뒤에, step 사이 이벤트는 step_id 없이 기록한다", async () => {
  const env = loadLogger();
  const rows = parseCsv((await runBlock(env)).csv);
  const cue = rows.find((r) => r.event === "cue_shown");
  assert.equal(cue.step_id, "s01");
  assert.ok(Number(cue.t_event) >= 1016);
  const end = rows.find((r) => r.event === "step_end");
  assert.equal(end.detail, "outcome=completed");
  assert.equal(rows.find((r) => r.event === "block_end").step_id, "");
});

test("블록이 없으면 기록하지 않고, 끝난 블록은 브라우저에 백업한다", async () => {
  const env = loadLogger();
  env.fire("pointerdown", { pointerId: 1, pointerType: "pen", clientX: 1, clientY: 1 });
  assert.equal(env.logger.active, false);
  await runBlock(env);
  assert.deepEqual(env.logger.savedBlocks(), ["events_P90-1_b01.csv"]);
});

test("쉼표나 따옴표가 든 값은 CSV 규칙대로 감싼다", () => {
  const env = loadLogger();
  env.logger.startBlock(META);
  env.logger.log("rec_state", { rec_state: "IDLE", detail: 'note=a,b"c' });
  const line = env.logger.endBlock().csv.split("\n")[2];
  assert.ok(line.endsWith('"note=a,b""c"'), line);
});

test("분석 코드로 점검할 데이터 폴더를 만든다 (CT_LOG_OUT 이 있을 때)", { skip: !process.env.CT_LOG_OUT }, async () => {
  const out = process.env.CT_LOG_OUT;
  const env = loadLogger();
  const { name, csv } = await runBlock(env);
  const write = (relative, text) => {
    fs.mkdirSync(path.dirname(path.join(out, relative)), { recursive: true });
    fs.writeFileSync(path.join(out, relative), text);
  };
  write(`events/${name}`, csv);
  write("scripts/script_logtest.csv", [
    "script_id,step_id,exp,step_type,task_type,language,cue_text,target_slot,target_size,on_preset,target_x,target_y,text,time_limit_ms",
    "logtest,s01,exp2,switch_size,circle,,빨간 펜 5pt,2,5,1,400,300,,20000",
    "logtest,s02,exp2,copy,copy,ko,아래 문장을 따라 쓰세요,,,,,,실험 설계,60000",
    "",
  ].join("\n"));
  write("sessions.csv", [
    "session_id,participant,condition_order,script_variant,date,device,browser,windows,screen_w,screen_h,dpr,experimenter,notes",
    "P90-1,P90,C3-C1-C2,A-B-C,2000-01-01,TEST,node,TEST,2560,1600,1.5,TEST,logger.test.js",
    "",
  ].join("\n"));
  write("participants.csv", [
    "participant,handedness,native_language,note_language,tablet_note_months",
    "P90,right,ko,ko,12",
    "",
  ].join("\n"));
  write("questionnaire.csv", "participant,condition,item,value\nP90,C3,tlx_mental,50\n");
});
