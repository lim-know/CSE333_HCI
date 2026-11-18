// size.js, recognition.js, task.js 의 계산 부분을 브라우저 없이 확인한다.
// 실행: node --test prototype/tests/*.test.js
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const JS = path.join(__dirname, "..", "js");
const read = (name) => fs.readFileSync(path.join(JS, name), "utf8");

function loadSize() {
  const context = { Math, Number };
  vm.createContext(context);
  return vm.runInContext(`${read("size.js")}\nSize;`, context);
}

// recognition.js 를 가짜 window/Logger/Pen 위에서 돌린다
function loadRecognition() {
  let clock = 0;
  const listeners = {};
  const logs = [];
  const timers = [];
  const area = { closest: (selector) => (selector === ".desk" ? area : null) };
  const context = {
    window: { addEventListener: (type, fn) => { (listeners[type] ||= []).push(fn); } },
    document: { body: { dataset: {} } },
    location: { search: "" },
    performance: { now: () => clock },
    setTimeout: (fn, ms) => { timers.push({ at: clock + ms, fn }); return timers.length; },
    clearTimeout: () => {},
    URLSearchParams,
    Logger: { log: (event, fields) => logs.push({ event, ...fields }), configure: () => {} },
    showTuneSlider: () => {},
    updateTuneSlider: () => {},
    hideTuneSlider: () => {},
    Math, Number, Object, Map, Boolean, Infinity,
  };
  vm.createContext(context);
  context.Size = vm.runInContext(`${read("size.js")}\nSize;`, context);
  vm.runInContext(`
    var Pen = {
      slot: 1, sizes: { 1: 1, 2: 1, 3: 4 }, rememberSize: true,
      get size() { return this.sizes[this.slot]; },
      setSlot(slot, source) { if (slot === this.slot) return false; this.slot = slot; Logger.log("slot_change", { source, slot }); return true; },
      setSize(size, source) { if (size === this.size) return false; this.sizes[this.slot] = size; Logger.log("size_change", { source, size }); return true; },
    };`, context);
  const recognition = vm.runInContext(`${read("recognition.js")}\nRecognition;`, context);

  const touch = (type, id, x, y) => {
    for (const fn of listeners[type] || []) {
      fn({ type, pointerType: "touch", pointerId: id, clientX: x, clientY: y, width: 10, height: 10, timeStamp: clock, target: area });
    }
  };
  const pen = (id, x) => ({ pointerId: id, clientX: x, clientY: 300, timeStamp: clock });
  const advance = (ms) => {
    clock += ms;
    for (const t of timers.splice(0)) if (t.at <= clock) t.fn(); else timers.push(t);
  };
  return { recognition, logs, touch, pen, advance, Pen: context.Pen };
}

test("굵기: 프리셋은 같은 간격, 근처에서 스냅", () => {
  const Size = loadSize();
  assert.deepEqual([...Size.PRESETS].map((p) => Size.toRatio(p)), [0, 0.25, 0.5, 0.75, 1]);
  assert.equal(Size.fromRatio(0.5 + 5 / Size.TRACK_PX), 2);      // 5px 옆 → 2pt 로 붙음
  assert.notEqual(Size.fromRatio(0.5 + 30 / Size.TRACK_PX), 2);  // 30px 옆 → 사이값
  assert.equal(Size.fromDrag(1, 80), 2);                          // 80px = 한 칸
  assert.equal(Size.fromDrag(1, -1000), 0.5);                     // 끝에서 멈춤
  assert.equal(Size.fromDrag(1, 1000), 8);
});

test("C3: 정지한 손가락 수가 슬롯, 드래그가 굵기", () => {
  const { recognition, logs, touch, pen, advance, Pen } = loadRecognition();
  recognition.setMode("count");
  touch("pointerdown", 11, 100, 400);
  touch("pointerdown", 12, 140, 400);
  advance(50);
  assert.equal(recognition.penDown(pen(1, 600)), false, "아직 정지 시간 전이면 필기");
  advance(100);
  assert.equal(recognition.state, "ARMED");
  assert.equal(recognition.penDown(pen(1, 600)), true);
  assert.equal(Pen.slot, 2);
  recognition.penMove(pen(1, 680));
  assert.equal(Pen.size, 2);
  recognition.penUp(pen(1, 680));
  const events = logs.map((l) => l.event);
  assert.ok(events.indexOf("activation") < events.indexOf("slot_change"));
  assert.ok(events.includes("gesture_commit"));
  assert.equal(logs.find((l) => l.event === "activation").n_still, 2);
});

test("움직이는 손가락은 정지로 세지 않는다", () => {
  const { recognition, touch, pen, advance } = loadRecognition();
  recognition.setMode("count");
  touch("pointerdown", 11, 100, 400);
  advance(100);
  touch("pointermove", 11, 130, 400);   // 30px 이동 → 시간 다시 잼
  advance(60);
  assert.equal(recognition.penDown(pen(1, 600)), false);
  advance(80);
  assert.equal(recognition.penDown(pen(1, 600)), true);
});

