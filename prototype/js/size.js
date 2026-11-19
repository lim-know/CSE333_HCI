// 담당: 정원준 (11/17 추가)
// 역할: 굵기(pt) 계산을 세 조건이 똑같이 쓰도록 한곳에 모은다.
//  - 프리셋 1 / 2 / 4 / 6 / 8 pt. 프리셋 사이도 연속으로 고를 수 있다.
//  - 위치 ↔ 굵기는 선형 눈금: 간격과 굵기가 비례한다.
//  - 프리셋 근처 SNAP_PX 안에 들어오면 프리셋 값으로 붙는다.
//  - C1 슬라이더와 C2·C3 펜 드래그가 같은 트랙 길이와 스냅을 쓴다.

const Size = (() => {
  "use strict";

  const PRESETS = [1, 2, 3, 4, 5, 6, 7, 8]; // pt
  const MIN = PRESETS[0];
  const MAX = PRESETS[PRESETS.length - 1];
  const TRACK_PX = 320; // 최소 → 최대까지 펜(또는 슬라이더)이 움직이는 거리
  const SNAP_PX = 8; // 프리셋에서 이 거리 안이면 붙음 (파일럿에서 조정)
  const PX_PER_PT = 96 / 72;

  const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value));
  const round1 = (value) => Math.round(value * 10) / 10;

  // 굵기 → 트랙 위치 비율 (0~1) - 선형 눈금
  function toRatio(size) {
    return (clamp(size, MIN, MAX) - MIN) / (MAX - MIN);
  }

  // 트랙 위치 비율 → 굵기. 프리셋 근처면 붙인다.
  function fromRatio(ratio) {
    const r = clamp(ratio, 0, 1);
    for (const preset of PRESETS) {
      if (Math.abs(r - toRatio(preset)) * TRACK_PX <= SNAP_PX) return preset;
    }
    return clamp(round1(MIN + r * (MAX - MIN)), MIN, MAX);
  }

  // 펜 드래그: 시작 굵기에서 가로로 dx 픽셀 움직였을 때의 굵기
  function fromDrag(startSize, dx) {
    return fromRatio(toRatio(startSize) + dx / TRACK_PX);
  }

  const toPx = (size) => size * PX_PER_PT;
  const label = (size) =>
    `${Number.isInteger(size) ? size : size.toFixed(1)} pt`;

  return {
    PRESETS,
    MIN,
    MAX,
    TRACK_PX,
    SNAP_PX,
    toRatio,
    fromRatio,
    fromDrag,
    toPx,
    label,
  };
})();
