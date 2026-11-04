// 담당: 노태림
// 역할: 모든 이벤트를 메모리에 쌓고 실험이 끝나면 CSV로 저장.
// 컬럼 형식은 docs/log-schema.md 를 따른다. 형식을 바꾸면 분석 담당(정원준)과 합의할 것.

const Logger = {
  rows: [],
  meta: { participant: null, condition: null, phase: null },

  setMeta(fields) { Object.assign(this.meta, fields); },

  // TODO: docs/log-schema.md 컬럼 순서대로 한 줄 기록
  log(event) {
    this.rows.push({ ...this.meta, t: performance.now(), ...event });
  },

  // TODO: CSV 문자열로 변환해 파일로 다운로드 (파일명: P01_C3_main.csv 등)
  download() {},
};
