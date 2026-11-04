// 담당: 노태림
// 역할: C3 Count & Tune 인식 로직
//  - 펜 다운 순간 "정지한" 손가락 개수 → 펜 슬롯 1~3 결정 (4개 이상 무시)
//  - 손가락 정지 판정: 이동 거리 / 유지 시간 임계값 (파일럿에서 확정)
//  - 손가락 + 펜 드래그 → 가로 이동량으로 굵기 연속 조절, 프리셋 근처 스냅
//  - 상태: IDLE → ARMED (손가락 정지) → TUNING (펜 드래그) → 펜 업 시 확정
// 참고: tools/touch-probe.html 이 펜+손가락 동시 입력 확인용 검증 페이지

const Recognition = {
  STILL_PX: 12,    // 파일럿에서 조정
  STILL_MS: 120,   // 파일럿에서 조정
  PRESETS: [0.5, 1, 2, 4, 8],   // pt
  state: 'IDLE',

  // TODO: pointerdown / pointermove / pointerup 처리
  init(canvas, onSlotChange, onSizeChange) {},
};