test("C2: 손가락 수와 상관없이 슬롯은 그대로, 굵기만", () => {
  const { recognition, touch, pen, advance, Pen } = loadRecognition();
  recognition.setMode("size");
  touch("pointerdown", 11, 100, 400);
  touch("pointerdown", 12, 140, 400);
  touch("pointerdown", 13, 180, 400);
  advance(200);
  assert.equal(recognition.penDown(pen(1, 600)), true);
  assert.equal(Pen.slot, 1);
  recognition.penMove(pen(1, 520));
  assert.equal(Pen.size, 0.5);
});

test("C1과 손가락 4개 이상은 제스처가 아니다", () => {
  const { recognition, touch, pen, advance } = loadRecognition();
  recognition.setMode("off");
  touch("pointerdown", 11, 100, 400);
  advance(200);
  assert.equal(recognition.penDown(pen(1, 600)), false);
  recognition.setMode("count");
  for (const id of [12, 13, 14]) touch("pointerdown", id, 100 + id, 400);
  advance(200);
  assert.equal(recognition.penDown(pen(1, 600)), false);
});

test("배정표: 6가지 순서를 2명씩, 조건·세트 짝이 고르게", () => {
  const source = read("task.js");
  const match = source.match(/const ORDERS = (\[[\s\S]*?\]);/);
  const ORDERS = vm.runInNewContext(match[1]);
  const pick = (n) => ORDERS[Math.floor(((n - 1) % 12) / 2)];
  const orders = new Set();
  const pairs = {};
  for (let n = 1; n <= 12; n++) {
    const o = pick(n);
    orders.add(o.conditions.join("-"));
    o.conditions.forEach((c, i) => { pairs[c + o.sets[i]] = (pairs[c + o.sets[i]] || 0) + 1; });
  }
  assert.equal(orders.size, 6);
  assert.deepEqual(Object.values(pairs).sort(), Array(9).fill(4));
});

function loadPassages() {
  const context = {};
  vm.createContext(context);
  const Passage = vm.runInContext(`${read("passage.js")}
Passage;`, context);
  const PASSAGES = vm.runInContext(`${read("scripts-data.js")}
PASSAGES;`, context);
  return { Passage, PASSAGES };
}
const SIZES = { 1: 1, 2: 1, 3: 4 };   // script.js DEFAULT_SIZES
const plain = (v) => JSON.parse(JSON.stringify(v));   // vm 안에서 만든 배열 비교용

test("제시문: 표시마다 바꾸기 + 본문으로 돌아가기 단계", () => {
  const { Passage } = loadPassages();
  const p = Passage.load("t", "가나 [빨강 2 밑줄|다라]를 쓴다. [형광 4 칠하기|마바] 끝", SIZES);
  assert.deepEqual(plain(p.steps.map((s) => [s.task_type, s.step_type, s.slot, s.size])), [
    ["underline", "switch_size", 2, 2],
    ["return", "switch_only", 1, 1],
    ["highlight", "switch_only", 3, 4],
    ["return", "switch_only", 1, 1],
  ]);
  // 표시 바로 뒤에 표시가 오면 돌아가기 단계 없음, 끝이 표시면 돌아가기 없음
  const q = Passage.load("t", "가 [빨강 2 밑줄|나] [검정 4 글씨|다]", SIZES);
  assert.deepEqual(plain(q.steps.map((s) => s.task_type)), ["underline", "word"]);
  assert.match(p.text, /^script_id,step_id,exp,step_type/);
});

test("제시문 표기 오류는 바로 알려 준다", () => {
  const { Passage } = loadPassages();
  assert.throws(() => Passage.load("t", "[파랑 2 밑줄|가]", SIZES), /펜 이름/);
  assert.throws(() => Passage.load("t", "[빨강 2 줄|가]", SIZES), /표시 이름/);
  assert.throws(() => Passage.load("t", "[검정 1 밑줄|가] 나", SIZES), /바꿀 게 없는/);
  assert.throws(() => Passage.load("t", "가 [빨강 2 밑줄 나", SIZES), /닫히지 않은/);
});

test("임시 제시문: 모두 읽히고, 세트 A/B/C 는 구조가 같다", () => {
  const { Passage, PASSAGES } = loadPassages();
  const shape = (key) => Passage.load(key, PASSAGES[key], SIZES).steps
    .map((s) => `${s.task_type}/${s.step_type}/${s.slot}/${s.size}`).join(" ");
  assert.ok(Passage.load("practice", PASSAGES.practice, SIZES).steps.length > 0);
  assert.equal(shape("A"), shape("B"));
  assert.equal(shape("A"), shape("C"));
  const types = Passage.load("A", PASSAGES.A, SIZES).steps.map((s) => s.step_type);
  for (const t of ["switch_only", "size_only", "switch_size"]) assert.ok(types.includes(t), t);
});
