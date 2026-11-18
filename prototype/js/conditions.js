// 담당: 강민진 (11/17 정원준 구현, 민진 검토)
// 역할: 조건별 입력 UI
//  - C1: 툴바(펜 3종) + 굵기 슬라이더
//  - C2: 펜은 툴바에서 고르고, 손가락 + 펜 드래그로 굵기 조절 (손가락 수와 상관없이 굵기만)
//  - C3: Count & Tune. 툴바는 지금 펜·굵기 표시만 하고 누를 수 없음
// 세 조건 모두 같은 펜·같은 스냅 프리셋·같은 렌더링을 쓴다 (size.js).
// C1 슬라이더 길이는 C2·C3 펜 드래그 거리와 같다 (Size.TRACK_PX).

const Conditions = (() => {
  "use strict";

  const SETUP = {
    C1: { recognition: "off", toolbarPens: true, slider: true },
    C2: { recognition: "size", toolbarPens: true, slider: false },
    C3: { recognition: "count", toolbarPens: false, slider: false },
  };

  let current = null;
  const slider = document.querySelector("#size-slider");
  const thumb = slider.querySelector(".size-thumb");
  let sliding = null;   // pointerId

  // ---------- C1 굵기 슬라이더 ----------

  slider.style.width = `${Size.TRACK_PX}px`;
  for (const preset of Size.PRESETS) {
    const tick = document.createElement("div");
    tick.className = "size-tick";
    tick.style.left = `${Size.toRatio(preset) * Size.TRACK_PX}px`;
    slider.appendChild(tick);
  }

  function sizeAt(event) {
    const rect = slider.getBoundingClientRect();
    return Size.fromRatio((event.clientX - rect.left) / rect.width);
  }

  function syncSlider() {
    thumb.style.left = `${Size.toRatio(Pen.size) * Size.TRACK_PX}px`;
  }

  slider.addEventListener("pointerdown", (event) => {
    if (!SETUP[current]?.slider || sliding !== null || Ink.locked) return;
    event.preventDefault();
    sliding = event.pointerId;
    slider.setPointerCapture(event.pointerId);
    Logger.log("slider_start", { source: "slider", slot: Pen.slot, size: Pen.size });
    Pen.setSize(sizeAt(event), "slider");
  });
  slider.addEventListener("pointermove", (event) => {
    if (event.pointerId !== sliding) return;
    Pen.setSize(sizeAt(event), "slider");
  });
  const stop = (event) => {
    if (event.pointerId !== sliding) return;
    sliding = null;
    Logger.log("slider_end", { source: "slider", slot: Pen.slot, size: Pen.size });
  };
  slider.addEventListener("pointerup", stop);
  slider.addEventListener("pointercancel", stop);
  slider.addEventListener("lostpointercapture", stop);

  // ---------- 조건 전환 ----------

  function setup(condition) {
    if (!SETUP[condition]) throw new Error(`알 수 없는 조건: ${condition}`);
    current = condition;
    document.body.dataset.condition = condition;
    Recognition.setMode(SETUP[condition].recognition);
    syncSlider();
  }

  return {
    setup,
    syncSlider,
    get current() { return current; },
    get toolbarPens() { return current === null || SETUP[current].toolbarPens; },
  };
})();
