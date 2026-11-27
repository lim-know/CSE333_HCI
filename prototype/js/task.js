// 담당: 강민진 (11/17 정원준 구현, 민진 검토)
// 역할: 실험 진행
//  - 시작 화면: 참가자 번호 → 조건 순서·제시문 세트를 배정표에서 자동으로 고름 (직접 바꿀 수도 있음)
//  - 조건마다: 설명 → 연습 블록 → 본과제 블록 → 설문 안내
//  - 블록 = 제시문 하나 (11/18 팀 결정). 위에 제시문, 아래 칸에 옮겨 적으면서 표시된 곳은 지정한 펜·굵기로 표시
//  - 단계 = 펜 상태를 바꿔야 하는 곳 (passage.js). 지금 단계의 펜·굵기로 그은 획이 끝나면 다음 단계로
//    → 단계 시작(cue_shown) = 앞 단계의 정답 획이 끝난 때. 전환 시간은 "이전 획 끝 → 정답 획"으로 본다
//  - 다른 펜·굵기로 쓰면 알림. 표시가 남았는데 완료를 누르면 알림 (넘어가지 않음)
//  - 참가자에게 안 보이는 단계별 시간 제한(time_limit_ms)이 지나면 timeout 으로 다음 단계
//  - 블록이 끝날 때마다 로그 CSV 저장. 세션이 끝나면 sessions/participants 한 줄과 사용한 스크립트도 저장
// 진행자 단축키: Ctrl+Shift+S = 이 단계 건너뛰기(skipped), Ctrl+Shift+Q = 세션 중단
// 제시문은 scripts-data.js (실험 설계 담당: 최유진)

