"""분석 코드 테스트용 가짜 데이터를 만든다. 실제 실험 결과가 아니다.

같은 시드로 항상 같은 파일이 나온다. 로그 형식을 바꾸면 다시 실행한다.

사용법:
    python make_sample_data.py [출력 폴더, 기본값 ../data/sample]

일부러 넣은 사례:
- P00 C3 exp2 s03: 잘못된 슬롯으로 먼저 쓰고 수정
- P00 C3 exp2 s04(copy): 슬롯은 그대로인데 획이 굵기 조절로 먹힌 오작동
- P00 C3 exp2 s05: 손가락이 움직여 인식 실패(후보) 후 재시도
- P01 C3 exp2 s05: 시간 초과로 끝내 못 맞춤
- P01 C2 exp2 s02: 터치 pointercancel
"""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

from logdata import (
    EVENT_COLUMNS, PARTICIPANT_COLUMNS, QUESTIONNAIRE_COLUMNS, SCHEMA_VERSION,
    SCRIPT_COLUMNS, SESSION_COLUMNS,
)

SEED = 333
COPY_STROKES = {"ko": 14, "en": 8}   # 형식 테스트용 임의 값, 실측치 아님
SPEED = {"C1": 1.0, "C2": 0.9, "C3": 0.75}


def _step(step_id, exp, step_type, task_type, slot, size, language="", text="", on_preset=""):
    cue = {1: "검은 펜", 2: "노란 형광펜", 3: "빨간 펜"}.get(slot, "지금 펜")
    if step_type == "copy":
        cue_text = "아래 문장을 따라 쓰세요"
    else:
        cue_text = f"{cue} {size}pt" if size != "" else cue
    return {
        "step_id": step_id, "exp": exp, "step_type": step_type, "task_type": task_type,
        "language": language, "cue_text": cue_text, "target_slot": slot, "target_size": size,
        "on_preset": on_preset, "target_x": 400 if step_type != "copy" else "",
        "target_y": 300 if step_type != "copy" else "", "text": text,
    }


def _exp2_steps(words: tuple[str, str]) -> list[dict]:
    return [
        _step("s01", "exp2", "switch_only", "underline", 2, ""),
        _step("s02", "exp2", "size_only", "underline", "", 2.0, on_preset=1),
        _step("s03", "exp2", "switch_size", "circle", 3, 2.0, on_preset=1),
        _step("s04", "exp2", "copy", "copy", "", "", language="ko", text=words[0]),
        _step("s05", "exp2", "switch_size", "highlight", 2, 4.0, on_preset=1),
        _step("s06", "exp2", "copy", "copy", "", "", language="en", text=words[1]),
    ]


def make_scripts() -> dict[str, list[dict]]:
    return {
        "practice": [
            _step("p01", "exp2", "switch_only", "underline", 2, ""),
            _step("p02", "exp2", "switch_size", "circle", 3, 1.0, on_preset=1),
        ],
        "exp1": [
            _step("m01", "exp1", "size_only", "line", "", 2.0, on_preset=1),
            _step("m02", "exp1", "size_only", "line", "", 3.0, on_preset=0),
            _step("m03", "exp1", "size_only", "line", "", 6.0, on_preset=0),
        ],
        "exp2A": _exp2_steps(("가설 검정", "sample data")),
        "exp2B": _exp2_steps(("표본 평균", "test result")),
        "exp2C": _exp2_steps(("실험 설계", "main effect")),
    }


