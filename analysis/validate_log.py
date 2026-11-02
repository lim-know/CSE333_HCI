"""세션 직후 실행하는 로그 점검. 오류가 있으면 종료 코드 1을 반환한다.

사용법:
    python validate_log.py <데이터 폴더>
"""
from __future__ import annotations

import sys

import pandas as pd

from logdata import (
    APP_EVENTS, CONDITIONS, EXPS, LANGUAGES, OUTCOMES, PHASES, POINTER_EVENTS,
    POINTER_TYPES, SCHEMA_VERSION, STEP_TYPES, Dataset, load_dataset, parse_detail,
)


def _unknown(series: pd.Series, allowed: set[str]) -> list[str]:
    return sorted(set(series.dropna().astype(str)) - allowed)


def _check_scripts(scripts: pd.DataFrame, errors: list[str]) -> None:
    duplicated = scripts[scripts.duplicated(["script_id", "step_id"], keep=False)]
    if len(duplicated):
        errors.append(f"스크립트 step_id 중복: {sorted(set(duplicated['step_id']))}")
    for column, allowed in (("exp", EXPS), ("step_type", STEP_TYPES), ("language", LANGUAGES)):
        bad = _unknown(scripts[column], allowed)
        if bad:
            errors.append(f"스크립트 {column} 값 오류: {bad}")
    for row in scripts.itertuples():
        where = f"스크립트 {row.script_id}/{row.step_id}"
        if row.step_type == "copy":
            if pd.isna(row.language):
                errors.append(f"{where}: copy 단계에 language 없음")
            if pd.notna(row.target_slot) or pd.notna(row.target_size):
                errors.append(f"{where}: copy 단계에는 목표값을 비워야 함")
        if row.step_type in ("switch_only", "switch_size") and pd.isna(row.target_slot):
            errors.append(f"{where}: target_slot 없음")
        if row.step_type in ("size_only", "switch_size") and pd.isna(row.target_size):
            errors.append(f"{where}: target_size 없음")


def _check_block(key: tuple, block: pd.DataFrame, scripts: pd.DataFrame,
                 errors: list[str], warnings: list[str]) -> None:
    label = f"{key[0]} block {key[1]}"
    for column in ("condition", "phase", "exp", "script_id", "participant"):
        if block[column].nunique(dropna=False) != 1:
            errors.append(f"{label}: {column} 값이 블록 안에서 바뀜")
    if block["seq"].duplicated().any():
        errors.append(f"{label}: seq 중복")
    in_file_order = block["seq"].to_numpy()
    if (in_file_order[1:] <= in_file_order[:-1]).any():
        errors.append(f"{label}: seq 가 증가하지 않음")
    if (block["t_event"].diff().dropna() < 0).any():
        warnings.append(f"{label}: t_event 역전 {(block['t_event'].diff() < 0).sum()}건")
    for event in ("block_start", "block_end"):
        count = int((block["event"] == event).sum())
        if count != 1:
            errors.append(f"{label}: {event} {count}개 (1개여야 함)")

    pen_downs = block[(block["event"] == "pointerdown") & (block["pointer_type"] == "pen")]
    if pen_downs[["n_touch", "n_still"]].isna().any().any():
        errors.append(f"{label}: 펜 pointerdown 에 n_touch/n_still 누락")
    pointer_rows = block[block["event"].isin(POINTER_EVENTS)]
    if pointer_rows[["pointer_id", "pointer_type", "x", "y"]].isna().any().any():
        errors.append(f"{label}: 포인터 이벤트의 ID, 종류, 좌표 누락")
    state_rows = block[block["event"].isin({"cue_shown", "ink_start"})]
    if state_rows[["slot", "size"]].isna().any().any():
        errors.append(f"{label}: cue_shown/ink_start 에 slot/size 누락")
    bad_slot = block["slot"].dropna()
    if (~bad_slot.isin([1, 2, 3])).any():
        errors.append(f"{label}: slot 값이 1~3 범위를 벗어남")
    if (block["size"].dropna() <= 0).any():
        errors.append(f"{label}: size 가 0 이하")

    cancels = int((block["event"] == "pointercancel").sum())
    if cancels:
        warnings.append(f"{label}: pointercancel {cancels}건")
    if pointer_rows.empty:
        warnings.append(f"{label}: 포인터 이벤트 없음")

    script_id = block["script_id"].iloc[0]
    expected = scripts[scripts["script_id"] == script_id]
    if expected.empty:
        errors.append(f"{label}: 스크립트 {script_id} 없음")
        return
    if expected["exp"].iloc[0] != block["exp"].iloc[0]:
        errors.append(f"{label}: 스크립트와 로그의 exp 불일치")

    expected_steps = set(expected["step_id"])
    cues = block[block["event"] == "cue_shown"]
    cued = set(cues["step_id"].dropna())
    if expected_steps - cued:
        errors.append(f"{label}: 지시가 나오지 않은 단계 {sorted(expected_steps - cued)}")
    if cued - expected_steps:
        errors.append(f"{label}: 스크립트에 없는 단계 {sorted(cued - expected_steps)}")
    repeated = cues[cues["step_id"].duplicated()]["step_id"]
    if len(repeated):
        errors.append(f"{label}: cue_shown 중복 {sorted(set(repeated))}")

    ends = block[block["event"] == "step_end"]
    missing_end = cued - set(ends["step_id"].dropna())
    if missing_end:
        errors.append(f"{label}: step_end 없음 {sorted(missing_end)}")
    for row in ends.itertuples():
        outcome = parse_detail(row.detail).get("outcome")
        if outcome not in OUTCOMES:
            errors.append(f"{label}/{row.step_id}: outcome 값 오류 ({outcome})")
        elif outcome != "completed":
            warnings.append(f"{label}/{row.step_id}: {outcome}")
    if (block["event"] == "block_start").any():
        start = block[block["event"] == "block_start"].iloc[0]
        details = parse_detail(start["detail"])
        missing = [k for k in ("build", "still_px", "still_ms", "epoch_ms") if k not in details]
        if missing:
            errors.append(f"{label}: block_start detail 누락 {missing}")


