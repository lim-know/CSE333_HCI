"""로그 형식 정의와 불러오기 (docs/log-schema.md 와 항상 같이 고친다).

v1.2 (제시문형 과제) 기준. 열(컬럼)은 v1.1과 같고 값의 뜻과 규칙만 바뀌었다.
브라우저 로거(prototype/js/logger.js)는 열이 그대로라 schema_version 에 "1.1"을 계속 쓴다.
그래서 버전 구분은 schema_version 이 아니라 block_start 의 build 값으로 한다 (KNOWN_BUILDS).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# logger.js 가 쓰는 값. 열 구성이 바뀔 때만 올린다 (값의 뜻이 바뀐 v1.2도 열은 같아서 1.1).
SCHEMA_VERSION = "1.1"
ACCEPTED_SCHEMA_VERSIONS = {"1.1", "1.2"}   # 나중에 로거가 1.2로 올려도 읽히게

# 코드 버전(block_start detail 의 build) → 설명. 새 build 가 나오면 여기와 log-schema.md 표를 같이 고친다.
KNOWN_BUILDS = {
    "exp-2026-11-18": "PR #10 / PR #11 초기 (11/20 파일럿). 단계별 60초 제한 있음",
    "exp-2026-11-21": "PR #11 f140813: 블록마다 저장, script 저장, 완료를 일찍 누르면 skipped. 60초 제한 있음",
    "exp-2026-11-28": "PR #11 515b823: 단계 = 할 일 단위. 본문도 return 단계, 블록 첫 본문은 no_change. 60초 제한 아직 있음",
    "exp-2026-11-29": "fix/no-time-limit f941f1b (515b823 + 시간 제한 없앰, 디버그 로그 정리). 본실험용",
    "sample": "make_sample_data.py 가짜 데이터",
}

EVENT_COLUMNS = [
    "schema_version", "session_id", "participant", "block", "condition", "phase",
    "exp", "script_id", "step_id", "seq", "t_event", "t_logged", "event", "source",
    "pointer_id", "pointer_type", "x", "y", "width", "height", "buttons",
    "slot", "size", "rec_state", "n_touch", "n_still", "detail",
]
SCRIPT_COLUMNS = [
    "script_id", "step_id", "exp", "step_type", "task_type", "language", "cue_text",
    "target_slot", "target_size", "on_preset", "target_x", "target_y", "text",
    "time_limit_ms",
]
# 시간 제한은 11/26 팀 결정으로 없앨 예정이라, 열이 빠지거나 비어도 읽는다.
OPTIONAL_SCRIPT_COLUMNS = {"time_limit_ms"}
SESSION_COLUMNS = [
    "session_id", "participant", "condition_order", "script_variant", "date",
    "device", "browser", "windows", "screen_w", "screen_h", "dpr", "experimenter", "notes",
]
PARTICIPANT_COLUMNS = [
    "participant", "handedness", "native_language", "note_language", "tablet_note_months",
]
QUESTIONNAIRE_COLUMNS = ["participant", "condition", "item", "value"]
TLX_ITEMS = ["tlx_mental", "tlx_physical", "tlx_temporal", "tlx_performance", "tlx_effort", "tlx_frustration"]
PREFERENCE_ITEM = "preference_rank"

POINTER_EVENTS = {"pointerdown", "pointermove", "pointerup", "pointercancel"}
APP_EVENTS = {
    "block_start", "block_end", "cue_shown", "step_end", "toolbar_tap", "slider_start",
    "slider_end", "slot_change", "size_change", "activation", "gesture_commit",
    "ink_start", "ink_end", "rec_state",
}
CONDITIONS = {"C1", "C2", "C3"}
PHASES = {"practice", "main"}
EXPS = {"exp1", "exp2"}
STEP_TYPES = {"switch_only", "size_only", "switch_size", "no_change"}   # v1.2: copy 없음. no_change 는 515b823부터
TASK_TYPES = {"underline", "circle", "highlight", "word", "return"}
LANGUAGES = {"ko"}   # 11/4 결정: 한국어 고정. 열은 기록용으로 남긴다.
OUTCOMES = {"completed", "timeout", "skipped"}   # timeout 은 시간 제한이 있던 build 에서만 나온다
POINTER_TYPES = {"pen", "touch", "mouse"}
POINTER_SOURCES = {"canvas", "ui"}   # 포인터가 닿은 곳: 필기 영역 / 툴바·슬라이더·완료 버튼
GESTURE_CONDITIONS = {"C2", "C3"}
BASE_STATE = (1, 1.0)   # 본문 펜: 검정(슬롯 1) 1pt. passage.js 의 BASE 와 같아야 한다

# 브라우저가 세션마다 내려받는 파일 수 (docs/device-setup.md). collect.py 가 세션 끝에 확인한다.
EXPECTED_FILES = {"events": 18, "script": 15, "session": 1, "participant": 1}

_TEXT_COLUMNS = {
    "schema_version", "session_id", "participant", "condition", "phase", "exp",
    "script_id", "step_id", "event", "source", "pointer_type", "rec_state", "detail",
    "step_type", "task_type", "language", "cue_text", "text", "condition_order",
    "script_variant", "date", "device", "browser", "windows", "experimenter", "notes",
    "handedness", "native_language", "note_language", "item",
}


@dataclass
class Dataset:
    events: pd.DataFrame
    scripts: pd.DataFrame
    sessions: pd.DataFrame
    participants: pd.DataFrame
    questionnaire: pd.DataFrame


def read_csv(path: Path, required: list[str], optional: set[str] | frozenset = frozenset()) -> pd.DataFrame:
    """필수 컬럼을 확인하고, 숫자처럼 보이는 ID가 숫자로 바뀌지 않게 읽는다.

    optional 에 든 열은 없어도 되고, 없으면 빈 열로 채운다.
    step_id("01")나 participant("P01")가 숫자로 바뀌면 다른 표와 맞출 때 어긋나므로 글자로 읽는다.
    """
    header = pd.read_csv(path, nrows=0).columns.tolist()
    missing = [c for c in required if c not in header and c not in optional]
    if missing:
        raise ValueError(f"{path.name}: 컬럼 누락 {missing}")
    dtype = {c: "string" for c in header if c in _TEXT_COLUMNS}
    frame = pd.read_csv(path, dtype=dtype)
    for column in optional:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame


def load_dataset(root: str | Path) -> Dataset:
    """data/sample 또는 data/raw 처럼 같은 구조의 폴더를 읽는다.

    폴더 구조 (collect.py 가 브라우저 다운로드 폴더에서 이렇게 정리해 준다):
        events/events_<세션>_bNN.csv
        scripts/script_<제시문>.csv
        sessions.csv, participants.csv
        questionnaire.csv   (설문. 아직 없으면 빈 표로 읽고 validate_log 가 주의를 띄운다)
    """
    root = Path(root)
    event_files = sorted((root / "events").glob("events_*.csv"))
    script_files = sorted((root / "scripts").glob("script_*.csv"))
    if not event_files:
        raise FileNotFoundError(f"{root / 'events'} 에 events_*.csv 가 없습니다")
    if not script_files:
        raise FileNotFoundError(f"{root / 'scripts'} 에 script_*.csv 가 없습니다")
    frames = []
    for path in event_files:
        frame = read_csv(path, EVENT_COLUMNS)
        frames.append(frame.assign(source_file=path.name))
    questionnaire_path = root / "questionnaire.csv"
    questionnaire = (
        read_csv(questionnaire_path, QUESTIONNAIRE_COLUMNS)
        if questionnaire_path.exists()
        else pd.DataFrame(columns=QUESTIONNAIRE_COLUMNS)
    )
    return Dataset(
        events=pd.concat(frames, ignore_index=True),
        scripts=pd.concat(
            [read_csv(p, SCRIPT_COLUMNS, OPTIONAL_SCRIPT_COLUMNS) for p in script_files], ignore_index=True,
        ),
        sessions=read_csv(root / "sessions.csv", SESSION_COLUMNS),
        participants=read_csv(root / "participants.csv", PARTICIPANT_COLUMNS),
        questionnaire=questionnaire,
    )


def canvas_pen_downs(events: pd.DataFrame) -> pd.Series:
    """필기 영역에 닿은 펜 다운. 툴바·슬라이더·완료 버튼을 누른 펜 다운(source=ui)은 뺀다."""
    is_pen_down = (events["event"] == "pointerdown") & (events["pointer_type"] == "pen")
    return is_pen_down & ~events["source"].fillna("").eq("ui")


def parse_detail(detail: object) -> dict[str, str]:
    """'outcome=timeout;still_px=12' 형식의 detail 값을 dict 로 바꾼다."""
    if detail is None or pd.isna(detail):
        return {}
    pairs = (part.split("=", 1) for part in str(detail).split(";") if "=" in part)
    return {key.strip(): value.strip() for key, value in pairs}


def block_builds(events: pd.DataFrame) -> pd.Series:
    """(session_id, block) → build 값. block_start 가 없으면 빈칸."""
    starts = events[events["event"] == "block_start"]
    builds = starts["detail"].map(lambda d: parse_detail(d).get("build", pd.NA))
    return pd.Series(builds.to_numpy(), index=pd.MultiIndex.from_frame(starts[["session_id", "block"]]))