class BlockLog:
    """브라우저 로거가 남길 행을 흉내 낸다."""

    def __init__(self, meta: dict, rng: random.Random, speed: float):
        self.meta, self.rng, self.speed = meta, rng, speed
        self.rows: list[dict] = []
        self.seq = 0
        self.t = 1000.0
        self.slot, self.size = 1, 1.0
        self.step_id = ""

    def wait(self, ms: float) -> None:
        self.t += ms * self.speed * self.rng.uniform(0.8, 1.2)

    def emit(self, event: str, **fields) -> None:
        self.seq += 1
        self.t += self.rng.uniform(1.0, 9.0)
        row = dict.fromkeys(EVENT_COLUMNS, "")
        row.update(self.meta)
        row.update(schema_version=SCHEMA_VERSION, step_id=self.step_id, seq=self.seq,
                   t_event=round(self.t, 1), t_logged=round(self.t + self.rng.uniform(0.2, 2.5), 1),
                   event=event)
        row.update(fields)
        self.rows.append(row)

    def pointer(self, event: str, kind: str, pid: int, x: float, y: float, **fields) -> None:
        size = 1 if kind == "pen" else 30
        self.emit(event, pointer_id=pid, pointer_type=kind, x=round(x, 1), y=round(y, 1),
                  width=size, height=size, buttons=int(event != "pointerup"), **fields)

    def ink(self, moves: int = 2) -> None:
        self.pointer("pointerdown", "pen", 1, 400, 300, n_touch=0, n_still=0)
        self.emit("ink_start", source="pen", slot=self.slot, size=self.size)
        for i in range(moves):
            self.wait(40)
            self.pointer("pointermove", "pen", 1, 400 + 15 * (i + 1), 300)
        self.pointer("pointerup", "pen", 1, 400 + 15 * moves, 300)
        self.emit("ink_end", source="pen", slot=self.slot, size=self.size)

    def toolbar(self, slot: int) -> None:
        self.wait(450)
        self.pointer("pointerdown", "pen", 1, 80 + 60 * slot, 40, n_touch=0, n_still=0)
        self.pointer("pointerup", "pen", 1, 80 + 60 * slot, 40)
        self.emit("toolbar_tap", source="toolbar", slot=slot, size=self.size)
        self.slot = slot
        self.emit("slot_change", source="toolbar", slot=slot, size=self.size)

    def slider(self, size: float) -> None:
        self.wait(400)
        self.emit("slider_start", source="slider", slot=self.slot, size=self.size)
        self.wait(600)
        self.size = size
        self.emit("size_change", source="slider", slot=self.slot, size=size)
        self.emit("slider_end", source="slider", slot=self.slot, size=size)

    def gesture(self, fingers: int, slot: int | None, size: float | None, fingers_moved: bool = False) -> None:
        """손가락을 올리고 펜 다운. slot/size 가 None 이면 그 값은 바꾸지 않는다."""
        ids = [10 + i for i in range(fingers)]
        for pid in ids:
            self.pointer("pointerdown", "touch", pid, 900 + 40 * pid, 500)
        self.wait(200)
        if fingers_moved:
            for pid in ids:
                self.pointer("pointermove", "touch", pid, 900 + 40 * pid + 25, 500)
        n_still = 0 if fingers_moved else fingers
        self.pointer("pointerdown", "pen", 1, 400, 300, n_touch=fingers, n_still=n_still)
        if fingers_moved:
            self.emit("ink_start", source="pen", slot=self.slot, size=self.size)
            self.pointer("pointerup", "pen", 1, 410, 300)
            self.emit("ink_end", source="pen", slot=self.slot, size=self.size)
        else:
            self.emit("activation", source="gesture", slot=self.slot, size=self.size,
                      rec_state="ARMED", n_touch=fingers, n_still=n_still)
            if slot is not None and slot != self.slot:
                self.slot = slot
                self.emit("slot_change", source="gesture", slot=slot, size=self.size)
            self.emit("rec_state", rec_state="TUNING", source="gesture", slot=self.slot, size=self.size)
            self.wait(300)
            self.pointer("pointermove", "pen", 1, 430, 300)
            if size is not None and size != self.size:
                self.size = size
                self.emit("size_change", source="gesture", slot=self.slot, size=size)
            self.pointer("pointerup", "pen", 1, 430, 300)
            self.emit("gesture_commit", source="gesture", slot=self.slot, size=self.size)
            self.emit("rec_state", rec_state="IDLE", source="gesture", slot=self.slot, size=self.size)
        for pid in ids:
            self.pointer("pointerup", "touch", pid, 900 + 40 * pid, 500)

    def switch(self, condition: str, slot: int | None, size: float | None) -> None:
        if condition == "C1":
            if slot is not None:
                self.toolbar(slot)
            if size is not None:
                self.slider(size)
        elif condition == "C2":
            if slot is not None:
                self.toolbar(slot)
            if size is not None:
                self.gesture(1, None, size)
        else:
            self.gesture(slot if slot is not None else self.slot, slot, size)


def _number(value) -> float | None:
    return None if value == "" else float(value)


