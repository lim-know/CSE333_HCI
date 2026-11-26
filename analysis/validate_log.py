"""세션 직후 실행하는 로그 점검. 오류가 있으면 종료 코드 1을 반환한다.

사용법:
    python validate_log.py <데이터 폴더>
"""
from __future__ import annotations

import sys

import pandas as pd

from logdata import (
    ACCEPTED_SCHEMA_VERSIONS, APP_EVENTS, CONDITIONS, EXPS, GESTURE_CONDITIONS, KNOWN_BUILDS,
    LANGUAGES, OUTCOMES, PHASES, POINTER_EVENTS, POINTER_SOURCES, POINTER_TYPES, STEP_TYPES,
    TASK_TYPES, Dataset, load_dataset, parse_detail,
)

# 시간 제한과 실제 단계 길이를 비교할 때의 여유 (ms)
LIMIT_SLACK_MS = 500
MAIN_BLOCKS_PER_CONDITION = 5   # 조건당 본과제 제시문 5개 (PR #11)

# 참가자 번호 → (조건 순서, 제시문 세트 순서). prototype/js/task.js 의 ORDERS 와 같아야 한다 (리포트 4.4).
# 두 명씩 같은 순서: P01·P02, P03·P04, ...  보충 참가자는 빠진 사람과 같은 순서를 쓴다.
ORDERS = [
    ("C1-C2-C3", "A-B-C"), ("C1-C3-C2", "A-B-C"), ("C2-C1-C3", "B-C-A"),
    ("C2-C3-C1", "C-A-B"), ("C3-C1-C2", "B-C-A"), ("C3-C2-C1", "C-A-B"),
]


