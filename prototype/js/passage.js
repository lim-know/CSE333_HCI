// 담당: 최유진(제시문 내용) · 강민진(진행) — 11/18 정원준 구현
// 역할: 제시문 표기법을 읽어서 (1) 화면에 그릴 조각 (2) 로그용 단계(scripts 표)로 바꾼다.
//
// 제시문 표기법 (scripts-data.js)
//   본문은 그냥 쓴다. 본문 펜은 BASE (검정 1pt).
//   표시할 곳은 [펜 굵기 표시|단어]
//     펜: 검정 / 빨강 / 형광       굵기: pt 숫자 (0.5, 1, 2, 4, 8 처럼 프리셋 권장)
//     표시: 밑줄 / 동그라미 / 칠하기 / 글씨
//   예) 핵심은 [빨강 2 밑줄|작업 기억]이다.
//
// 단계 = 펜 상태를 바꿔야 하는 곳. 표시 하나마다 "표시 펜으로 바꾸기" 단계가 생기고,
// 뒤에 본문이 이어지면 "본문 펜으로 돌아가기" 단계(task_type=return)가 하나 더 생긴다.
// 단계 유형(switch_only / size_only / switch_size)은 슬롯별로 굵기를 기억한다고 보고 계산한다.

const Passage = (() => {
  "use strict";

  const BASE = { slot: 1, size: 1 };
  const PEN_WORDS = { 검정: 1, 빨강: 2, 형광: 3 };
  const PEN_LABEL = { 1: "검정", 2: "빨강", 3: "형광펜" };
  const MARK_WORDS = {
    밑줄: "underline",
    동그라미: "circle",
    칠하기: "highlight",
    글씨: "word",
  };
  const MARK_LABEL = {
    underline: "밑줄",
    circle: "동그라미",
    highlight: "칠하기",
    word: "글씨",
    return: "본문",
  };
  const COLUMNS = [
    "script_id",
    "step_id",
    "exp",
    "step_type",
    "task_type",
    "language",
    "cue_text",
    "target_slot",
    "target_size",
    "on_preset",
    "target_x",
    "target_y",
    "text",
    "time_limit_ms",
  ];
  const DEFAULT_LIMIT_MS = 60000;

  // "[빨강 2 밑줄|작업 기억]" 들을 찾아 본문/표시 조각으로 나눈다
  function segments(markup) {
    const parts = [];
    const pattern = /\[([^\]|]+)\|([^\]]+)\]/g;
    let last = 0;
    let match;
    let markNo = 0;
    while ((match = pattern.exec(markup))) {
      if (match.index > last)
        parts.push({ kind: "text", text: markup.slice(last, match.index) });
      const words = match[1].trim().split(/\s+/);
      if (words.length !== 3)
        throw new Error(
          `표시 형식 오류: "[${match[1]}|…]" → [펜 굵기 표시|단어]`,
        );
      const [penWord, sizeWord, markWord] = words;
      const slot = PEN_WORDS[penWord];
      const size = Number(sizeWord.replace(/pt$/i, ""));
      const mark = MARK_WORDS[markWord];
      if (!slot) throw new Error(`펜 이름 오류: "${penWord}" (검정/빨강/형광)`);
      if (!(size > 0)) throw new Error(`굵기 오류: "${sizeWord}"`);
      if (!mark)
        throw new Error(
          `표시 이름 오류: "${markWord}" (밑줄/동그라미/칠하기/글씨)`,
        );
      parts.push({
        kind: "mark",
        no: ++markNo,
        slot,
        size,
        mark,
        text: match[2].trim(),
      });
      last = pattern.lastIndex;
    }
    if (last < markup.length)
      parts.push({ kind: "text", text: markup.slice(last) });
    if (
      /[[\]|]/.test(
        parts
          .filter((p) => p.kind === "text")
          .map((p) => p.text)
          .join(""),
      )
    ) {
      throw new Error("닫히지 않은 [ ] 또는 | 가 본문에 남아 있어요");
    }
    return parts;
  }

  const label = (slot, size) => `${PEN_LABEL[slot]} ${size}pt`;

  // 조각 → 단계. initialSizes 는 블록 시작 때 슬롯별 굵기 (script.js DEFAULT_SIZES)
  function steps(parts, initialSizes, presets = [1, 2, 3, 4, 5, 6, 7, 8]) {
    const sizes = { ...initialSizes };
    let slot = BASE.slot;
    const out = [];
    const require = (want, info) => {
      const sameSlot = want.slot === slot;
      if (sameSlot && sizes[slot] === want.size) {
        throw new Error(
          `바꿀 게 없는 단계: ${info.text} (${label(want.slot, want.size)})`,
        );
      }
      const type = sameSlot
        ? "size_only"
        : sizes[want.slot] === want.size
          ? "switch_only"
          : "switch_size";
      slot = want.slot;
      sizes[slot] = want.size;
      out.push({ ...info, slot: want.slot, size: want.size, step_type: type });
    };

    // 단계를 우선순위별로 분류해서 수집
    // 우선: 모든 색상의 "글씨" 단계만
    // 나머지: 밑줄, 동그라미, 칠하기 (모든 색상)
    const wordSteps = []; // 글씨 단계 (모든 색상)
    const otherSteps = []; // 밑줄, 동그라미, 칠하기 (모든 색상)

    parts.forEach((part, i) => {
      if (part.kind !== "mark") return;
      const stepInfo = {
        task_type: part.mark,
        mark_no: part.no,
        text: part.text,
      };

      // 글씨 단계인지 확인
      const isWord = part.mark === "word";

      if (isWord) {
        wordSteps.push({ part, stepInfo });
      } else {
        otherSteps.push({ part, stepInfo });
      }

      // return 단계도 처리
      const rest = parts.slice(i + 1);
      const next = rest.find((p) => p.kind === "mark" || p.text.trim());

      // wordSteps만 return 추가 (줄글/본문으로 돌아가기)
      // otherSteps는 절대 return 없음 (줄글과 같은 순서에 있을 수 없음)
      if (isWord && next && next.kind === "text") {
        const returnInfo = {
          task_type: "return",
          mark_no: part.no,
          text: next.text.trim().slice(0, 12),
        };
        wordSteps.push({ part, stepInfo: returnInfo, isReturn: true });
      }
    });

    // 글씨 단계 먼저 처리
    wordSteps.forEach(({ part, stepInfo, isReturn }) => {
      if (!isReturn) {
        require(part, stepInfo);
      } else {
        require(BASE, stepInfo);
      }
    });

    // 그 다음 나머지 단계(밑줄, 동그라미, 칠하기) 처리
    otherSteps.forEach(({ part, stepInfo, isReturn }) => {
      if (!isReturn) {
        require(part, stepInfo);
      } else {
        require(BASE, stepInfo);
      }
    });

    return out.map((s, i) => ({
      ...s,
      step_id: String(i + 1).padStart(2, "0"),
      on_preset: presets.includes(s.size) ? 1 : 0,
      cue_text:
        s.task_type === "return"
          ? `본문 ${label(s.slot, s.size)}`
          : `${label(s.slot, s.size)} ${MARK_LABEL[s.task_type]}`,
    }));
  }

  const csvValue = (v) => {
    const s = v === undefined || v === null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };

  // 로그 분석용 scripts 표 (docs/log-schema.md 와 같은 열)
  function toCsv(id, list, limitMs = DEFAULT_LIMIT_MS) {
    const rows = list.map((s) => ({
      script_id: id,
      step_id: s.step_id,
      exp: "exp2",
      step_type: s.step_type,
      task_type: s.task_type,
      language: "ko",
      cue_text: s.cue_text,
      target_slot: s.slot,
      target_size: s.size,
      on_preset: s.on_preset,
      target_x: "",
      target_y: "",
      text: s.text,
      time_limit_ms: limitMs,
    }));
    return (
      [
        COLUMNS.join(","),
        ...rows.map((r) => COLUMNS.map((c) => csvValue(r[c])).join(",")),
      ].join("\n") + "\n"
    );
  }

  function load(id, markup, initialSizes, presets) {
    const parts = segments(markup.replace(/\s+/g, " ").trim());
    const list = steps(parts, initialSizes, presets);
    return { id, parts, steps: list, text: toCsv(id, list) };
  }

  return { BASE, PEN_LABEL, MARK_LABEL, segments, steps, toCsv, load, label };
})();
