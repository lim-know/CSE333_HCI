"""분석 코드 테스트용 가짜 데이터를 만든다. 실제 실험 결과가 아니다. 로그 형식 v1.2 (제시문형 과제).

같은 시드로 항상 같은 파일이 나온다. 로그 형식이나 판정 규칙을 바꾸면 다시 실행한다.
브라우저(prototype2 f140813)가 남기는 이벤트 순서를 흉내 낸다:
- 툴바: 펜 pointerdown(source=ui) → slot_change(toolbar) → toolbar_tap
- 슬라이더: 펜 pointerdown(ui) → slider_start → size_change(slider) → slider_end
- C2·C3 제스처: 손가락 pointerdown → (C3: slot_change(gesture)) → rec_state ARMED → 펜 pointerdown
  → activation → rec_state TUNING → size_change(gesture) → 펜 pointerup → gesture_commit → … → rec_state IDLE
- 지금 단계의 펜·굵기로 그은 획이 끝나면 step_end(completed) → 다음 단계 cue_shown.
  마지막 단계는 완료 버튼(펜 탭, source=ui)을 누를 때 step_end.
- 연습 블록 단계표는 브라우저가 저장하지 않으므로 여기서도 만들지 않는다.

크기를 줄이려고 조건당 본과제 제시문은 2개(실제 5개), 참가자는 4명(P01~P04)이다.
그래서 validate_log 가 "본과제 제시문 2개 (기대 5개)" 주의를 띄우는 것이 정상이다.

일부러 넣은 사례 (tests/test_pipeline.py 가 확인한다):
- P01 C3 exp2C_0 02: 손가락 수를 틀려(2개) 빨간 펜으로 먼저 쓰고 고침 → 오답 획(펜) 1, 첫 시도 오답
- P01 C3 exp2C_0 04: 손가락이 움직여 인식 실패 → 본문 상태 획(인식 실패 후보 1) 후 재시도
- P01 C2 exp2B_0 01: 블록 시작에 굵기를 바꾸지 않은 제스처(no_change) 후 본문을 씀 (11/20 파일럿 사례)
- P02 C3 exp2C_0 01: 옷자락처럼 손가락이 닿아 슬롯만 바뀜(펜 없음) → 되돌리고 본문을 이어 씀 (penless)
- P02 C1 exp2A_1 03: 표시를 남긴 채 완료를 누름 → 진행 중 단계 skipped(participant), 나머지 not_reached
- P03 C2 exp2C_0 03: 진행자가 건너뜀(Ctrl+Shift+S) → skipped(experimenter)
- P03 C1 exp2A_0 01: 펜 옆 버튼으로 지우개 사용
- P04 C2 exp2C_1 02: 터치 pointercancel
- 모든 참가자의 *_1 제시문 01 단계: 블록 맨 앞이 표시라 앞선 본문 획이 없음 → prev_ink_fallback
"""
from __future__ import annotations

import csv
import math
import random
import sys
from pathlib import Path

from logdata import (
    EVENT_COLUMNS, PARTICIPANT_COLUMNS, QUESTIONNAIRE_COLUMNS, SCHEMA_VERSION, SCRIPT_COLUMNS,
    SESSION_COLUMNS, TLX_ITEMS,
)

SEED = 333
DEFAULT_SIZES = {1: 1.0, 2: 1.0, 3: 4.0}   # script.js DEFAULT_SIZES (블록 시작 때 슬롯별 굵기)
BASE = (1, 1.0)
DONE_BUTTON = (1200.0, 40.0)
# 조건별 조작 시간 배율 (가짜 값). C3가 펜+굵기에서 빠르고, 굵기만은 C2≈C3 가 되도록 둔다.
SPEED = {"C1": {"switch": 1.0, "size": 1.0}, "C2": {"switch": 1.0, "size": 0.75},
         "C3": {"switch": 0.6, "size": 0.75}}
# 첫 조작에서 굵기를 한 칸 빗나갈 확률 (가짜 값). 빗나가면 틀린 굵기로 한 획 긋고 다시 맞춘다.
OVERSHOOT = {"C1": 0.10, "C2": 0.20, "C3": 0.25}
PARTICIPANTS = ["P01", "P02", "P03", "P04"]
ORDERS = {"P01": ("C1-C2-C3", "A-B-C"), "P02": ("C1-C2-C3", "A-B-C"),
          "P03": ("C1-C3-C2", "A-B-C"), "P04": ("C1-C3-C2", "A-B-C")}

