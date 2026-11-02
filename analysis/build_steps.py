"""원시 이벤트 + 스크립트 표 -> 단계별 분석 표(steps).

판정 기준은 이 파일에만 둔다. 기준이 바뀌면 재수집 없이 다시 실행하면 된다.

사용법:
    python build_steps.py <데이터 폴더> [출력 CSV 경로]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from logdata import load_dataset, parse_detail

# 잠정값: 파일럿 후 확정 (docs/log-schema.md "합의할 것" 참고)
SIZE_TOL_RATIO = 1.10   # 목표 굵기 대비 이 비율 안이면 정답

ACTION_EVENTS = {"toolbar_tap", "slider_start", "slider_end", "activation", "gesture_commit"}


def _size_ok(size: float, target: float) -> bool:
    if pd.isna(target):
        return True
    if pd.isna(size) or size <= 0:
        return False
    ratio = size / target
    return 1 / SIZE_TOL_RATIO <= ratio <= SIZE_TOL_RATIO


def _slot_ok(slot: float, target: float) -> bool:
    return True if pd.isna(target) else slot == target


def _log2_error(size: float, target: float) -> float:
    if pd.isna(size) or pd.isna(target) or size <= 0:
        return np.nan
    return float(np.log2(size / target))


def _summarize_step(block: pd.DataFrame, cue: pd.Series, spec: pd.Series, order_index: float) -> dict:
    """한 단계의 이벤트를 분석용 한 줄로 요약한다."""
    step = block[block["step_id"] == cue["step_id"]]
    is_copy = spec["step_type"] == "copy"
    t_cue = cue["t_event"]
    target_slot, target_size = spec["target_slot"], spec["target_size"]

    previous_ink = block[(block["event"] == "ink_end") & (block["t_event"] < t_cue)]
    t_prev_ink_end = previous_ink["t_event"].max() if len(previous_ink) else np.nan

    inks = step[step["event"] == "ink_start"]
    t_first_correct, n_wrong_slot, n_wrong_size = np.nan, 0, 0
    if not is_copy:
        for ink in inks.itertuples():
            slot_ok = _slot_ok(ink.slot, target_slot)
            size_ok = _size_ok(ink.size, target_size)
            if slot_ok and size_ok:
                t_first_correct = ink.t_event
                break
            n_wrong_slot += not slot_ok
            n_wrong_size += not size_ok

    actions = step[step["event"].isin(ACTION_EVENTS)]
    if not np.isnan(t_first_correct):
        actions = actions[actions["t_event"] <= t_first_correct]
    t_first_action = actions["t_event"].min() if len(actions) else np.nan
    t_last_action = actions["t_event"].max() if len(actions) else np.nan

    end_rows = step[step["event"] == "step_end"]
    t_end = end_rows["t_event"].iloc[-1] if len(end_rows) else np.nan
    outcome = parse_detail(end_rows["detail"].iloc[-1]).get("outcome", "unknown") if len(end_rows) else "missing"

    pen_downs = step[(step["event"] == "pointerdown") & (step["pointer_type"] == "pen")]
    n_activations = int((step["event"] == "activation").sum())
    # 손가락이 닿아 있는데 정지로 판정되지 않은 펜 다운: 전환 단계에서만 인식 실패 후보로 본다.
    possible_missed = 0 if is_copy else int(((pen_downs["n_touch"] >= 1) & (pen_downs["n_still"] == 0)).sum())

    first_ink = inks.iloc[0] if len(inks) else None
    last_ink = inks.iloc[-1] if len(inks) else None
    first_size = first_ink["size"] if first_ink is not None else np.nan
    final_size = last_ink["size"] if last_ink is not None else np.nan

    return {
        "session_id": cue["session_id"],
        "participant": cue["participant"],
        "block": cue["block"],
        "condition": cue["condition"],
        "order_index": order_index,
        "phase": cue["phase"],
        "exp": cue["exp"],
        "script_id": cue["script_id"],
        "step_id": cue["step_id"],
        "step_type": spec["step_type"],
        "task_type": spec["task_type"],
        "language": spec["language"],
        "target_slot": target_slot,
        "target_size": target_size,
        "on_preset": spec["on_preset"],
        "start_slot": cue["slot"],
        "start_size": cue["size"],
        "outcome": outcome,
        "t_cue": t_cue,
        "t_prev_ink_end": t_prev_ink_end,
        "t_first_action": t_first_action,
        "t_last_action": t_last_action,
        "t_first_ink": first_ink["t_event"] if first_ink is not None else np.nan,
        "t_first_correct": t_first_correct,
        "t_end": t_end,
        "time_cue_to_correct": t_first_correct - t_cue,
        "time_prev_ink_to_correct": t_first_correct - t_prev_ink_end,
        "time_reaction": t_first_action - t_cue,
        "time_manipulate": t_last_action - t_first_action,
        "time_acquire": t_first_correct - t_last_action,
        "duration": t_end - t_cue,
        "first_slot": first_ink["slot"] if first_ink is not None else np.nan,
        "first_size": first_size,
        "final_slot": last_ink["slot"] if last_ink is not None else np.nan,
        "final_size": final_size,
        "first_size_log2_err": _log2_error(first_size, target_size),
        "final_size_log2_err": _log2_error(final_size, target_size),
        "n_pen_downs": len(pen_downs),
        "n_ink": len(inks),
        "n_toolbar_taps": int((step["event"] == "toolbar_tap").sum()),
        "n_slider_drags": int((step["event"] == "slider_start").sum()),
        "n_gestures": int((step["event"] == "gesture_commit").sum()),
        "n_activations": n_activations,
        "n_unintended": n_activations if is_copy else 0,
        "n_possible_missed": possible_missed,
        "n_wrong_slot": n_wrong_slot,
        "n_wrong_size": n_wrong_size,
        "n_pointercancel": int((step["event"] == "pointercancel").sum()),
    }


def build_steps(events: pd.DataFrame, scripts: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    specs = scripts.set_index(["script_id", "step_id"])
    orders = {
        row.session_id: str(row.condition_order).split("-")
        for row in sessions.itertuples()
    }
    rows = []
    for (session_id, _), block in events.groupby(["session_id", "block"], sort=True):
        block = block.sort_values("seq")
        for _, cue in block[block["event"] == "cue_shown"].iterrows():
            order = orders.get(session_id, [])
            order_index = order.index(cue["condition"]) + 1 if cue["condition"] in order else np.nan
            spec = specs.loc[(cue["script_id"], cue["step_id"])]
            rows.append(_summarize_step(block, cue, spec, order_index))
    return pd.DataFrame(rows)


def main(root: str, out: str | None) -> None:
    data = load_dataset(root)
    steps = build_steps(data.events, data.scripts, data.sessions)
    if out:
        steps.to_csv(out, index=False)
        print(f"{len(steps)}개 단계 저장: {out}")
    else:
        print(steps.to_string(max_rows=20))


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("사용법: python build_steps.py <데이터 폴더> [출력 CSV 경로]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
