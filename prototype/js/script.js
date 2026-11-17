"use strict";
// 담당: 노태림 (필기·지우개·툴바·조절 슬라이더 표시)
// 11/17 정원준: 조건·과제·로그 연결을 위해 정리
//  - 펜 상태(슬롯, 굵기)를 Pen 한곳에서 바꾸고, 바뀔 때마다 로그를 남긴다
//  - C2·C3 제스처 판단은 recognition.js 로 옮김 (이 파일은 결과만 받아서 그림)
//  - 굵기 단위를 pt로 (size.js). 화면에는 pt × 96/72 px로 그린다
//  - 형광펜은 반투명. 획을 통째로 그려서 겹친 부분이 진해지지 않게 함

const canvas = document.querySelector("#canvas");
const ctx = canvas.getContext("2d");

const tools = [...document.querySelectorAll(".pen-tool[data-slot]")];
const undoButton = document.querySelector("#undo");
const redoButton = document.querySelector("#redo");
const ERASER_WIDTH = 24;
const eraserCursor = document.querySelector("#eraser-cursor");

// 슬롯 = 손가락 수. 순서: 검정, 빨강, 노랑 형광펜 (11/17 결정)
const PENS = {
  1: { name: "검정 펜", color: "#252b37", alpha: 1 },
  2: { name: "빨간 펜", color: "#e65060", alpha: 1 },
  3: { name: "노란 형광펜", color: "#f1bb3c", alpha: 0.45 },
};
const DEFAULT_SIZES = { 1: 1, 2: 1, 3: 4 };   // 블록 시작 때 굵기 (pt)

// ---------- 펜 상태 ----------
// rememberSize: 슬롯마다 굵기를 따로 기억할지 (log-schema "합의할 것". 기본은 기억)
const Pen = {
  slot: 1,
  sizes: { ...DEFAULT_SIZES },
  shared: DEFAULT_SIZES[1],
  rememberSize: true,

  get size() {
    return this.rememberSize ? this.sizes[this.slot] : this.shared;
  },
  get color() {
    return PENS[this.slot].color;
  },
  get alpha() {
    return PENS[this.slot].alpha;
  },

  // source: toolbar / slider / gesture. 값이 바뀔 때만 로그를 남긴다.
  setSlot(slot, source) {
    if (slot === this.slot) return false;
    this.slot = slot;
    updateToolUI();
    Logger.log("slot_change", { source, slot: this.slot, size: this.size });
    return true;
  },
  setSize(size, source) {
    if (size === this.size) return false;
    if (this.rememberSize) this.sizes[this.slot] = size;
    else this.shared = size;
    updateToolUI();
    Logger.log("size_change", { source, slot: this.slot, size: this.size });
    return true;
  },
  // 블록 시작 때. 로그 없이 처음 상태로 되돌린다.
  reset() {
    this.slot = 1;
    this.sizes = { ...DEFAULT_SIZES };
    this.shared = DEFAULT_SIZES[1];
    updateToolUI();
  },
};

// ---------- 앱 설정 (task.js 가 바꿈) ----------
const Ink = {
  locked: false,        // true면 필기 안 됨 (안내 화면 등)
  allowEraser: true,    // 실험 모드에서는 끔
  allowMouse: false,    // 펜 없이 테스트할 때만 (?mouse=1)
  onStroke: null,       // 획이 하나 끝날 때 부를 함수 (선택)
  clear() {
    strokes = [];
    redoStack = [];
    render();
  },
};
Ink.allowMouse = new URLSearchParams(location.search).get("mouse") === "1";

let activePointer = null;
let activeMode = null;   // "ink" | "erase" | "gesture"
let last = null;
let strokes = [];
let redoStack = [];
let currentStroke = null;
let renderQueued = false;

function isPen(event) {
  return event.pointerType === "pen" || (Ink.allowMouse && event.pointerType === "mouse");
}
function point(event) {
  const rect = canvas.getBoundingClientRect();
  return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}
function erasing(event) {
  return Ink.allowEraser && (event.buttons & (32 | 2)) !== 0; //펜측면 버튼 누를때 buttons:32 button:5
}
function distanceToSegment(p, a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;

  const lengthSquared = dx * dx + dy * dy;

  if (lengthSquared === 0) {
    return Math.hypot(p.x - a.x, p.y - a.y);
  }

  const t = Math.max(
    0,
    Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / lengthSquared),
  );

  const x = a.x + t * dx;
  const y = a.y + t * dy;

  return Math.hypot(p.x - x, p.y - y);
}

function hitStroke(p, stroke) {
  const points = stroke.points;
  const radius = (ERASER_WIDTH + stroke.width) / 2;

  for (let i = 1; i < points.length; i++) {
    if (distanceToSegment(p, points[i - 1], points[i]) <= radius) {
      return true;
    }
  }

  return (
    points.length === 1 &&
    Math.hypot(p.x - points[0].x, p.y - points[0].y) <= radius
  );
}
function eraseStroke(p) {
  const before = strokes.length;

  strokes = strokes.filter((stroke) => !hitStroke(p, stroke));

  if (strokes.length !== before) {
    render();
  }
}