# 제시문: (표시 종류, 슬롯, 굵기, 뒤에 본문이 이어지는지). 세트 A·B·C 는 같은 구조 (실제 제시문과 같은 방식).
# 0번: 본문으로 시작. 1번: 표시로 시작 (앞선 본문 획이 없는 경우).
PASSAGES = [
    [("word", 1, 4.0, True), ("underline", 2, 2.0, True), ("word", 1, 2.0, True), ("highlight", 3, 8.0, True)],
    [("word", 2, 2.0, True), ("circle", 1, 4.0, True), ("highlight", 3, 4.0, False)],
]
PRACTICE = [("word", 1, 4.0, True), ("underline", 2, 2.0, False)]
MARK_LABEL = {"underline": "밑줄", "circle": "동그라미", "highlight": "칠하기", "word": "글씨"}
PEN_LABEL = {1: "검정", 2: "빨강", 3: "형광펜"}


def passage_steps(marks: list[tuple]) -> list[dict]:
    """passage.js steps() 와 같은 규칙: 글씨 표시(+본문 복귀)를 먼저, 밑줄·동그라미·칠하기는 나중에."""
    sizes = dict(DEFAULT_SIZES)
    slot = BASE[0]
    out = []

    def require(want_slot, want_size, task_type):
        nonlocal slot
        same_slot = want_slot == slot
        if same_slot and sizes[slot] == want_size:
            raise ValueError("바꿀 게 없는 단계")
        kind = "size_only" if same_slot else ("switch_only" if sizes[want_slot] == want_size else "switch_size")
        slot = want_slot
        sizes[slot] = want_size
        out.append({"task_type": task_type, "step_type": kind, "slot": want_slot, "size": want_size})

    words = [m for m in marks if m[0] == "word"]
    others = [m for m in marks if m[0] != "word"]
    for mark, s, z, text_after in words:
        require(s, z, mark)
        if text_after:
            require(BASE[0], BASE[1], "return")
    for mark, s, z, _ in others:
        require(s, z, mark)
    for i, step in enumerate(out):
        step["step_id"] = f"{i + 1:02d}"
        label = f"{PEN_LABEL[step['slot']]} {step['size']:g}pt"
        step["cue_text"] = f"본문 {label}" if step["task_type"] == "return" else f"{label} {MARK_LABEL[step['task_type']]}"
    return out


def script_rows(script_id: str, steps: list[dict]) -> list[dict]:
    return [{
        "script_id": script_id, "step_id": s["step_id"], "exp": "exp2", "step_type": s["step_type"],
        "task_type": s["task_type"], "language": "ko", "cue_text": s["cue_text"],
        "target_slot": s["slot"], "target_size": f"{s['size']:g}", "on_preset": 1,
        "target_x": "", "target_y": "", "text": "가짜", "time_limit_ms": "",   # 시간 제한 없음 (11/26 결정)
    } for s in steps]