def _run_step(log: BlockLog, condition: str, spec: dict, participant: str) -> None:
    log.step_id = spec["step_id"]
    log.emit("cue_shown", slot=log.slot, size=log.size, detail=f"text_len={len(spec['cue_text'])}")
    log.wait(500)
    case = (participant, condition, spec["exp"], spec["step_id"])
    outcome = "completed"

    if spec["step_type"] == "copy":
        if case == ("P00", "C3", "exp2", "s04"):
            log.gesture(log.slot, None, None)   # 손이 닿아 획이 굵기 조절로 먹힘, 슬롯 변화 없음
        for _ in range(COPY_STROKES[spec["language"]]):
            log.ink(moves=1)
            log.wait(120)
    else:
        slot, size = _number(spec["target_slot"]), _number(spec["target_size"])
        slot = int(slot) if slot is not None else None
        if case == ("P00", "C3", "exp2", "s03"):
            log.gesture(2, 2, None)
            log.wait(150)
            log.ink()
            log.wait(600)
        if case == ("P00", "C3", "exp2", "s05"):
            log.gesture(slot, None, None, fingers_moved=True)
            log.wait(400)
        if case == ("P01", "C2", "exp2", "s02"):
            log.pointer("pointerdown", "touch", 20, 900, 500)
            log.pointer("pointercancel", "touch", 20, 900, 500)
        if case == ("P01", "C3", "exp2", "s05"):
            log.gesture(1, 1, None)
            log.wait(300)
            log.ink()
            log.wait(9000)
            outcome = "timeout"
        else:
            log.switch(condition, slot, size)
            log.wait(250)
            log.ink()
    log.wait(150)
    log.emit("step_end", slot=log.slot, size=log.size, detail=f"outcome={outcome}")
    log.step_id = ""
    log.wait(300)


def _run_block(participant, session_id, block_no, condition, phase, script_id, steps, rng, order):
    exp = steps[0]["exp"]
    meta = {"session_id": session_id, "participant": participant, "block": block_no,
            "condition": condition, "phase": phase, "exp": exp, "script_id": script_id}
    log = BlockLog(meta, rng, SPEED[condition])
    log.emit("block_start", detail=f"build=sample;still_px=12;still_ms=120;epoch_ms={1793000000000 + block_no};order={order}")
    for spec in steps:
        _run_step(log, condition, spec, participant)
    log.emit("block_end")
    return log.rows


def _write(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(out: str) -> None:
    root = Path(out)
    rng = random.Random(SEED)
    scripts = make_scripts()
    for script_id, steps in scripts.items():
        _write(root / "scripts" / f"script_{script_id}.csv", SCRIPT_COLUMNS,
               [{**step, "script_id": script_id} for step in steps])

    runs = [("P00", "P00-1", ["C1", "C2", "C3"], "A"), ("P01", "P01-1", ["C3", "C1", "C2"], "B")]
    form_of = {"C1": "exp2A", "C2": "exp2B", "C3": "exp2C"}
    sessions, participants, questionnaire = [], [], []
    for participant, session_id, order, variant in runs:
        sessions.append({
            "session_id": session_id, "participant": participant,
            "condition_order": "-".join(order), "script_variant": variant, "date": "2000-01-01",
            "device": "FAKE", "browser": "FAKE", "windows": "FAKE", "screen_w": 2560,
            "screen_h": 1600, "dpr": 1.5, "experimenter": "FAKE", "notes": "가짜 데이터",
        })
        participants.append({
            "participant": participant, "handedness": "right", "native_language": "ko",
            "note_language": "mixed", "english_proficiency": 3, "tablet_note_months": 24,
        })
        block_no = 0
        for condition in order:
            for phase, script_id in (("practice", "practice"), ("main", "exp1"), ("main", form_of[condition])):
                block_no += 1
                rows = _run_block(participant, session_id, block_no, condition, phase, script_id,
                                  scripts[script_id], rng, "-".join(order))
                _write(root / "events" / f"events_{session_id}_b{block_no:02d}.csv", EVENT_COLUMNS, rows)
            for item in ("tlx_mental", "tlx_physical", "tlx_temporal", "tlx_performance", "tlx_effort", "tlx_frustration"):
                questionnaire.append({"participant": participant, "condition": condition,
                                      "item": item, "value": rng.randrange(10, 90, 5)})
            questionnaire.append({"participant": participant, "condition": condition,
                                  "item": "preference_rank", "value": order.index(condition) + 1})

    _write(root / "sessions.csv", SESSION_COLUMNS, sessions)
    _write(root / "participants.csv", PARTICIPANT_COLUMNS, participants)
    _write(root / "questionnaire.csv", QUESTIONNAIRE_COLUMNS, questionnaire)


if __name__ == "__main__":
    default = Path(__file__).resolve().parent.parent / "data" / "sample"
    target = sys.argv[1] if len(sys.argv) > 1 else str(default)
    main(target)
    print(f"가짜 데이터 생성 완료: {target}")