// 획 하나를 경로 하나로 그린다. 형광펜이 겹쳐서 얼룩지지 않는다.
function drawStroke(stroke) {
  const points = stroke.points;
  ctx.save();
  ctx.globalAlpha = stroke.alpha;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.lineWidth = stroke.width;
  ctx.strokeStyle = stroke.color;
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  if (points.length === 1) ctx.lineTo(points[0].x + 0.01, points[0].y);
  for (let i = 1; i < points.length; i++) ctx.lineTo(points[i].x, points[i].y);
  ctx.stroke();
  ctx.restore();
}

function updateEraserCursor(event, erasing) {
  canvas.classList.toggle("erasing", erasing);

  if (erasing) {
    eraserCursor.style.display = "block";
    eraserCursor.style.left = `${event.clientX}px`;
    eraserCursor.style.top = `${event.clientY}px`;
  } else {
    eraserCursor.style.display = "none";
  }
}

function render() {
  const rect = canvas.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  for (const stroke of strokes) drawStroke(stroke);
  updateHistoryButtons();
}
function requestRender() {
  if (renderQueued) return;
  renderQueued = true;
  requestAnimationFrame(() => {
    renderQueued = false;
    render();
  });
}
function updateHistoryButtons() {
  undoButton.disabled = strokes.length === 0;
  redoButton.disabled = redoStack.length === 0;
}
function resize() {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(rect.width * dpr));
  const height = Math.max(1, Math.round(rect.height * dpr));
  if (canvas.width === width && canvas.height === height) return;
  canvas.width = width;
  canvas.height = height;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  render();
}
function startStroke(p) {
  currentStroke = {
    slot: Pen.slot,
    color: Pen.color,
    alpha: Pen.alpha,
    size: Pen.size,
    width: Size.toPx(Pen.size),
    points: [p],
  };
  strokes.push(currentStroke);
  redoStack = [];
  requestRender();
  Logger.log("ink_start", { source: "pen", slot: Pen.slot, size: Pen.size });
}
function endStroke() {
  if (!currentStroke) return;
  Logger.log("ink_end", { source: "pen", slot: currentStroke.slot, size: currentStroke.size });
  const finished = currentStroke;
  currentStroke = null;
  if (typeof Ink.onStroke === "function") Ink.onStroke(finished);
}

function down(event) {
  // 손가락은 recognition.js 가 따로 본다. 여기서는 그리지 않는다.
  if (!isPen(event) || activePointer !== null || Ink.locked) return;
  event.preventDefault();

  // C2·C3: 정지한 손가락이 있으면 제스처로 처리 (잉크 없음)
  if (Recognition.penDown(event)) {
    activeMode = "gesture";
    activePointer = event.pointerId;
    canvas.setPointerCapture(event.pointerId);
    return;
  }

  activePointer = event.pointerId;
  canvas.setPointerCapture(event.pointerId);
  last = point(event);
  if (erasing(event)) {
    activeMode = "erase";
    eraseStroke(last);
  } else {
    activeMode = "ink";
    startStroke(last);
  }
}
function move(event) {
  if (isPen(event)) updateEraserCursor(event, erasing(event));
  if (event.pointerId !== activePointer) return;
  event.preventDefault();

  if (activeMode === "gesture") {
    Recognition.penMove(event);
    return;
  }

  const samples =
    typeof event.getCoalescedEvents === "function"
      ? event.getCoalescedEvents()
      : [event];
  for (const sample of samples.length ? samples : [event]) {
    const next = point(sample);
    if (activeMode === "erase") {
      eraseStroke(next);
    } else if (currentStroke) {
      currentStroke.points.push(next);
    }
    last = next;
  }
  if (activeMode === "ink") requestRender();
}
function finish(event) {
  if (activeMode === "gesture") Recognition.penUp(event);
  if (activeMode === "ink") endStroke();
  activePointer = null;
  activeMode = null;
  last = null;
}
function up(event) {
  if (event.pointerId !== activePointer) return;
  finish(event);
  updateEraserCursor(event, false);
  if (canvas.hasPointerCapture(event.pointerId))
    canvas.releasePointerCapture(event.pointerId);
}
canvas.addEventListener("pointerdown", down);
canvas.addEventListener("pointermove", move);
canvas.addEventListener("pointerup", up);
canvas.addEventListener("pointercancel", up);
canvas.addEventListener("lostpointercapture", (event) => {
  if (activePointer === event.pointerId) {
    finish(event);
    updateEraserCursor(event, false);
  }
});
canvas.addEventListener("contextmenu", (event) => event.preventDefault());