class BlockLog:
    """브라우저 로거가 남길 행을 흉내 낸다. 펜 상태(슬롯별 굵기 기억)도 브라우저처럼 따라간다."""

    def __init__(self, meta: dict, rng: random.Random, condition: str, person: float):
        self.meta, self.rng, self.condition, self.person = meta, rng, condition, person
        self.rows: list[dict] = []
        self.seq = 0
        self.t = 1000.0
        self.slot = BASE[0]
        self.sizes = dict(DEFAULT_SIZES)
        self.step_id = ""
        self.rec = "IDLE"

    @property
    def size(self) -> float:
        return self.sizes[self.slot]

    def wait(self, ms: float) -> None:
        self.t += ms * self.person * math.exp(self.rng.gauss(0, 0.15))

    def emit(self, event: str, **fields) -> None:
        self.seq += 1
        self.t += self.rng.uniform(0.5, 3.0)
        row = dict.fromkeys(EVENT_COLUMNS, "")
        row.update(self.meta)
        row.update(schema_version=SCHEMA_VERSION, step_id=self.step_id, seq=self.seq,
                   t_event=round(self.t, 1), t_logged=round(self.t + self.rng.uniform(0.2, 2.0), 1), event=event)
        row.update(fields)
        self.rows.append(row)

    def pointer(self, event, kind, pid, x, y, source="canvas", buttons=None, **fields):
        width = 1 if kind == "pen" else 30
        if buttons is None:
            buttons = 0 if event == "pointerup" else 1
        self.emit(event, source=source if event != "pointermove" else "", pointer_id=pid, pointer_type=kind,
                  x=round(x, 1), y=round(y, 1), width=width, height=width, buttons=buttons, **fields)

    def rec_state(self, state: str) -> None:
        self.rec = state
        self.emit("rec_state", source="gesture", rec_state=state, slot=self.slot, size=self.size)

    # ----- 필기 -----

    def ink(self, n_touch=0, n_still=0) -> tuple[int, float]:
        self.wait(120)
        self.pointer("pointerdown", "pen", 1, 400, 300, n_touch=n_touch, n_still=n_still)
        self.emit("ink_start", source="pen", slot=self.slot, size=self.size)
        state = (self.slot, self.size)
        self.wait(90)
        self.pointer("pointermove", "pen", 1, 420, 300)
        self.wait(90)
        self.pointer("pointerup", "pen", 1, 440, 300)
        self.emit("ink_end", source="pen", slot=state[0], size=state[1])
        return state

    def body(self, strokes: int) -> None:
        for _ in range(strokes):
            self.ink()

    def eraser(self) -> None:
        self.wait(200)
        self.pointer("pointerdown", "pen", 1, 400, 300, buttons=33, n_touch=0, n_still=0)
        self.wait(150)
        self.pointer("pointerup", "pen", 1, 400, 300, buttons=0)

    def done_tap(self) -> None:
        self.wait(400)
        self.pointer("pointerdown", "pen", 1, *DONE_BUTTON, source="ui", n_touch=0, n_still=0)
        self.pointer("pointerup", "pen", 1, *DONE_BUTTON, source="ui")

    # ----- 조작 -----

    def toolbar(self, slot: int) -> None:
        self.wait(700 * SPEED[self.condition]["switch"])
        self.pointer("pointerdown", "pen", 1, 80 + 60 * slot, 40, source="ui", n_touch=0, n_still=0)
        self.pointer("pointerup", "pen", 1, 80 + 60 * slot, 40, source="ui")
        self.slot = slot
        self.emit("slot_change", source="toolbar", slot=self.slot, size=self.size)
        self.emit("toolbar_tap", source="toolbar", slot=self.slot, size=self.size)

    def slider(self, size: float) -> None:
        self.wait(800 * SPEED[self.condition]["size"])
        self.pointer("pointerdown", "pen", 1, 300, 40, source="ui", n_touch=0, n_still=0)
        self.emit("slider_start", source="slider", slot=self.slot, size=self.size)
        self.wait(700)
        self.sizes[self.slot] = size
        self.emit("size_change", source="slider", slot=self.slot, size=size)
        self.pointer("pointerup", "pen", 1, 320, 40, source="ui")
        self.emit("slider_end", source="slider", slot=self.slot, size=self.size)

    def fingers_down(self, n: int, count_mode: bool) -> list[int]:
        """손가락 n개를 올리고 정지 판정(120ms)까지. C3(count_mode)는 이때 손가락 수로 슬롯이 바뀐다."""
        ids = [10 + i for i in range(n)]
        self.wait(500 * SPEED[self.condition]["switch"])
        for pid in ids:
            self.pointer("pointerdown", "touch", pid, 900 + 40 * pid, 500)
        self.wait(130)
        if count_mode and n != self.slot:
            self.slot = n
            self.emit("slot_change", source="gesture", slot=self.slot, size=self.size)
        self.rec_state("ARMED")
        return ids

    def fingers_up(self, ids: list[int]) -> None:
        self.wait(120)
        for pid in ids:
            self.pointer("pointerup", "touch", pid, 900 + 40 * pid, 500)
        self.rec_state("IDLE")

    def tune(self, n_touch: int, size: float | None) -> None:
        """손가락이 정지한 채 펜 다운 → (끌기) → 펜 업. size 가 None 이면 끌지 않는다 (no_change)."""
        self.wait(250)
        self.pointer("pointerdown", "pen", 1, 400, 300, n_touch=n_touch, n_still=n_touch)
        self.emit("activation", source="gesture", slot=self.slot, size=self.size, rec_state="ARMED",
                  n_touch=n_touch, n_still=n_touch)   # PR #11 0cf62ef: activation 의 n_still = 닿은 손가락 수
        self.rec_state("TUNING")
        self.wait(600 * SPEED[self.condition]["size"])
        if size is not None and size != self.size:
            self.pointer("pointermove", "pen", 1, 400 + 40 * size, 300)
            self.sizes[self.slot] = size
            self.emit("size_change", source="gesture", slot=self.slot, size=size)
        self.pointer("pointerup", "pen", 1, 400 + 40 * (size or 0), 300)
        self.emit("gesture_commit", source="gesture", slot=self.slot, size=self.size)
        self.rec_state("ARMED")

    def gesture(self, fingers: int, size: float | None) -> None:
        count_mode = self.condition == "C3"
        ids = self.fingers_down(fingers, count_mode)
        if size is not None and size != self.size:
            self.tune(fingers, size)
        elif not count_mode:
            self.tune(fingers, None)
        self.fingers_up(ids)

    def switch(self, slot: int, size: float) -> None:
        """조건에 맞는 방법으로 목표 상태로 바꾼다. 굵기는 가끔 한 칸 빗나가서 다시 맞춘다."""
        current = self.sizes[slot]
        if size != current and self.rng.random() < OVERSHOOT[self.condition]:
            # 목표와도, 지금 굵기와도 다른 한 칸 옆 값 (지금 굵기면 본문 획과 구분이 안 된다)
            miss = next(m for m in (size + 1.0, size - 1.0, size + 2.0) if 1 <= m <= 8 and m != current)
            self._switch(slot, miss)
            self.ink()                                 # 틀린 굵기로 그은 획 (오답 획, 첫 시도 오차)
        self._switch(slot, size)

    def _switch(self, slot: int, size: float) -> None:
        if self.condition == "C1":
            if slot != self.slot:
                self.toolbar(slot)
            if size != self.size:
                self.slider(size)
        elif self.condition == "C2":
            if slot != self.slot:
                self.toolbar(slot)
            if size != self.size:
                self.gesture(1, size)
        else:
            self.gesture(slot, size)


