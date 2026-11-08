"use strict";
const canvas = document.querySelector("#canvas");
const ctx = canvas.getContext("2d");

const tools = [...document.querySelectorAll("[data-color]")];
const undoButton = document.querySelector("#undo");
const redoButton = document.querySelector("#redo");
const PEN_WIDTH = 3;
const ERASER_WIDTH = 24;
const eraserCursor = document.querySelector("#eraser-cursor");
let color = "#252b37";
let activePointer = null;
let last = null;
let lastEraser = false;
let strokes = [];
let redoStack = [];
let currentStroke = null;

function point(event) {
  const rect = canvas.getBoundingClientRect();
  return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}
function erasing(event) {
  return (event.buttons & (32 | 2)) !== 0; //펜측면 버튼 누를때 buttons:32 button:5
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
function drawSegment(a, b, strokeColor, width) {
  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.lineWidth = width;
  ctx.strokeStyle = strokeColor;
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(b.x, b.y);
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
  for (const stroke of strokes) {
    for (let i = 1; i < stroke.points.length; i++) {
      drawSegment(
        stroke.points[i - 1],
        stroke.points[i],
        stroke.color,
        stroke.width,
      );
    }
    if (stroke.points.length === 1)
      drawSegment(
        stroke.points[0],
        stroke.points[0],
        stroke.color,
        stroke.width,
      );
  }
  updateHistoryButtons();
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
    color,
    width: penWidth,
    points: [p],
  };
  strokes.push(currentStroke);
  redoStack = [];
  drawSegment(p, p, color, penWidth);
  updateHistoryButtons();
}
function down(event) {
  if (event.pointerType === "touch") {
    console.log("hand touch", {
      pointerType: event.pointerType,
      button: event.button,
      buttons: event.buttons,
    });
    touchPointers.add(event.pointerId);
    return;
  }

  if (
    event.pointerType === "pen" &&
    touchPointers.size >= 1 &&
    touchPointers.size <= 3 &&
    activePointer === null
  ) {
    console.log("Entering tuning mode", {
      pointerType: event.pointerType,
      button: event.button,
      buttons: event.buttons,
    });
    event.preventDefault();

    selectedPreset = touchPointers.size - 1;
    penWidth = presetWidths[selectedPreset];
    color = tools[selectedPreset].dataset.color;
    tools.forEach((tool, index) => {
      tool.classList.toggle("active", index === selectedPreset);
    });

    updatePresetUI();
    updateThickness();

    tuning = true;
    activePointer = event.pointerId;
    canvas.setPointerCapture(event.pointerId);

    tuneStartX = event.clientX;
    tuneStartY = event.clientY;
    tuneStartWidth = penWidth;

    showTuneSlider();
    return;
  }

  if (event.pointerType !== "pen" || activePointer !== null) return;
  console.log("Entering pen mode", {
    pointerType: event.pointerType,
    button: event.button,
    buttons: event.buttons,
  });
  event.preventDefault();
  activePointer = event.pointerId;
  canvas.setPointerCapture(event.pointerId);
  last = point(event);
  if (erasing(event)) {
    eraseStroke(last);
  } else {
    startStroke(last);
  }
}
function move(event) {
  if (
    event.pointerType === "pen" &&
    tuning &&
    event.pointerId === activePointer
  ) {
    event.preventDefault();
    const deltaX = event.clientX - tuneStartX;
    penWidth = calculateWidth(deltaX);
    presetWidths[selectedPreset] = penWidth;
    updateTuneSlider(penWidth);
    updatePresetUI();
    updateThickness();
    return;
  }

  updateEraserCursor(event, erasing(event));
  if (event.pointerId !== activePointer) return;
  event.preventDefault();
  const samples =
    typeof event.getCoalescedEvents === "function"
      ? event.getCoalescedEvents()
      : [event];
  for (const sample of samples.length ? samples : [event]) {
    const next = point(sample);
    const erase =
      erasing(sample) || (sample.buttons === undefined && erasing(event));
    if (erase) {
      eraseStroke(next);
      currentStroke = null;
    } else {
      drawSegment(last, next, color, penWidth);
      currentStroke.points.push(next);
    }
    last = next;
  }
}
function up(event) {
  if (event.pointerType === "touch") {
    touchPointers.delete(event.pointerId);
    return;
  }
  if (
    event.pointerType === "pen" &&
    tuning &&
    event.pointerId === activePointer
  ) {
    tuning = false;
    activePointer = null;
    hideTuneSlider();
    if (canvas.hasPointerCapture(event.pointerId)) {
      canvas.releasePointerCapture(event.pointerId);
    }
    return;
  }

  if (event.pointerId !== activePointer) return;
  activePointer = null;
  last = null;
  lastEraser = false;
  currentStroke = null;
  updateEraserCursor(event, erasing(event));
  if (canvas.hasPointerCapture(event.pointerId))
    canvas.releasePointerCapture(event.pointerId);
}
canvas.addEventListener("pointerdown", down);
canvas.addEventListener("pointermove", move);
canvas.addEventListener("pointerup", up);
canvas.addEventListener("pointercancel", up);
canvas.addEventListener("lostpointercapture", (event) => {
  if (activePointer === event.pointerId) {
    activePointer = null;
    last = null;
    currentStroke = null;
    updateEraserCursor(event, false);
  }
});
canvas.addEventListener("contextmenu", (event) => event.preventDefault());
tools.forEach((button, index) =>
  button.addEventListener("click", () => {
    selectedPreset = index;
    color = button.dataset.color;
    penWidth = presetWidths[selectedPreset];

    updateThickness();
    tools.forEach((tool) => {
      const active = tool === button;
      tool.classList.toggle("active", active);
    });
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

const SLIDER_WIDTH = 320;
let tuneSliderLeft = 0;
let tuneSliderTop = 0;
let offsetX = 0;
let offsetY = 0;
let dragging = false;

const thicknessDot = document.querySelector(".thickness-dot");
const thicknessValue = document.querySelector("#thickness-value");

function updatePresetUI() {
  const presets = document.querySelectorAll("[data-preset]");

  presets.forEach((preset, index) => {
    preset.classList.toggle("active", index === selectedPreset);
  });
}

function updateThickness() {
  thicknessDot.style.width = `${penWidth}px`;
  thicknessDot.style.height = `${penWidth}px`;
  thicknessDot.style.backgroundColor = color;
  thicknessValue.textContent = `${penWidth.toFixed(1)} px`;
}

function showTuneSlider() {
  const ratio = (penWidth - MIN_WIDTH) / (MAX_WIDTH - MIN_WIDTH);

  tuneSliderLeft = tuneStartX - ratio * SLIDER_WIDTH;
  tuneSliderTop = tuneStartY - 32;

  tuneSlider.style.left = `${tuneSliderLeft}px`;
  tuneSlider.style.top = `${tuneSliderTop}px`;
  tuneSlider.style.display = "block";

  updateTuneSlider(penWidth, tuneStartX);
}

function updateTuneSlider(width, pointerX) {
  const ratio = (width - MIN_WIDTH) / (MAX_WIDTH - MIN_WIDTH);
  const thumbX = ratio * SLIDER_WIDTH;

  tuneThumb.style.left = `${thumbX}px`;
  tuneValue.style.left = `${thumbX}px`;
  tuneValue.textContent = width.toFixed(1);
}

function hideTuneSlider() {
  tuneSlider.style.display = "none";
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

const MIN_WIDTH = 0.1;
const MAX_WIDTH = 15.0;
const SNAP_THRESHOLD = 0.2;
const PIXELS_PER_STEP = 4;

const touchPointers = new Set();
const presetWidths = [3.0, 3.0, 5.0];
let selectedPreset = 0;
let penWidth = presetWidths[selectedPreset];

let tuning = false;
let tuneStartX = 0;
let tuneStartY = 0;
let tuneStartWidth = 0;

function calculateWidth(deltaX) {
  let width =
    tuneStartWidth + (deltaX / SLIDER_WIDTH) * (MAX_WIDTH - MIN_WIDTH);

  width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, width));
  width = Math.round(width * 10) / 10;

  const nearestInteger = Math.round(width);

  if (Math.abs(width - nearestInteger) <= SNAP_THRESHOLD) {
    width = nearestInteger;
  }

  return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, width));
}

new ResizeObserver(resize).observe(canvas);
resize();
updateThickness();
