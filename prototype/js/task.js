// 담당: 강민진 (11/17 정원준 구현, 민진 검토)
// 역할: 실험 진행
//  - 시작 화면: 참가자 번호 → 조건 순서·제시문 세트를 배정표에서 자동으로 고름 (직접 바꿀 수도 있음)
//  - 조건마다: 설명 → 연습 블록 → 본과제 블록 → 설문 안내
//  - 단계마다: 상단 배너에 지시 하나 + 완료 버튼. 지시가 그려진 시각을 Logger.cueShown 으로 기록
//  - 참가자에게 안 보이는 시간 제한(time_limit_ms)이 지나면 timeout 으로 넘어감
//  - 블록이 끝날 때마다 로그 CSV 저장. 세션이 끝나면 sessions/participants 한 줄과 사용한 스크립트도 저장
// 진행자 단축키: Ctrl+Shift+S = 이 단계 건너뛰기(skipped), Ctrl+Shift+Q = 세션 중단
// 과제 내용은 scripts-data.js (실험 설계 담당: 최유진)

const Task = (() => {
  "use strict";

  // 조건 순서 6가지 × 2명, 제시문 세트도 같이 돌림 (11/15 안건 문서 표)
  const ORDERS = [
    { conditions: ["C1", "C2", "C3"], sets: ["A", "B", "C"] },   // P01, P02
    { conditions: ["C1", "C3", "C2"], sets: ["A", "B", "C"] },   // P03, P04
    { conditions: ["C2", "C1", "C3"], sets: ["B", "C", "A"] },   // P05, P06
    { conditions: ["C2", "C3", "C1"], sets: ["C", "A", "B"] },   // P07, P08
    { conditions: ["C3", "C1", "C2"], sets: ["B", "C", "A"] },   // P09, P10
    { conditions: ["C3", "C2", "C1"], sets: ["C", "A", "B"] },   // P11, P12
  ];

  // 조건 설명 (진행 대본 확정 전 임시 문구. 최유진 검토)
  const INTRO = {
    C1: "위쪽 툴바에서 펜을 누르고, 툴바의 슬라이더로 굵기를 맞춘 뒤 표시하세요.",
    C2: "펜은 위쪽 툴바에서 고르세요. 굵기는 왼손 손가락 하나를 화면에 대고, 펜을 화면에 댄 채 좌우로 움직여 맞춥니다. 펜을 떼면 확정됩니다.",
    C3: "왼손 손가락 1개 = 검정 펜, 2개 = 빨간 펜, 3개 = 노란 형광펜입니다. 손가락을 화면에 댄 채 펜을 대면 펜이 바뀌고, 그대로 좌우로 움직이면 굵기가 바뀝니다. 펜을 떼면 확정됩니다.",
  };
  const ACTION = {
    underline: "밑줄 긋기", circle: "동그라미 치기", highlight: "덧칠하기",
    word: "단어 쓰기", line: "선 긋기", copy: "따라 쓰기",
  };
  const DEFAULT_LIMIT_MS = 30000;
  const BUILD = "exp-2026-11-17";   // 코드를 고치면 바꿔 주세요. 로그 block_start 에 남음
  Logger.configure({ build: BUILD });

  const $ = (selector) => document.querySelector(selector);
  const banner = $("#cue-banner");
  const cueText = $("#cue-text");
  const cueProgress = $("#cue-progress");
  const doneButton = $("#done-button");
  const homeButton = $("#home-button");
  const overlay = $("#screen");
  const target = $("#target");
  const desk = $(".desk");

  let session = null;      // 진행 중인 세션
  let stepDone = null;     // 지금 단계를 끝내는 함수 (outcome) => void
  let aborted = false;
  let closeScreen = null;  // 열린 안내 화면을 닫는 함수 (세션 중단용)

  // ---------- 스크립트 ----------

  function parseCsv(text) {
    const rows = [];
    let row = [];
    let field = "";
    let quoted = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
        else if (c === '"') quoted = false;
        else field += c;
      } else if (c === '"') quoted = true;
      else if (c === ",") { row.push(field); field = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(field); field = "";
        if (row.some((v) => v !== "")) rows.push(row);
        row = [];
      } else field += c;
    }
    if (field !== "" || row.length) { row.push(field); rows.push(row); }
    const [header, ...body] = rows;
    return body.map((values) => Object.fromEntries(header.map((key, i) => [key.trim(), (values[i] ?? "").trim()])));
  }

  function loadScript(id) {
    const text = SCRIPT_CSV[id];
    if (!text) throw new Error(`스크립트 없음: ${id} (scripts-data.js 확인)`);
    return { id, text, steps: parseCsv(text) };
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
        button.addEventListener("click", () => closeScreen && closeScreen(value));
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

  const escapeHtml = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  // 목표 위치에 단어(또는 따라 쓸 문장)를 띄운다. 화면 밖이면 안쪽으로 당긴다.
  function showTarget(step) {
    target.innerHTML = "";
    const rect = desk.getBoundingClientRect();
    const isCopy = step.step_type === "copy";
    const box = document.createElement("div");
    box.className = isCopy ? "target copy" : `target ${step.task_type}`;
    box.innerHTML = isCopy
      ? `<div class="copy-text">${escapeHtml(step.text)}</div><div class="copy-area"></div>`
      : `<span class="target-word">${escapeHtml(step.text || "목표")}</span>`;
    target.appendChild(box);
    const w = box.offsetWidth;
    const h = box.offsetHeight;
    const x = Math.min(Math.max(Number(step.target_x) || rect.width / 2, 16), rect.width - w - 16);
    const y = Math.min(Math.max(Number(step.target_y) || rect.height / 2, 96), rect.height - h - 16);
    box.style.left = `${x}px`;
    box.style.top = `${y}px`;
  }

  // ---------- 단계와 블록 ----------

  function runStep(step, index, total) {
    return new Promise((resolve) => {
      Ink.clear();
      showTarget(step);
      const action = ACTION[step.task_type] || step.task_type;
      const cue = step.step_type === "copy"
        ? `${escapeHtml(step.cue_text)}`
        : `<strong>${escapeHtml(step.cue_text)}</strong><span class="cue-action">${escapeHtml(action)}</span>`;
      setBanner(cue, `${index + 1} / ${total}`, true);
      Ink.locked = false;
      Logger.cueShown(step.step_id, { slot: Pen.slot, size: Pen.size });

      const limit = Number(step.time_limit_ms) || DEFAULT_LIMIT_MS;
      const timer = setTimeout(() => stepDone("timeout"), limit);
      stepDone = (outcome) => {
        if (!stepDone) return;
        stepDone = null;
        clearTimeout(timer);
        Logger.stepEnd(outcome, { slot: Pen.slot, size: Pen.size });
        resolve(outcome);
      };
    });
  }

  async function runBlock(meta, script) {
    Pen.reset();
    Ink.clear();
    resetToolbarPosition();
    Conditions.setup(meta.condition);
    Logger.startBlock({ ...meta, script_id: script.id });
    for (let i = 0; i < script.steps.length && !aborted; i++) {
      await runStep(script.steps[i], i, script.steps.length);
    }
    Ink.locked = true;
    target.innerHTML = "";
    setBanner("", "", false);
    Logger.endBlock();
  }

  // ---------- 세션 ----------

  function assignOrder(participant) {
    const n = Number((participant.match(/\d+/) || ["0"])[0]);
    if (n < 1) return ORDERS[0];
    return ORDERS[Math.floor(((n - 1) % 12) / 2)];
  }

  function csvLine(values) {
    return values.map((v) => {
      const s = v === undefined || v === null ? "" : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    }).join(",");
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
    const browser = (navigator.userAgentData?.brands || [])
      .filter((b) => !/Not.?A.?Brand/i.test(b.brand))
      .map((b) => `${b.brand} ${b.version}`).join(" / ") || navigator.userAgent;
    const sessionCols = ["session_id", "participant", "condition_order", "script_variant", "date", "device",
      "browser", "windows", "screen_w", "screen_h", "dpr", "experimenter", "notes"];
    const sessionRow = [s.session_id, s.participant, s.order.conditions.join("-"), s.order.sets.join("-"),
      new Date().toISOString().slice(0, 10), "", browser, "", window.screen.width, window.screen.height,
      window.devicePixelRatio, s.experimenter, s.aborted ? "세션 중단됨" : ""];
    downloadText(`session_${s.session_id}.csv`, `${csvLine(sessionCols)}\n${csvLine(sessionRow)}\n`);

    const partCols = ["participant", "handedness", "native_language", "note_language", "tablet_note_months"];
    const partRow = [s.participant, s.handedness, "ko", s.note_language, s.tablet_note_months];
    downloadText(`participant_${s.participant}.csv`, `${csvLine(partCols)}\n${csvLine(partRow)}\n`);

    for (const script of s.scripts.values()) downloadText(`script_${script.id}.csv`, script.text);
  }

  async function runSession(s) {
    document.body.classList.add("study");
    Ink.allowEraser = false;
    aborted = false;
    s.scripts = new Map();
    let block = 0;
    try {
      for (let k = 0; k < 3 && !aborted; k++) {
        const condition = s.order.conditions[k];
        const set = s.order.sets[k];
        await showScreen(
          `<p class="screen-step">${k + 1} / 3</p><h1>방법 ${k + 1}</h1>
           <p>${INTRO[condition]}</p><p class="screen-note">진행자: 조건 ${condition}, 제시문 세트 ${set}</p>`,
          [["연습 시작", true]],
        );
        if (aborted) break;
        Conditions.setup(condition);
        const base = { session_id: s.session_id, participant: s.participant, condition, exp: "exp2" };
        if (s.practice) {
          const practice = loadScript("practice");
          s.scripts.set(practice.id, practice);
          await runBlock({ ...base, block: ++block, phase: "practice" }, practice);
          if (aborted) break;
          await showScreen("<h1>연습 끝</h1><p>준비되면 본과제를 시작하세요.</p>", [["본과제 시작", true]]);
          if (aborted) break;
        }
        const main = loadScript(`exp2${set}`);
        s.scripts.set(main.id, main);
        await runBlock({ ...base, block: ++block, phase: "main" }, main);
        if (aborted) break;
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
    saveSessionFiles(s);
    stepDone = null;
    const saved = Logger.savedBlocks().filter((name) => name.includes(`_${s.session_id}_`));
    const list = saved.map((name) => `<li><button class="link" data-name="${escapeHtml(name)}">${escapeHtml(name)}</button></li>`).join("");
    const end = showScreen(
      `<h1>${aborted ? "세션 중단" : "실험 끝"}</h1>
       <p>${aborted ? "" : "마지막 설문과 선호 순위를 진행해 주세요. "}다운로드 폴더의 파일을 팀 드라이브로 옮겨 주세요.</p>
       <p class="screen-note">브라우저에 백업된 블록 (누르면 다시 받기)</p><ul class="saved">${list}</ul>`,
      [["처음 화면", true]],
    );
    overlay.querySelectorAll("button.link").forEach((b) => b.addEventListener("click", (e) => {
      e.stopPropagation();
      Logger.redownload(b.dataset.name);
    }));
    await end;
    document.body.classList.remove("study");
    home();
  }

  function alertScreen(html) {
    return showScreen(`<h1>문제가 생겼어요</h1><p>${html}</p>`, [["확인", true]]);
  }

  // ---------- 처음 화면 ----------

  function home() {
    session = null;
    Ink.locked = true;
    Ink.allowEraser = true;
    document.body.classList.remove("study", "free");
    target.innerHTML = "";
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
      const valid = conditions.length === 3 && new Set(conditions).size === 3 && conditions.every((c) => /^C[123]$/.test(c))
        && sets.length === 3 && sets.every((v) => /^[ABC]$/.test(v));
      const participant = f.participant.value.trim().toUpperCase();
      if (!valid || !/^[A-Z]+\d+$/.test(participant)) {
        form.querySelector(".form-error").textContent = "참가자 번호(P01), 조건 순서(C1-C2-C3), 세트(A-B-C)를 확인해 주세요.";
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

    overlay.querySelectorAll("[data-free]").forEach((button) => button.addEventListener("click", () => {
      startFree(button.dataset.free);
    }));
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
    if (stepDone) stepDone("completed");
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