def run_block(meta: dict, steps: list[dict], rng: random.Random, condition: str, person: float,
              case: dict) -> list[dict]:
    log = BlockLog(meta, rng, condition, person)
    log.emit("block_start", detail="build=sample;still_px=12;still_ms=120;touch_to_pen_ms=none;palm_px=0;"
                                   f"snap_px=8;track_px=320;epoch_ms={1795000000000 + 1000 * meta['block']}")
    prev = BASE
    for index, step in enumerate(steps):
        target = (step["slot"], step["size"])
        log.step_id = step["step_id"]
        log.emit("cue_shown", slot=log.slot, size=log.size)
        sid = step["step_id"]
        if case.get("eraser") == sid:
            log.eraser()
        if case.get("no_change") == sid:
            log.gesture(1, None)                       # 굵기를 안 바꾼 제스처
        if case.get("penless") == sid:
            ids = log.fingers_down(3, True)            # 옷자락: 슬롯 3으로 바뀜, 펜 없이 뗌
            log.fingers_up(ids)
            log.gesture(1, None)                       # 손가락 1개로 검정으로 되돌림
        # 표시 앞의 본문: 블록 첫 표시가 맨 앞이면 없음, 본문 복귀 단계는 표시 단어를 마저 쓰는 획 1개
        if index == 0 and case.get("starts_with_mark"):
            n_body = 0
        elif step["task_type"] == "return":
            n_body = 1
        elif prev == BASE:
            n_body = 3
        else:
            n_body = 0
        log.body(n_body)
        if case.get("early_done") == sid:
            # 표시를 남긴 채 완료: 진행 중 단계 skipped, 바로 block_end
            log.done_tap()
            log.emit("step_end", slot=log.slot, size=log.size, detail="outcome=skipped")
            log.step_id = ""
            log.emit("block_end")
            return log.rows
        if case.get("experimenter_skip") == sid:
            log.wait(3000)
            log.emit("step_end", slot=log.slot, size=log.size, detail="outcome=skipped")
            prev = (log.slot, log.size)
            continue
        if case.get("wrong_fingers") == sid:
            log.gesture(2, None)                       # 2개 → 빨간 펜
            log.ink()                                  # 오답 획
        if case.get("missed") == sid:
            log.wait(400)
            log.pointer("pointerdown", "touch", 20, 950, 500)
            log.pointer("pointermove", "touch", 20, 980, 500)   # 손가락이 움직여 정지가 아님
            log.ink(n_touch=1, n_still=0)              # 본문 상태 획 (인식 실패 후보)
            log.pointer("pointerup", "touch", 20, 980, 500)
        if case.get("cancel") == sid:
            log.pointer("pointerdown", "touch", 21, 950, 520)
            log.pointer("pointercancel", "touch", 21, 950, 520)
        log.switch(*target)
        log.ink()                                      # 정답 획 → 다음 단계
        prev = target
        if index + 1 < len(steps):
            log.emit("step_end", slot=log.slot, size=log.size, detail="outcome=completed")
        else:
            log.ink()                                  # 표시를 마저 칠하고
            log.done_tap()
            log.emit("step_end", slot=log.slot, size=log.size, detail="outcome=completed")
    log.step_id = ""
    log.emit("block_end")
    return log.rows