const Task = (() => {
  "use strict";

  // 조건 순서 6가지 × 2명, 제시문 세트도 같이 돌림 (11/15 안건 문서 표)
  const ORDERS = [
    { conditions: ["C1", "C2", "C3"], sets: ["A", "B", "C"] }, // P01, P02
    { conditions: ["C1", "C3", "C2"], sets: ["A", "B", "C"] }, // P03, P04
    { conditions: ["C2", "C1", "C3"], sets: ["B", "C", "A"] }, // P05, P06
    { conditions: ["C2", "C3", "C1"], sets: ["C", "A", "B"] }, // P07, P08
    { conditions: ["C3", "C1", "C2"], sets: ["B", "C", "A"] }, // P09, P10
    { conditions: ["C3", "C2", "C1"], sets: ["C", "A", "B"] }, // P11, P12
  ];

  // 과제 설명 (세 조건 공통) + 조건 설명. 진행 대본 확정 전 임시 문구 (최유진 검토)
  const HOW_TO = `위의 제시문을 아래 칸에 옮겨 적으세요. 본문은 <b>검정 1pt</b>로 씁니다.
    표시된 곳은 적힌 펜·굵기로 표시하세요: <b>밑줄</b>(단어 아래 선), <b>동그라미</b>(단어 둘레),
    <b>칠하기</b>(단어 위를 형광펜으로 덧칠), <b>글씨</b>(그 펜으로 단어를 씀). 표시한 뒤에는 다시 검정 1pt로 이어 씁니다.`;
  const INTRO = {
    C1: "펜은 툴바에서 누르고, 굵기는 툴바의 슬라이더로 맞춥니다.",
    C2: "펜은 툴바에서 고르세요. 굵기는 왼손 손가락 하나를 화면에 대고, 펜을 화면에 댄 채 좌우로 움직여 맞춥니다. 펜을 떼면 확정됩니다.",
    C3: "왼손 손가락 1개 = 검정 펜, 2개 = 빨간 펜, 3개 = 노란 형광펜입니다. 손가락을 화면에 댄 채 펜을 대면 펜이 바뀌고, 그대로 좌우로 움직이면 굵기가 바뀝니다. 펜을 떼면 확정됩니다.",
  };
  const SIZE_TOL = 1.1; // 분석(build_steps.py SIZE_TOL_RATIO)과 같은 기준
  const sameSize = (a, b) =>
    a > 0 && b > 0 && a / b <= SIZE_TOL && b / a <= SIZE_TOL;
  const sameState = (stroke, want) =>
    want && stroke.slot === want.slot && sameSize(stroke.size, want.size);
  const BUILD = "exp-2026-11-28"; // 코드를 고치면 바꿔 주세요. 로그 block_start 에 남음
  Logger.configure({ build: BUILD });

  const $ = (selector) => document.querySelector(selector);
  const banner = $("#cue-banner");
  const cueText = $("#cue-text");
  const cueProgress = $("#cue-progress");
  const doneButton = $("#done-button");
  const homeButton = $("#home-button");
  const overlay = $("#screen");
  const target = $("#target");
  const passage = $("#passage");
  const toast = $("#toast");
  const desk = $(".desk");

  let session = null; // 진행 중인 세션
  let stepDone = null; // 지금 단계를 끝내는 함수 (outcome) => void  (건너뛰기·중단용)
  let blockDone = null; // 완료 버튼을 눌렀을 때 부르는 함수
  let aborted = false;
  let closeScreen = null; // 열린 안내 화면을 닫는 함수 (세션 중단용)

  // ---------- 스크립트 ----------

  function parseCsv(text) {
    const rows = [];
    let row = [];
    let field = "";
    let quoted = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i + 1] === '"') {
          field += '"';
          i++;
        } else if (c === '"') quoted = false;
        else field += c;
      } else if (c === '"') quoted = true;
      else if (c === ",") {
        row.push(field);
        field = "";
      } else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(field);
        field = "";
        if (row.some((v) => v !== "")) rows.push(row);
        row = [];
      } else field += c;
    }
    if (field !== "" || row.length) {
      row.push(field);
      rows.push(row);
    }
    const [header, ...body] = rows;
    return body.map((values) =>
      Object.fromEntries(
        header.map((key, i) => [key.trim(), (values[i] ?? "").trim()]),
      ),
    );
  }

  // practice → PASSAGES.practice, exp2A → PASSAGES.A
  function loadScript(id, markupIndex = 0) {
    const key = id === "practice" ? "practice" : id.replace(/^exp2/, "");
    const data = PASSAGES[key];
    if (!data) throw new Error(`제시문 없음: ${key} (scripts-data.js 확인)`);

    // 배열인 경우 해당 인덱스의 항목 선택, 문자열인 경우 그대로 사용
    const markup = Array.isArray(data) ? data[markupIndex] : data;
    if (!markup)
      throw new Error(`제시문 인덱스 범위 초과: ${key}[${markupIndex}]`);

    // 배열인 경우 블록 번호를 ID에 포함 (exp2A_0, exp2A_1 등)
    const scriptId = Array.isArray(data) ? `${id}_${markupIndex}` : id;
    return Passage.load(scriptId, markup, DEFAULT_SIZES, [...Size.PRESETS]);
  }

  // 제시문 세트의 길이 반환 (배열이면 길이, 문자열이면 1)
  function getPassageCount(key) {
    const data = PASSAGES[key];
    return Array.isArray(data) ? data.length : 1;
  }

  // ---------- 화면 ----------

  function showScreen(html, buttons) {
    Ink.locked = true;
    overlay.innerHTML = `<div class="screen-card">${html}<div class="screen-buttons"></div></div>`;
    const row = overlay.querySelector(".screen-buttons");
    return new Promise((resolve) => {
      closeScreen = (value) => {
        closeScreen = null;
        overlay.hidden = true;
        resolve(value);
      };
      for (const [label, value, cls] of buttons) {
        const button = document.createElement("button");
        button.textContent = label;
        if (cls) button.className = cls;
        button.addEventListener(
          "click",
          () => closeScreen && closeScreen(value),
        );
        row.appendChild(button);
      }
      overlay.hidden = false;
    });
  }

  function setBanner(text, progress = "", done = false) {
    cueText.innerHTML = text;
    cueProgress.textContent = progress;
    doneButton.hidden = !done;
  }

  const escapeHtml = (s) =>
    String(s).replace(
      /[&<>"]/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c],
    );

  // ---------- 제시문 화면 ----------

  const markColor = (slot) => PENS[slot].color;

  // 제시문 패널을 그리고, 그 아래를 쓰는 칸으로 표시한다
  function renderPassage(script) {
    passage.innerHTML = script.parts
      .map((part) => {
        if (part.kind === "text") return escapeHtml(part.text);
        const tag = `${Passage.label(part.slot, part.size)} ${Passage.MARK_LABEL[part.mark]}`;
        return (
          `<span class="mark m-${part.mark}" data-no="${part.no}" style="--ink:${markColor(part.slot)}">` +
          `<span class="mark-text">${escapeHtml(part.text)}</span><span class="mark-tag">${escapeHtml(tag)}</span></span>`
        );
      })
      .join("");
    passage.hidden = false;
    const top = passage.offsetTop + passage.offsetHeight + 100;
    target.innerHTML = `<div class="write-area" style="top:${top}px"></div>`;
  }

  function clearPassage() {
    passage.hidden = true;
    passage.innerHTML = "";
    target.innerHTML = "";
  }

  let toastTimer = null;
  function showToast(text) {
    const writeArea = target.querySelector(".write-area");
    toast.style.top = `${(passage.offsetTop + passage.offsetHeight + writeArea.offsetTop) / 2}px`;
    toast.textContent = text;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.hidden = true;
    }, 2500);
  }

  // ---------- 블록 ----------
  // 단계는 획으로 진행된다: 지금 단계의 펜·굵기로 그은 획이 끝나면 다음 단계.
  // 마지막 단계는 완료 버튼을 누를 때 step_end (그 뒤 본문 필기도 단계 안에 남도록)

  function runBlock(meta, script, title) {
    console.log("script.parts", script.parts);
    console.log("script.steps", script.steps);
    return new Promise((resolve) => {
      Pen.reset();
      Ink.clear();
      resetToolbarPosition();
      Conditions.setup(meta.condition);
      Logger.startBlock({ ...meta, script_id: script.id });
      renderPassage(script);
      Ink.locked = false;

      const steps = script.steps;
      const marks = script.parts.filter((p) => p.kind === "mark").length;
      let index = -1;
      let reached = false; // 지금 단계의 정답 획이 나왔는지 (마지막 단계용)
      let prev = { ...Passage.BASE }; // 바로 앞에 요구된 상태. 이 상태로 쓰는 건 그냥 본문 필기
      let timer = null;

      const markEl = (no) => passage.querySelector(`.mark[data-no="${no}"]`);
      const show = () => {
        passage
          .querySelectorAll(".mark.current")
          .forEach((el) => el.classList.remove("current"));
        const step = steps[index];
        const doneMarks = passage.querySelectorAll(
          ".mark.done, .mark.missed",
        ).length;
        let cue = "제시문을 끝까지 옮겨 적고 <strong>완료</strong>를 누르세요";
        if (step && !reached) {
          if (step.task_type === "return")
            cue = `다음: <strong>${escapeHtml(Passage.label(step.slot, step.size))}</strong> ${step.text}`;
          else {
            markEl(step.mark_no)?.classList.add("current");
            cue = `다음: <strong>${escapeHtml(step.cue_text)}</strong>`;
          }
        }
        setBanner(
          `<span class="cue-title">${escapeHtml(title)}</span>${cue}`,
          `표시 ${doneMarks} / ${marks}`,
          true,
        );
      };

      const begin = (i) => {
        index = i;
        reached = false;
        const step = steps[i];
        Logger.cueShown(step.step_id, { slot: Pen.slot, size: Pen.size });
        timer = setTimeout(
          () => finish("timeout"),
          Number(step.time_limit_ms) || 60000,
        );
        show();
      };

      // 지금 단계를 끝내고 다음 단계로
      const finish = (outcome) => {
        clearTimeout(timer);
        const step = steps[index];
        if (!step) return;
        Logger.stepEnd(outcome, { slot: Pen.slot, size: Pen.size });
        if (step.task_type !== "return" && outcome !== "completed")
          markEl(step.mark_no)?.classList.add("missed");
        prev =
          outcome === "completed"
            ? { slot: step.slot, size: step.size }
            : { slot: Pen.slot, size: Pen.size };
        if (index + 1 < steps.length) begin(index + 1);
        else {
          index = steps.length;
          show();
        }
      };

      // 정답 획 (마지막 단계면 완료 버튼까지 단계를 열어 둔다)
      const correct = () => {
        const step = steps[index];
        if (step.task_type !== "return")
          markEl(step.mark_no)?.classList.add("done");
        if (index + 1 < steps.length) finish("completed");
        else {
          clearTimeout(timer);
          reached = true;
          prev = { slot: step.slot, size: step.size };
          show();
        }
      };

      Ink.onStroke = (stroke) => {
        const step = steps[index];
        if (!step || reached) return;
        if (sameState(stroke, step)) correct();
        else if (!sameState(stroke, prev)) {
          showToast(
            `지금 ${Passage.label(stroke.slot, stroke.size)}입니다. 표시: ${step.task_type === "return" ? "본문 " + Passage.label(step.slot, step.size) : step.cue_text}`,
          );
        }
      };

      const end = (lastOutcome) => {
        clearTimeout(timer);
        if (index < steps.length)
          Logger.stepEnd(lastOutcome, { slot: Pen.slot, size: Pen.size });
        Ink.onStroke = null;
        Ink.locked = true;
        stepDone = null;
        blockDone = null;
        clearPassage();
        setBanner("", "", false);
        Logger.endBlock();
        resolve();
      };

      // 진행자: 건너뛰기(skipped) / 중단
      stepDone = (outcome) => {
        if (aborted) return end(outcome);
        if (index >= steps.length) return;
        if (reached) return end("completed");
        finish(outcome);
      };

      blockDone = () => {
        // 미완료 시 경고 메시지 (기존 코드)
        if (index < steps.length && !reached) {
          showToast("아직 표시하지 않은 곳이 있어요");
          end("skipped");
          return;
        }
        end("completed");
      };

      begin(0);
    });
  }

  // ---------- 세션 ----------

  function assignOrder(participant) {
    const n = Number((participant.match(/\d+/) || ["0"])[0]);
    if (n < 1) return ORDERS[0];
    return ORDERS[Math.floor(((n - 1) % 12) / 2)];
  }

  function csvLine(values) {
    return values
      .map((v) => {
        const s = v === undefined || v === null ? "" : String(v);
        return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
      })
      .join(",");
  }

  function downloadText(name, text) {
    const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // 분석 폴더에 넣을 sessions/participants 한 줄, 사용한 스크립트
  function saveSessionFiles(s) {
    console.log("saveSessionFiles called - final save");
    const browser =
      (navigator.userAgentData?.brands || [])
        .filter((b) => !/Not.?A.?Brand/i.test(b.brand))
        .map((b) => `${b.brand} ${b.version}`)
        .join(" / ") || navigator.userAgent;
    const sessionCols = [
      "session_id",
      "participant",
      "condition_order",
      "script_variant",
      "date",
      "device",
      "browser",
      "windows",
      "screen_w",
      "screen_h",
      "dpr",
      "experimenter",
      "notes",
    ];
    const sessionRow = [
      s.session_id,
      s.participant,
      s.order.conditions.join("-"),
      s.order.sets.join("-"),
      new Date().toISOString().slice(0, 10),
      "",
      browser,
      "",
      window.screen.width,
      window.screen.height,
      window.devicePixelRatio,
      s.experimenter,
      s.aborted ? "세션 중단됨" : "",
    ];
    downloadText(
      `session_${s.session_id}.csv`,
      `${csvLine(sessionCols)}\n${csvLine(sessionRow)}\n`,
    );

    const partCols = [
      "participant",
      "handedness",
      "native_language",
      "note_language",
      "tablet_note_months",
    ];
    const partRow = [
      s.participant,
      s.handedness,
      "ko",
      s.note_language,
      s.tablet_note_months,
    ];
    downloadText(
      `participant_${s.participant}.csv`,
      `${csvLine(partCols)}\n${csvLine(partRow)}\n`,
    );
  }

  // 조건별 script 저장 (각 조건 끝마다 호출)
  function saveConditionFiles(conditionScripts) {
    console.log("saveConditionFiles called");
    for (const script of conditionScripts.values())
      downloadText(`script_${script.id}.csv`, script.text);
  }

  async function runSession(s) {
    document.body.classList.add("study");
    Ink.allowEraser = true; //지우개 가능
    aborted = false;
    s.scripts = new Map();
    let block = 0;
    try {
      for (let k = 0; k < 3 && !aborted; k++) {
        const condition = s.order.conditions[k];
        const set = s.order.sets[k];
        await showScreen(
          `<p class="screen-step">${k + 1} / 3</p><h1>방법 ${k + 1}</h1>
           <p>${HOW_TO}</p><p>${INTRO[condition]}</p><p class="screen-note">진행자: 조건 ${condition}, 제시문 세트 ${set}</p>`,
          [["연습 시작", true]],
        );
        if (aborted) break;

        // 블록 로그 자동 다운로드 활성화 (매 블록 끝마다 다운로드)
        Logger.configure({ download: true });

        Conditions.setup(condition);
        const base = {
          session_id: s.session_id,
          participant: s.participant,
          condition,
          exp: "exp2",
        };
        if (s.practice) {
          const practice = loadScript("practice");
          s.scripts.set(practice.id, practice);
          await runBlock(
            { ...base, block: ++block, phase: "practice" },
            practice,
            `방법 ${k + 1} · 연습`,
          );
          if (aborted) break;
          await showScreen(
            "<h1>연습 끝</h1><p>준비되면 본과제를 시작하세요.</p>",
            [["본과제 시작", true]],
          );
          if (aborted) break;
        }
        const main_count = getPassageCount(set);
        const conditionScripts = new Map(); // 이 조건의 script만 저장
        for (let m = 0; m < main_count && !aborted; m++) {
          const main = loadScript(`exp2${set}`, m);
          s.scripts.set(main.id, main);
          conditionScripts.set(main.id, main); // 이 조건의 script에도 추가
          await runBlock(
            { ...base, block: ++block, phase: "main" },
            main,
            `방법 ${k + 1} · 과제 ${m + 1}/${main_count}`,
          );
          if (aborted) break;
        }

        // 각 조건이 끝났을 때 이 조건의 script 저장
        if (!aborted) {
          saveConditionFiles(conditionScripts);
        }

        if (k < 2) {
          await showScreen(
            "<h1>이 방법은 끝났습니다</h1><p>설문(NASA-TLX)을 작성해 주세요. 잠시 쉬었다가 다음으로 넘어갑니다.</p>",
            [["진행자: 다음 방법으로", true]],
          );
        }
      }
    } catch (error) {
      console.error(error);
      alertScreen(`오류: ${escapeHtml(error.message)}`);
    }
    s.aborted = aborted;
    // 세션 완료 시 최종 session/participant 파일 저장
    saveSessionFiles(s);
    stepDone = null;
    const saved = Logger.savedBlocks().filter((name) =>
      name.includes(`_${s.session_id}_`),
    );
    const list = saved
      .map(
        (name) =>
          `<li><button class="link" data-name="${escapeHtml(name)}">${escapeHtml(name)}</button></li>`,
      )
      .join("");
    const end = showScreen(
      `<h1>${aborted ? "세션 중단" : "실험 끝"}</h1>
       <p>${aborted ? "" : "마지막 설문과 선호 순위를 진행해 주세요. "}다운로드 폴더의 파일을 팀 드라이브로 옮겨 주세요.</p>
       <p class="screen-note">브라우저에 백업된 블록 (누르면 다시 받기)</p><ul class="saved">${list}</ul>`,
      [["처음 화면", true]],
    );
    overlay.querySelectorAll("button.link").forEach((b) =>
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        Logger.redownload(b.dataset.name);
      }),
    );
    await end;
    document.body.classList.remove("study");
    home();
  }

  function alertScreen(html) {
    return showScreen(`<h1>문제가 생겼어요</h1><p>${html}</p>`, [
      ["확인", true],
    ]);
  }

  // ---------- 처음 화면 ----------

  function home() {
    session = null;
    Ink.locked = true;
    Ink.allowEraser = true;
    document.body.classList.remove("study", "free");
    clearPassage();
    setBanner("Count &amp; Tune 실험", "", false);
    homeButton.hidden = true;
    Ink.clear();
    overlay.innerHTML = $("#setup-template").innerHTML;
    overlay.hidden = false;

    const form = overlay.querySelector("form");
    const pInput = form.elements.participant;
    const fill = () => {
      const order = assignOrder(pInput.value.trim());
      form.elements.order.value = order.conditions.join("-");
      form.elements.sets.value = order.sets.join("-");
    };
    pInput.addEventListener("input", fill);
    fill();

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const f = form.elements;
      const conditions = f.order.value.trim().toUpperCase().split("-");
      const sets = f.sets.value.trim().toUpperCase().split("-");
      const valid =
        conditions.length === 3 &&
        new Set(conditions).size === 3 &&
        conditions.every((c) => /^C[123]$/.test(c)) &&
        sets.length === 3 &&
        sets.every((v) => /^[ABC]$/.test(v));
      const participant = f.participant.value.trim().toUpperCase();
      if (!valid || !/^[A-Z]+\d+$/.test(participant)) {
        form.querySelector(".form-error").textContent =
          "참가자 번호(P01), 조건 순서(C1-C2-C3), 세트(A-B-C)를 확인해 주세요.";
        return;
      }
      overlay.hidden = true;
      session = {
        participant,
        session_id: `${participant}-${f.session.value.trim() || "1"}`,
        experimenter: f.experimenter.value.trim(),
        handedness: f.handedness.value,
        note_language: f.note_language.value,
        tablet_note_months: f.tablet_note_months.value.trim(),
        practice: f.practice.checked,
        order: { conditions, sets },
      };
      runSession(session);
    });

    overlay.querySelectorAll("[data-free]").forEach((button) =>
      button.addEventListener("click", () => {
        startFree(button.dataset.free);
      }),
    );
  }

  // 자유 모드: 로그 없이 조건만 바꿔서 써 보기 (실행 취소·지우개 사용 가능)
  function startFree(condition) {
    overlay.hidden = true;
    document.body.classList.add("free");
    Pen.reset();
    Conditions.setup(condition);
    Ink.locked = false;
    setBanner(`자유 모드 · ${condition}`, "", false);
    homeButton.hidden = false;
  }

  // ---------- 버튼·단축키 ----------

  doneButton.addEventListener("click", () => {
    if (blockDone) blockDone();
  });
  homeButton.addEventListener("click", home);

  window.addEventListener("keydown", (event) => {
    if (!event.ctrlKey || !event.shiftKey) return;
    const key = event.key.toLowerCase();
    if (key === "s" && stepDone) {
      event.preventDefault();
      stepDone("skipped");
    } else if (key === "q" && session) {
      event.preventDefault();
      aborted = true;
      if (stepDone) stepDone("skipped");
      else if (closeScreen) closeScreen(false);
    }
  });

  // ?log=dev 로 열면 logger.js 개발 모드가 이미 블록을 시작했으므로 바로 자유 모드로
  if (new URLSearchParams(location.search).get("log") === "dev") {
    startFree(new URLSearchParams(location.search).get("condition") || "C3");
  } else {
    home();
  }

  return { assignOrder, parseCsv, ORDERS };
})();
