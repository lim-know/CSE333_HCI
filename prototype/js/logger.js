// 담당: 정원준 (형식: docs/log-schema.md v1.1)
// 역할: 원시 이벤트를 블록 단위로 모아 CSV로 저장한다. 판정(정답, 오류)은 기록하지 않는다.
//
// 자동으로 기록하는 것
//  - 펜·터치의 pointerdown / pointermove / pointerup / pointercancel (호버 포함)
//  - 펜 pointerdown 의 source(canvas/ui), n_touch, n_still
//
// 다른 코드에서 부르는 것 (블록이 시작되지 않았으면 아무것도 기록하지 않는다)
//  Logger.startBlock({ session_id, participant, block, condition, phase, exp, script_id })
//  Logger.cueShown(step_id, { slot, size })     지시가 화면에 그려진 뒤의 시각을 기록
//  Logger.log(event, { source, slot, size, rec_state, ... })
//  Logger.stepEnd("completed" | "timeout" | "skipped", { slot, size })
//  Logger.endBlock()                             CSV 파일 다운로드
//
// 개발용: 주소 뒤에 ?log=dev&condition=C3 를 붙이면 블록이 자동으로 시작되고,
//          Ctrl+Shift+L 을 누르면 지금까지의 기록을 CSV로 내려받는다.