// 툴바 펜 버튼: C1·C2에서 펜을 고르는 곳. C3에서는 현재 펜 표시만 (conditions.js)
tools.forEach((button) =>
  button.addEventListener("click", () => {
    if (!Conditions.toolbarPens) return;
    const slot = Number(button.dataset.slot);
    Pen.setSlot(slot, "toolbar");
    Logger.log("toolbar_tap", { source: "toolbar", slot: Pen.slot, size: Pen.size });
  }),
);
undoButton.addEventListener("click", () => {
  if (!strokes.length || activePointer !== null) return;
  redoStack.push(strokes.pop());
  render();
});
redoButton.addEventListener("click", () => {
  if (!redoStack.length || activePointer !== null) return;
  strokes.push(redoStack.pop());
  render();
});
document.querySelector("#clear").addEventListener("click", () => {
  if (activePointer !== null || !strokes.length) return;
  if (!window.confirm("모든 필기를 지울까요?")) return;
  strokes = [];
  redoStack = [];
  render();
});

const toolbar = document.querySelector(".floating-toolbar");
const dragHandle = document.querySelector(".drag-handle");
const app = document.querySelector(".app");
const tuneSlider = document.querySelector("#tune-slider");
const tuneThumb = tuneSlider.querySelector(".tune-thumb");
const tuneValue = tuneSlider.querySelector(".tune-value");

let offsetX = 0;
let offsetY = 0;
let dragging = false;

const thicknessDot = document.querySelector(".thickness-dot");
const thicknessValue = document.querySelector("#thickness-value");

// 툴바: 지금 펜과 굵기 표시
function updateToolUI() {
  tools.forEach((tool) => {
    tool.classList.toggle("active", Number(tool.dataset.slot) === Pen.slot);
  });
  const px = Math.max(2, Math.min(20, Size.toPx(Pen.size)));
  thicknessDot.style.width = `${px}px`;
  thicknessDot.style.height = `${px}px`;
  thicknessDot.style.backgroundColor = Pen.color;
  thicknessDot.style.opacity = Pen.alpha;
  thicknessValue.textContent = Size.label(Pen.size);
  if (typeof Conditions !== "undefined") Conditions.syncSlider();
}

// C2·C3 굵기 조절 중 펜 옆에 뜨는 눈금 (recognition.js 가 부름)
// 슬라이더의 현재 값 위치가 펜 끝에 오도록 놓아서, 펜을 움직이는 만큼 손잡이가 따라간다.
function showTuneSlider(x, y, size) {
  const left = x - Size.toRatio(size) * Size.TRACK_PX;
  tuneSlider.style.width = `${Size.TRACK_PX}px`;
  tuneSlider.style.left = `${left}px`;
  tuneSlider.style.top = `${y - 72}px`;
  tuneSlider.style.display = "block";
  updateTuneSlider(size);
}

function updateTuneSlider(size) {
  const thumbX = Size.toRatio(size) * Size.TRACK_PX;
  tuneThumb.style.left = `${thumbX}px`;
  tuneThumb.style.width = tuneThumb.style.height = `${Math.max(8, Size.toPx(size) + 4)}px`;
  tuneThumb.style.background = Pen.color;
  tuneThumb.style.opacity = Math.max(Pen.alpha, 0.7);
  tuneValue.style.left = `${thumbX}px`;
  tuneValue.textContent = Size.label(size);
}

function hideTuneSlider() {
  tuneSlider.style.display = "none";
}

// 조절 눈금에 프리셋 표시
for (const preset of Size.PRESETS) {
  const tick = document.createElement("div");
  tick.className = "tune-tick";
  tick.style.left = `${Size.toRatio(preset) * Size.TRACK_PX}px`;
  tuneSlider.appendChild(tick);
}

dragHandle.addEventListener("pointerdown", (e) => {
  if (e.button !== 0) return;
  dragging = true;
  const rect = toolbar.getBoundingClientRect();
  const appRect = app.getBoundingClientRect();
  offsetX = e.clientX - rect.left;
  offsetY = e.clientY - rect.top + appRect.top;

  toolbar.style.left = `${rect.left - appRect.left}px`;
  toolbar.style.top = `${rect.top - appRect.top}px`;
  toolbar.style.transform = "none";
  dragHandle.setPointerCapture(e.pointerId);
});

dragHandle.addEventListener("pointermove", (e) => {
  if (!dragging) return;

  const appRect = app.getBoundingClientRect();
  const maxX = Math.max(0, appRect.width - toolbar.offsetWidth);
  const maxY = Math.max(0, appRect.height - toolbar.offsetHeight);

  const x = Math.max(0, Math.min(e.clientX - offsetX, maxX));
  const y = Math.max(0, Math.min(e.clientY - offsetY, maxY));

  toolbar.style.left = `${x}px`;
  toolbar.style.top = `${y}px`;
});

function stopDragging() {
  dragging = false;
}

dragHandle.addEventListener("pointerup", stopDragging);
dragHandle.addEventListener("pointercancel", stopDragging);

// 실험 모드에서는 툴바를 처음 자리로 (조건마다 이동 거리가 같도록)
function resetToolbarPosition() {
  toolbar.style.left = "";
  toolbar.style.top = "";
  toolbar.style.transform = "";
}

new ResizeObserver(resize).observe(canvas);
resize();
updateToolUI();