def validate(data: Dataset) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    events = data.events

    versions = set(events["schema_version"].dropna())
    if versions != {SCHEMA_VERSION}:
        errors.append(f"schema_version 불일치: {sorted(versions)} (기대값 {SCHEMA_VERSION})")
    for column, allowed in (
        ("event", POINTER_EVENTS | APP_EVENTS),
        ("condition", CONDITIONS),
        ("phase", PHASES),
        ("exp", EXPS),
        ("pointer_type", POINTER_TYPES),
    ):
        bad = _unknown(events[column], allowed)
        if bad:
            errors.append(f"이벤트 {column} 값 오류: {bad}")
    for column in ("session_id", "block", "seq", "t_event", "t_logged", "event"):
        if events[column].isna().any():
            errors.append(f"이벤트 {column} 에 빈칸 있음")
    if errors:
        return errors, warnings

    _check_scripts(data.scripts, errors)

    known_sessions = set(data.sessions["session_id"])
    unknown = sorted(set(events["session_id"]) - known_sessions)
    if unknown:
        errors.append(f"sessions.csv 에 없는 세션: {unknown}")
    known_participants = set(data.participants["participant"])
    unknown = sorted(set(data.sessions["participant"]) - known_participants)
    if unknown:
        errors.append(f"participants.csv 에 없는 참가자: {unknown}")
    bad_native = data.participants[data.participants["native_language"] != "ko"]
    if len(bad_native):
        errors.append(f"한국어 모국어 조건 위반: {sorted(bad_native['participant'])}")
    if data.sessions["session_id"].duplicated().any():
        errors.append("sessions.csv 에 session_id 중복")

    for key, block in events.groupby(["session_id", "block"], sort=True):
        _check_block(key, block, data.scripts, errors, warnings)
    file_counts = events.groupby(["session_id", "block"])["source_file"].nunique()
    if (file_counts > 1).any():
        errors.append("같은 세션·블록이 여러 파일에 나뉘어 있음")

    for session in data.sessions.itertuples():
        order = str(session.condition_order).split("-")
        if sorted(order) != ["C1", "C2", "C3"]:
            errors.append(f"{session.session_id}: condition_order 오류 ({session.condition_order})")
            continue
        done = events[events["session_id"] == session.session_id]
        main_done = set(done.loc[done["phase"] == "main", "condition"])
        if main_done and main_done != set(order):
            warnings.append(f"{session.session_id}: 본 시행이 없는 조건 {sorted(set(order) - main_done)}")
        tlx = data.questionnaire[data.questionnaire["participant"] == session.participant]
        if main_done - set(tlx["condition"]):
            warnings.append(f"{session.session_id}: 설문이 없는 조건 {sorted(main_done - set(tlx['condition']))}")
    return errors, warnings


def main(root: str) -> int:
    errors, warnings = validate(load_dataset(root))
    for message in warnings:
        print(f"[주의] {message}")
    for message in errors:
        print(f"[오류] {message}")
    print(f"점검 끝: 오류 {len(errors)}건, 주의 {len(warnings)}건")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("사용법: python validate_log.py <데이터 폴더>")
    sys.exit(main(sys.argv[1]))