const Logger = (() => {
  "use strict";

  const SCHEMA_VERSION = "1.1";
  const COLUMNS = [
    "schema_version", "session_id", "participant", "block", "condition", "phase",
    "exp", "script_id", "step_id", "seq", "t_event", "t_logged", "event", "source",
    "pointer_id", "pointer_type", "x", "y", "width", "height", "buttons",
    "slot", "size", "rec_state", "n_touch", "n_still", "detail",
  ];
  const META_KEYS = ["session_id", "participant", "block", "condition", "phase", "exp", "script_id"];
  const APP_EVENTS = new Set([
    "block_start", "block_end", "cue_shown", "step_end", "toolbar_tap", "slider_start",
    "slider_end", "slot_change", "size_change", "activation", "gesture_commit",
    "ink_start", "ink_end", "rec_state",
  ]);
  const OUTCOMES = new Set(["completed", "timeout", "skipped"]);

  const config = {
    build: "dev",
    canvasSelector: ".desk",   // 이 요소 안에서 눌린 포인터는 source=canvas, 밖이면 ui
    stillPx: 12,                // 손가락 정지 판정 (recognition.js 와 같은 값을 쓴다)
    stillMs: 120,
    touchToPenMs: "none",       // 손→펜 간격 상한. 아직 쓰지 않으면 none
    download: true,             // endBlock 때 파일을 내려받을지
  };

  let current = null;   // { meta, rows, seq }
  let stepId = "";
  const touches = new Map();   // pointerId -> { x0, y0, t0, moved }

  // ---------- 기록 ----------

  function round(value, digits = 2) {
    if (typeof value !== "number" || !Number.isFinite(value)) return value;
    const scale = 10 ** digits;
    return Math.round(value * scale) / scale;
  }

  function push(event, fields, tEvent) {
    if (!current) return null;
    current.seq += 1;
    const row = {
      ...current.meta,
      schema_version: SCHEMA_VERSION,
      step_id: stepId,
      seq: current.seq,
      t_event: round(tEvent),
      t_logged: round(performance.now()),
      event,
      ...fields,
    };
    current.rows.push(row);
    return row;
  }

  function detailString(detail) {
    if (detail === undefined || detail === null || detail === "") return "";
    if (typeof detail === "string") return detail;
    return Object.entries(detail).map(([key, value]) => `${key}=${value}`).join(";");
  }

  function touchCounts(tPen) {
    let still = 0;
    for (const touch of touches.values()) {
      if (!touch.moved && tPen - touch.t0 >= config.stillMs) still += 1;
    }
    return { n_touch: touches.size, n_still: still };
  }

  // 앱 이벤트. fields.detail 은 문자열이나 객체({ outcome: "timeout" })로 줄 수 있다.
  function log(event, fields = {}) {
    if (!APP_EVENTS.has(event)) console.warn(`[Logger] 형식에 없는 이벤트: ${event}`);
    const { detail, ...rest } = fields;
    const row = { ...rest, detail: detailString(detail) };
    if (event === "activation" && row.n_touch === undefined) {
      Object.assign(row, touchCounts(performance.now()));
    }
    return push(event, row, performance.now());
  }

  // ---------- 블록 ----------

  function startBlock(meta) {
    const missing = META_KEYS.filter((key) => meta[key] === undefined || meta[key] === "");
    if (missing.length) throw new Error(`[Logger] startBlock 에 빠진 값: ${missing.join(", ")}`);
    if (current) {
      console.warn("[Logger] 끝나지 않은 블록이 있어 먼저 저장합니다");
      endBlock();
    }
    current = { meta: Object.fromEntries(META_KEYS.map((key) => [key, meta[key]])), rows: [], seq: 0 };
    stepId = "";
    log("block_start", {
      detail: {
        build: config.build,
        still_px: config.stillPx,
        still_ms: config.stillMs,
        touch_to_pen_ms: config.touchToPenMs,
        epoch_ms: Date.now(),
      },
    });
  }

  function endBlock() {
    if (!current) return null;
    stepId = "";
    log("block_end");
    const csv = toCsv(current.rows);
    const name = fileName(current.meta);
    current = null;
    backup(name, csv);
    if (config.download) download(name, csv);
    return { name, csv };
  }

  // 지시를 그린 다음 프레임이 화면에 나간 뒤의 시각을 cue_shown 으로 남긴다.
  function cueShown(id, fields = {}) {
    stepId = id;
    return new Promise((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(() => {
        resolve(push("cue_shown", { ...fields, detail: detailString(fields.detail) }, performance.now()));
      }));
    });
  }

  function stepEnd(outcome, fields = {}) {
    if (!OUTCOMES.has(outcome)) console.warn(`[Logger] outcome 값 오류: ${outcome}`);
    const row = log("step_end", { ...fields, detail: { outcome } });
    stepId = "";
    return row;
  }

  // ---------- 포인터 자동 기록 ----------

  function pointerSource(event) {
    const target = event.target;
    return target && typeof target.closest === "function" && target.closest(config.canvasSelector)
      ? "canvas"
      : "ui";
  }

  function pointerFields(sample) {
    return {
      pointer_id: sample.pointerId,
      pointer_type: sample.pointerType,
      x: round(sample.clientX, 1),
      y: round(sample.clientY, 1),
      width: round(sample.width, 1),
      height: round(sample.height, 1),
      buttons: sample.buttons,
    };
  }

  function trackTouch(type, event) {
    if (event.pointerType !== "touch") return;
    if (type === "pointerdown") {
      touches.set(event.pointerId, { x0: event.clientX, y0: event.clientY, t0: event.timeStamp, moved: false });
    } else if (type === "pointermove") {
      const touch = touches.get(event.pointerId);
      if (touch && Math.hypot(event.clientX - touch.x0, event.clientY - touch.y0) > config.stillPx) {
        touch.moved = true;
      }
    } else {
      touches.delete(event.pointerId);
    }
  }

  function onPointer(event) {
    const type = event.type;
    if (type === "pointermove") {
      // 펜이 닿아 있거나 터치일 때만 중간 점까지 남긴다. 펜 호버는 이벤트 한 번에 한 점.
      const detailed = event.buttons !== 0 || event.pointerType === "touch";
      const samples = detailed && typeof event.getCoalescedEvents === "function" ? event.getCoalescedEvents() : [];
      for (const sample of samples.length ? samples : [event]) {
        trackTouch(type, sample);
        push(type, pointerFields(sample), sample.timeStamp);
      }
      return;
    }
    const fields = { ...pointerFields(event), source: pointerSource(event) };
    if (type === "pointerdown" && event.pointerType === "pen") {
      Object.assign(fields, touchCounts(event.timeStamp));
    }
    trackTouch(type, event);
    push(type, fields, event.timeStamp);
  }

  for (const type of ["pointerdown", "pointermove", "pointerup", "pointercancel"]) {
    window.addEventListener(type, onPointer, { capture: true, passive: true });
  }

  // ---------- 저장 ----------

  function csvValue(value) {
    if (value === undefined || value === null) return "";
    const text = String(value);
    return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }

  function toCsv(rows) {
    const lines = rows.map((row) => COLUMNS.map((column) => csvValue(row[column])).join(","));
    return `${[COLUMNS.join(","), ...lines].join("\n")}\n`;
  }

  function fileName(meta) {
    return `events_${meta.session_id}_b${String(meta.block).padStart(2, "0")}.csv`;
  }

  function download(name, csv) {
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // 다운로드가 막혔을 때를 대비해 끝난 블록을 브라우저에도 남겨 둔다.
  function backup(name, csv) {
    try {
      localStorage.setItem(`count-tune-log:${name}`, csv);
    } catch (error) {
      console.warn("[Logger] 브라우저 백업 실패 (용량 초과일 수 있음)", error);
    }
  }

  function savedBlocks() {
    return Object.keys(localStorage)
      .filter((key) => key.startsWith("count-tune-log:"))
      .map((key) => key.slice("count-tune-log:".length))
      .sort();
  }

  function redownload(name) {
    const csv = localStorage.getItem(`count-tune-log:${name}`);
    if (csv === null) throw new Error(`[Logger] 백업 없음: ${name}`);
    download(name, csv);
  }

  // ---------- 개발용 ----------

  function startDevMode() {
    const params = new URLSearchParams(location.search);
    if (params.get("log") !== "dev") return;
    let blockNo = 0;
    const begin = () => {
      blockNo += 1;
      startBlock({
        session_id: "DEV-1", participant: "P00", block: blockNo,
        condition: params.get("condition") || "C3", phase: "practice", exp: "exp2", script_id: "dev",
      });
    };
    begin();
    window.addEventListener("keydown", (event) => {
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "l") {
        endBlock();
        begin();
      }
    });
    console.info("[Logger] 개발 모드: Ctrl+Shift+L 로 지금까지의 기록을 저장합니다");
  }

  startDevMode();

  return {
    configure(options) { Object.assign(config, options); },
    startBlock,
    endBlock,
    cueShown,
    stepEnd,
    log,
    savedBlocks,
    redownload,
    get active() { return current !== null; },
    get stepId() { return stepId; },
    COLUMNS,
    SCHEMA_VERSION,
  };
})();
