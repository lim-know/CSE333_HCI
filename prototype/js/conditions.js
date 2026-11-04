// 담당: 강민진
// 역할: 조건별 입력 UI
//  - C1: 툴바(펜 3종) + 굵기 슬라이더
//  - C2: 펜은 툴바에서 고르고, 손가락 1개 + 펜 드래그로 굵기 조절
//  - C3: Count & Tune (recognition.js 사용)
// 세 조건 모두 같은 펜·같은 스냅 프리셋·같은 렌더링을 쓴다.

const Conditions = {
  current: null,   // 'C1' | 'C2' | 'C3'

  // TODO: 조건에 맞는 UI 보이기/숨기기, 입력 핸들러 연결
  setup(condition) {},
};
