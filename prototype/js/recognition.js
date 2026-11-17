// 담당: 노태림 (11/17 정원준 구현, 태림 검토)
// 역할: C2·C3 제스처 인식
//  - 필기 영역에 닿은 손가락을 따라가며 "정지" 여부를 판정한다
//      정지 = 최근 STILL_MS 동안 STILL_PX 이상 움직이지 않음 (값은 파일럿에서 조정)
//  - 펜 다운 순간 정지한 손가락이 1~3개면 제스처, 아니면 보통 필기 (4개 이상은 무시)
//      C3 (count): 손가락 수 = 펜 슬롯, 펜을 가로로 끌면 굵기
//      C2 (size) : 손가락 수와 상관없이 굵기만. 펜은 툴바에서 고름
//      C1 (off)  : 제스처 없음
//  - 슬롯은 펜 다운 때 정해진다. 끄는 도중 손가락이 바뀌어도 무시
//  - hold 타이머 없음: 펜 다운이 트리거 (Li et al., 2005)
//  - 상태: IDLE → ARMED (정지한 손가락 있음) → TUNING (펜 드래그) → 펜 업 = 확정
// 손바닥 거르기: 접촉 크기(width/height)가 palmPx 보다 크면 손가락으로 세지 않는다.
//   기기마다 값이 달라서 기본은 꺼 둠(0). 파일럿 로그의 width/height 를 보고 정한다.

const Recognition = (() => {
  "use strict";

  const config = {
    stillPx: 12,
    stillMs: 120,
    maxFingers: 3,
    palmPx: 0,              // 0 = 끔
    areaSelector: ".desk",  // 이 안에 닿은 손가락만 센다
  };

  let mode = "off";            // off | size | count
  const touches = new Map();   // pointerId -> { ax, ay, at, palm }
  let state = "IDLE";
  let tuning = null;           // { pointerId, startX, startSize }
  let timer = null;

  const isPalm = (e) => config.palmPx > 0 && Math.max(e.width || 0, e.height || 0) > config.palmPx;

  // ---------- 손가락 추적 ----------

  function inArea(event) {
    const target = event.target;
    return Boolean(target && typeof target.closest === "function" && target.closest(config.areaSelector));
  }

  function onTouch(event) {
    if (event.pointerType !== "touch") return;
    const t = event.timeStamp;
    if (event.type === "pointerdown") {
      if (!inArea(event)) return;
      touches.set(event.pointerId, { ax: event.clientX, ay: event.clientY, at: t, palm: isPalm(event) });
    } else if (event.type === "pointermove") {
      const touch = touches.get(event.pointerId);
      if (!touch) return;
      if (isPalm(event)) touch.palm = true;
      // 기준점에서 STILL_PX 넘게 움직이면 기준점을 옮기고 시간을 다시 잰다
      if (Math.hypot(event.clientX - touch.ax, event.clientY - touch.ay) > config.stillPx) {
        touch.ax = event.clientX;
        touch.ay = event.clientY;
        touch.at = t;
      }
    } else {
      touches.delete(event.pointerId);
    }
    refresh();
  }

  function stillCount(now) {
    let n = 0;
    for (const touch of touches.values()) {
      if (!touch.palm && now - touch.at >= config.stillMs) n += 1;
    }
    return n;
  }

  // 로거가 펜 다운마다 부른다 (n_touch, n_still)
  function counts(now) {
    return { n_touch: touches.size, n_still: stillCount(now) };
  }

  // ---------- 상태 ----------

  function setState(next) {
    if (next === state) return;
    state = next;
    document.body.dataset.recState = state;
    Logger.log("rec_state", { source: "gesture", rec_state: state, slot: Pen.slot, size: Pen.size });
  }

  // 손가락 상태가 바뀌거나, 손가락이 "정지"가 될 시각이 되면 다시 판정한다
  function refresh() {
    clearTimeout(timer);
    if (tuning) return setState("TUNING");
    if (mode === "off") return setState("IDLE");
    const now = performance.now();
    setState(stillCount(now) > 0 ? "ARMED" : "IDLE");
    let wait = Infinity;
    for (const touch of touches.values()) {
      const remaining = touch.at + config.stillMs - now;
      if (!touch.palm && remaining > 0) wait = Math.min(wait, remaining);
    }
    if (wait < Infinity) timer = setTimeout(refresh, wait + 1);
  }

  // ---------- 펜 (script.js 가 부름) ----------

  // 제스처로 처리했으면 true. 이 펜 다운에는 잉크를 남기지 않는다.
  function penDown(event) {
    if (mode === "off") return false;
    const nStill = stillCount(event.timeStamp);
    if (nStill < 1 || nStill > config.maxFingers) return false;

    const slot = mode === "count" ? nStill : Pen.slot;
    const sizeAfter = Pen.rememberSize ? Pen.sizes[slot] : Pen.size;
    Logger.log("activation", {
      source: "gesture", slot, size: sizeAfter, rec_state: "ARMED",
      n_touch: touches.size, n_still: nStill,
    });
    if (mode === "count") Pen.setSlot(slot, "gesture");

    tuning = { pointerId: event.pointerId, startX: event.clientX, startSize: Pen.size };
    refresh();
    showTuneSlider(event.clientX, event.clientY, Pen.size);
    return true;
  }

  function penMove(event) {
    if (!tuning || event.pointerId !== tuning.pointerId) return;
    const samples = typeof event.getCoalescedEvents === "function" ? event.getCoalescedEvents() : [];
    const last = samples.length ? samples[samples.length - 1] : event;
    const size = Size.fromDrag(tuning.startSize, last.clientX - tuning.startX);
    if (Pen.setSize(size, "gesture")) updateTuneSlider(size);
  }

  function penUp(event) {
    if (!tuning || event.pointerId !== tuning.pointerId) return;
    Logger.log("gesture_commit", { source: "gesture", slot: Pen.slot, size: Pen.size });
    tuning = null;
    hideTuneSlider();
    refresh();
  }

  function setMode(next) {
    mode = next;
    tuning = null;
    hideTuneSlider();
    refresh();
  }

  for (const type of ["pointerdown", "pointermove", "pointerup", "pointercancel"]) {
    window.addEventListener(type, onTouch, { capture: true, passive: true });
  }

  // URL로 임계값 바꾸기 (파일럿용): ?still_px=15&still_ms=150&palm_px=40
  const params = new URLSearchParams(location.search);
  for (const [key, name] of [["still_px", "stillPx"], ["still_ms", "stillMs"], ["palm_px", "palmPx"]]) {
    if (params.has(key) && Number.isFinite(Number(params.get(key)))) config[name] = Number(params.get(key));
  }
  Logger.configure({
    stillPx: config.stillPx,
    stillMs: config.stillMs,
    touchCounter: counts,
    blockDetail: { palm_px: config.palmPx, snap_px: Size.SNAP_PX, track_px: Size.TRACK_PX },
  });

  return {
    config,
    setMode,
    penDown,
    penMove,
    penUp,
    counts,
    get mode() { return mode; },
    get state() { return state; },
  };
})();
