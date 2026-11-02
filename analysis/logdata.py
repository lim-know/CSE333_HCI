"""로그 형식 정의와 불러오기 (docs/log-schema.md 와 항상 같이 고친다)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

SCHEMA_VERSION = "1.0"

EVENT_COLUMNS = [
    "schema_version", "session_id", "participant", "block", "condition", "phase",
    "exp", "script_id", "step_id", "seq", "t_event", "t_logged", "event", "source",
    "pointer_id", "pointer_type", "x", "y", "width", "height", "buttons",
    "slot", "size", "rec_state", "n_touch", "n_still", "detail",
]
SCRIPT_COLUMNS = [
    "script_id", "step_id", "exp", "step_type", "task_type", "language", "cue_text",
    "target_slot", "target_size", "on_preset", "target_x", "target_y", "text",
]
SESSION_COLUMNS = [
    "session_id", "participant", "condition_order", "script_variant", "date",
    "device", "browser", "windows", "screen_w", "screen_h", "dpr", "experimenter", "notes",
]
PARTICIPANT_COLUMNS = [
    "participant", "handedness", "native_language", "note_language",
    "english_proficiency", "tablet_note_months",
]
QUESTIONNAIRE_COLUMNS = ["participant", "condition", "item", "value"]

POINTER_EVENTS = {"pointerdown", "pointermove", "pointerup", "pointercancel"}
APP_EVENTS = {
    "block_start", "block_end", "cue_shown", "step_end", "toolbar_tap", "slider_start",
    "slider_end", "slot_change", "size_change", "activation", "gesture_commit",
    "ink_start", "ink_end", "rec_state",
}
CONDITIONS = {"C1", "C2", "C3"}
PHASES = {"practice", "main"}
EXPS = {"exp1", "exp2"}
STEP_TYPES = {"switch_only", "size_only", "switch_size", "copy"}
LANGUAGES = {"ko", "en"}
OUTCOMES = {"completed", "timeout", "skipped"}
POINTER_TYPES = {"pen", "touch", "mouse"}

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


def _read_csv(path: Path, required: list[str]) -> pd.DataFrame:
    """필수 컬럼을 확인하고, 숫자처럼 보이는 ID가 숫자로 바뀌지 않게 읽는다."""
    header = pd.read_csv(path, nrows=0).columns.tolist()
    missing = [c for c in required if c not in header]
    if missing:
        raise ValueError(f"{path.name}: 컬럼 누락 {missing}")
    dtype = {c: "string" for c in header if c in _TEXT_COLUMNS}
    return pd.read_csv(path, dtype=dtype)


def load_dataset(root: str | Path) -> Dataset:
    """data/sample 또는 data/raw 처럼 같은 구조의 폴더를 읽는다."""
    root = Path(root)
    event_files = sorted((root / "events").glob("events_*.csv"))
    script_files = sorted((root / "scripts").glob("script_*.csv"))
    if not event_files:
        raise FileNotFoundError(f"{root / 'events'} 에 events_*.csv 가 없습니다")
    if not script_files:
        raise FileNotFoundError(f"{root / 'scripts'} 에 script_*.csv 가 없습니다")
    frames = []
    for path in event_files:
        frame = _read_csv(path, EVENT_COLUMNS)
        frames.append(frame.assign(source_file=path.name))
    return Dataset(
        events=pd.concat(frames, ignore_index=True),
        scripts=pd.concat([_read_csv(p, SCRIPT_COLUMNS) for p in script_files], ignore_index=True),
        sessions=_read_csv(root / "sessions.csv", SESSION_COLUMNS),
        participants=_read_csv(root / "participants.csv", PARTICIPANT_COLUMNS),
        questionnaire=_read_csv(root / "questionnaire.csv", QUESTIONNAIRE_COLUMNS),
    )


def parse_detail(detail: object) -> dict[str, str]:
    """'outcome=timeout;still_px=12' 형식의 detail 값을 dict 로 바꾼다."""
    if detail is None or pd.isna(detail):
        return {}
    pairs = (part.split("=", 1) for part in str(detail).split(";") if "=" in part)
    return {key.strip(): value.strip() for key, value in pairs}