CASES = {
    ("P01", "C3", "exp2C_0"): {"wrong_fingers": "02", "missed": "04"},
    ("P01", "C2", "exp2B_0"): {"no_change": "01"},
    ("P02", "C3", "exp2C_0"): {"penless": "01"},
    ("P02", "C1", "exp2A_1"): {"early_done": "03"},
    ("P03", "C2", "exp2C_0"): {"experimenter_skip": "03"},
    ("P03", "C1", "exp2A_0"): {"eraser": "01"},
    ("P04", "C2", "exp2C_1"): {"cancel": "02"},
}


def _write(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(out: str) -> None:
    root = Path(out)
    rng = random.Random(SEED)
    scripts = {}
    for variant in "ABC":
        for i, marks in enumerate(PASSAGES):
            script_id = f"exp2{variant}_{i}"
            scripts[script_id] = passage_steps(marks)
            _write(root / "scripts" / f"script_{script_id}.csv", SCRIPT_COLUMNS,
                   script_rows(script_id, scripts[script_id]))
    practice_steps = passage_steps(PRACTICE)

    sessions, participants, questionnaire = [], [], []
    for participant in PARTICIPANTS:
        session_id = f"{participant}-1"
        order, variants = ORDERS[participant]
        conditions, sets = order.split("-"), variants.split("-")
        person = math.exp(rng.gauss(0, 0.2))           # 사람마다 빠르기 차이
        sessions.append({
            "session_id": session_id, "participant": participant, "condition_order": order,
            "script_variant": variants, "date": "2000-01-01", "device": "FAKE", "browser": "FAKE",
            "windows": "FAKE", "screen_w": 2880, "screen_h": 1800, "dpr": 2, "experimenter": "FAKE",
            "notes": "가짜 데이터",
        })
        participants.append({"participant": participant, "handedness": "right", "native_language": "ko",
                             "note_language": "mixed", "tablet_note_months": 24})
        block_no = 0
        for condition, variant in zip(conditions, sets):
            blocks = [("practice", "practice", practice_steps)]
            blocks += [("main", f"exp2{variant}_{i}", scripts[f"exp2{variant}_{i}"]) for i in range(len(PASSAGES))]
            for phase, script_id, steps in blocks:
                block_no += 1
                meta = {"session_id": session_id, "participant": participant, "block": block_no,
                        "condition": condition, "phase": phase, "exp": "exp2", "script_id": script_id}
                case = dict(CASES.get((participant, condition, script_id), {}))
                if script_id.endswith("_1"):
                    case["starts_with_mark"] = True
                rows = run_block(meta, steps, rng, condition, person, case)
                _write(root / "events" / f"events_{session_id}_b{block_no:02d}.csv", EVENT_COLUMNS, rows)
            # 조건이 끝날 때 NASA-TLX (0~100, 5점 단위). C3가 조금 낮게 나오도록 한 가짜 값
            shift = {"C1": 10, "C2": 5, "C3": 0}[condition]
            for item in TLX_ITEMS:
                questionnaire.append({"participant": participant, "condition": condition, "item": item,
                                      "value": min(100, rng.randrange(10, 70, 5) + shift)})
        ranks = {"C3": 1, "C2": 2, "C1": 3} if participant != "P04" else {"C2": 1, "C3": 2, "C1": 3}
        for condition, rank in ranks.items():
            questionnaire.append({"participant": participant, "condition": condition,
                                  "item": "preference_rank", "value": rank})

    _write(root / "sessions.csv", SESSION_COLUMNS, sessions)
    _write(root / "participants.csv", PARTICIPANT_COLUMNS, participants)
    _write(root / "questionnaire.csv", QUESTIONNAIRE_COLUMNS, questionnaire)


if __name__ == "__main__":
    default = Path(__file__).resolve().parent.parent / "data" / "sample"
    target = sys.argv[1] if len(sys.argv) > 1 else str(default)
    main(target)
    print(f"가짜 데이터 생성 완료: {target}")