def expected_order(participant: str) -> tuple[str, str] | None:
    """task.js assignOrder() 와 같은 규칙. 번호를 못 읽으면 None."""
    digits = "".join(ch for ch in str(participant) if ch.isdigit())
    if not digits or int(digits) < 1:
        return None
    return ORDERS[((int(digits) - 1) % 12) // 2]


def _unknown(series: pd.Series, allowed: set[str]) -> list[str]:
    return sorted(set(series.dropna().astype(str)) - allowed)


def _check_scripts(scripts: pd.DataFrame, errors: list[str]) -> None:
    duplicated = scripts[scripts.duplicated(["script_id", "step_id"], keep=False)]
    if len(duplicated):
        errors.append(f"스크립트 step_id 중복: {sorted(set(duplicated['script_id'] + '/' + duplicated['step_id']))}")
    for column, allowed in (("exp", EXPS), ("step_type", STEP_TYPES), ("task_type", TASK_TYPES),
                            ("language", LANGUAGES)):
        bad = _unknown(scripts[column], allowed)
        if bad:
            errors.append(f"스크립트 {column} 값 오류: {bad}")
    for row in scripts.itertuples():
        where = f"스크립트 {row.script_id}/{row.step_id}"
        # v1.2: 모든 단계(본문 복귀 포함)에 목표 펜·굵기가 있다
        if pd.isna(row.target_slot) or pd.isna(row.target_size):
            errors.append(f"{where}: target_slot/target_size 없음")
        # time_limit_ms 는 11/26 결정으로 없앨 예정이라 검사하지 않는다 (있으면 timeout 판정 확인에만 쓴다)


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
    bad_source = _unknown(pen_downs["source"].fillna("(빈칸)"), POINTER_SOURCES)
    if bad_source:
        errors.append(f"{label}: 펜 pointerdown 의 source 는 canvas/ui 여야 함 ({bad_source})")
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

    if (block["event"] == "block_start").any():
        start = block[block["event"] == "block_start"].iloc[0]
        details = parse_detail(start["detail"])
        missing = [k for k in ("build", "still_px", "still_ms", "epoch_ms") if k not in details]
        if missing:
            errors.append(f"{label}: block_start detail 누락 {missing}")
        build = details.get("build")
        if build is not None and build not in KNOWN_BUILDS:
            warnings.append(f"{label}: 처음 보는 build '{build}' — logdata.KNOWN_BUILDS 와 log-schema.md 표에 추가")
        if block["condition"].iloc[0] in GESTURE_CONDITIONS and "touch_to_pen_ms" not in details:
            warnings.append(f"{label}: block_start 에 touch_to_pen_ms 없음 (손→펜 간격 기준이 기록되지 않음)")

    # 지시가 나온 단계는 모두 step_end 가 있어야 한다 (단계표가 없는 연습 블록도 확인)
    cues = block[block["event"] == "cue_shown"]
    ends = block[block["event"] == "step_end"]
    missing_end = set(cues["step_id"].dropna()) - set(ends["step_id"].dropna())
    if missing_end:
        errors.append(f"{label}: step_end 없음 {sorted(missing_end)}")

    script_id = block["script_id"].iloc[0]
    expected = scripts[scripts["script_id"] == script_id]
    if expected.empty:
        if block["phase"].iloc[0] == "practice":
            # 브라우저는 연습 제시문 단계표를 저장하지 않는다. 연습은 분석하지 않으므로 주의만 띄운다.
            warnings.append(f"{label}: 연습 블록 단계표({script_id}) 없음 — 분석에서 빠짐")
        else:
            errors.append(f"{label}: 스크립트 {script_id} 없음")
        return
    if expected["exp"].iloc[0] != block["exp"].iloc[0]:
        errors.append(f"{label}: 스크립트와 로그의 exp 불일치")

    expected_steps = set(expected["step_id"])
    cues = block[block["event"] == "cue_shown"]
    cued = set(cues["step_id"].dropna())
    ends = block[block["event"] == "step_end"]
    if expected_steps - cued:
        # v1.2: 표시를 남긴 채 완료를 누르면 진행 중 단계는 skipped, 남은 단계는 지시가 나오지 않는다.
        # 그 경우(마지막 step_end 바로 다음 행이 block_end)는 주의, 아니면 블록이 끊긴 것이라 오류.
        ordered = block.sort_values("seq")
        last_end = ends.sort_values("seq").tail(1)
        early_done = False
        if len(last_end) and parse_detail(last_end["detail"].iloc[0]).get("outcome") == "skipped":
            after = ordered[ordered["seq"] > last_end["seq"].iloc[0]]
            early_done = len(after) > 0 and after["event"].iloc[0] == "block_end"
        message = f"{label}: 지시가 나오지 않은 단계 {sorted(expected_steps - cued)}"
        if early_done:
            warnings.append(message + " (참가자가 완료를 일찍 누름)")
        else:
            errors.append(message)
    if cued - expected_steps:
        errors.append(f"{label}: 스크립트에 없는 단계 {sorted(cued - expected_steps)}")
    repeated = cues[cues["step_id"].duplicated()]["step_id"]
    if len(repeated):
        errors.append(f"{label}: cue_shown 중복 {sorted(set(repeated))}")

    limits = expected.set_index("step_id")["time_limit_ms"]
    cue_times = cues.drop_duplicates("step_id").set_index("step_id")["t_event"]
    for row in ends.itertuples():
        outcome = parse_detail(row.detail).get("outcome")
        if outcome not in OUTCOMES:
            errors.append(f"{label}/{row.step_id}: outcome 값 오류 ({outcome})")
            continue
        if outcome != "completed":
            warnings.append(f"{label}/{row.step_id}: {outcome}")
        if row.step_id not in cue_times.index or row.step_id not in limits.index:
            continue
        limit = limits[row.step_id]
        if pd.isna(limit):
            continue
        duration = row.t_event - cue_times[row.step_id]
        if outcome == "timeout" and duration < limit - LIMIT_SLACK_MS:
            warnings.append(f"{label}/{row.step_id}: 제한 시간({limit:g}ms) 전에 timeout ({duration:.0f}ms)")

def validate(data: Dataset) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    events = data.events

    versions = set(events["schema_version"].dropna())
    if not versions or not versions <= ACCEPTED_SCHEMA_VERSIONS:
        errors.append(f"schema_version 불일치: {sorted(versions)} (허용 {sorted(ACCEPTED_SCHEMA_VERSIONS)})")
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

    if data.questionnaire.empty:
        warnings.append("questionnaire.csv 없음 — NASA-TLX·선호 순위(H5)는 분석하지 않음")
    for session in data.sessions.itertuples():
        order = str(session.condition_order).split("-")
        if sorted(order) != ["C1", "C2", "C3"]:
            errors.append(f"{session.session_id}: condition_order 오류 ({session.condition_order})")
            continue
        expected = expected_order(session.participant)
        actual = (session.condition_order, session.script_variant)
        if expected is not None and actual != expected:
            # 진행자가 시작 화면에서 순서를 직접 바꿨거나 참가자 번호를 잘못 넣은 경우. 보충 참가자면 정상일 수 있다.
            warnings.append(f"{session.session_id}: 배정표와 다른 순서 {actual} (배정표 {expected}). 보충 참가자인지 확인")
        done = events[events["session_id"] == session.session_id]
        builds = set(done.loc[done["event"] == "block_start", "detail"].map(lambda d: parse_detail(d).get("build")))
        if len(builds) > 1:
            errors.append(f"{session.session_id}: 한 세션에 build 가 여러 개 {sorted(map(str, builds))} — 세션 중에 코드가 바뀜")
        main_rows = done[done["phase"] == "main"]
        for condition, blocks in main_rows.groupby("condition")["script_id"]:
            if blocks.nunique() != MAIN_BLOCKS_PER_CONDITION:
                warnings.append(f"{session.session_id} {condition}: 본과제 제시문 {blocks.nunique()}개 "
                                f"(기대 {MAIN_BLOCKS_PER_CONDITION}개) — 빠진 events 파일 확인")
        main_done = set(main_rows["condition"])
        if main_done and main_done != set(order):
            warnings.append(f"{session.session_id}: 본 시행이 없는 조건 {sorted(set(order) - main_done)}")
        if data.questionnaire.empty:
            continue
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
