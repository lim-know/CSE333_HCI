"""기록된 터치 궤적으로 인식 기준을 바꿔 다시 계산한다.

내부 테스트나 파일럿 뒤 STILL_PX, STILL_MS, 손→펜 간격(touch_to_pen_ms)을 정할 때 쓴다.
기록이 원시 이벤트라서 기준을 바꿔도 다시 수집할 필요가 없다.

판정 규칙은 tools/touch-probe.html 과 같다: 처음 닿은 위치에서 still_px 를 넘게 움직이면
그 손가락은 뗄 때까지 정지가 아니고, 닿은 지 still_ms 가 지나야 정지로 센다.
touch_to_pen_ms 를 주면, 손가락이 닿은 뒤 그 시간 안에 펜이 와야 센다 (손을 오래 올려둔 경우 제외).

사용법:
    python replay_thresholds.py <데이터 폴더> [--still PX MS ...] [--window MS ...]
    예: python replay_thresholds.py ../data/sample --still 12 120 --still 20 200 --window 500 1000 2000

출력:
1. 손→펜 간격 분포: 전환 단계(의도한 제스처)와 따라쓰기 단계(의도하지 않은 접촉)를 나눠 본다.
2. 기준 조합별로 손가락이 닿은 펜 다운 중 제스처로 인식되는 수.
   전환 단계에서는 많을수록, 따라쓰기 단계에서는 적을수록 좋다.
"""
from __future__ import annotations

import argparse
import math

import numpy as np
import pandas as pd

from logdata import canvas_pen_downs, load_dataset


def replay_block(block: pd.DataFrame, still_px: float, still_ms: float,
                 touch_to_pen_ms: float | None = None) -> pd.DataFrame:
    """필기 영역 펜 다운마다 기준을 적용한 정지 손가락 수와 손→펜 간격을 돌려준다."""
    block = block.sort_values("seq")
    is_canvas_pen_down = canvas_pen_downs(block)
    touches: dict[float, dict] = {}
    rows = []
    for index, row in zip(block.index, block.itertuples()):
        if row.event not in {"pointerdown", "pointermove", "pointerup", "pointercancel"}:
            continue
        if row.pointer_type == "touch":
            if row.event == "pointerdown":
                touches[row.pointer_id] = {"x0": row.x, "y0": row.y, "t0": row.t_event, "moved": False}
            elif row.event == "pointermove" and row.pointer_id in touches:
                touch = touches[row.pointer_id]
                if math.hypot(row.x - touch["x0"], row.y - touch["y0"]) > still_px:
                    touch["moved"] = True
            elif row.event in {"pointerup", "pointercancel"}:
                touches.pop(row.pointer_id, None)
        elif is_canvas_pen_down[index]:
            gaps = [row.t_event - touch["t0"] for touch in touches.values()]
            n_still = sum(
                not touch["moved"] and gap >= still_ms
                and (touch_to_pen_ms is None or gap <= touch_to_pen_ms)
                for touch, gap in zip(touches.values(), gaps)
            )
            rows.append({
                "session_id": row.session_id,
                "block": row.block,
                "condition": row.condition,
                "script_id": row.script_id,
                "step_id": row.step_id,
                "seq": row.seq,
                "n_touch": len(touches),
                "n_still_logged": row.n_still,
                "n_still_replay": n_still,
                # 마지막으로 닿은 손가락부터 펜까지의 시간. 여러 손가락이면 제스처가 완성된 시점 기준
                "touch_to_pen_ms": min(gaps) if gaps else np.nan,
            })
    return pd.DataFrame(rows)


def replay(events: pd.DataFrame, still_px: float, still_ms: float,
           touch_to_pen_ms: float | None = None) -> pd.DataFrame:
    frames = [
        replay_block(block, still_px, still_ms, touch_to_pen_ms)
        for _, block in events.groupby(["session_id", "block"])
    ]
    return pd.concat(frames, ignore_index=True)


def with_step_kind(result: pd.DataFrame, scripts: pd.DataFrame) -> pd.DataFrame:
    """펜 다운에 단계 종류를 붙인다: switch(전환 단계), copy(따라쓰기), between(단계 사이)."""
    types = scripts[["script_id", "step_id", "step_type"]]
    merged = result.merge(types, on=["script_id", "step_id"], how="left")
    merged["step_kind"] = np.select(
        [merged["step_type"] == "copy", merged["step_type"].notna()],
        ["copy", "switch"],
        default="between",
    )
    return merged


def interval_table(result: pd.DataFrame) -> pd.DataFrame:
    touched = result[result["n_touch"] >= 1]
    return touched.groupby(["condition", "step_kind"])["touch_to_pen_ms"].describe(
        percentiles=[0.1, 0.5, 0.9])[["count", "min", "10%", "50%", "90%", "max"]]


def threshold_table(events: pd.DataFrame, scripts: pd.DataFrame,
                    stills: list[tuple[float, float]], windows: list[float | None]) -> pd.DataFrame:
    rows = []
    for still_px, still_ms in stills:
        for window in windows:
            result = with_step_kind(replay(events, still_px, still_ms, window), scripts)
            touched = result[result["n_touch"] >= 1]
            row = {"still_px": still_px, "still_ms": still_ms,
                   "touch_to_pen_ms": "없음" if window is None else f"{window:g}"}
            for kind in ("switch", "copy"):
                part = touched[touched["step_kind"] == kind]
                row[f"{kind}_닿음"] = len(part)
                row[f"{kind}_인식"] = int((part["n_still_replay"] >= 1).sum())
            rows.append(row)
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", help="데이터 폴더")
    parser.add_argument("--still", nargs=2, type=float, action="append", metavar=("PX", "MS"),
                        help="정지 기준. 여러 번 줄 수 있다 (기본 12 120)")
    parser.add_argument("--window", nargs="+", type=float, metavar="MS",
                        help="손→펜 간격 상한 후보 (기본: 상한 없음만 계산)")
    args = parser.parse_args(argv)

    data = load_dataset(args.root)
    stills = [tuple(s) for s in args.still] if args.still else [(12.0, 120.0)]
    windows: list[float | None] = [None] + (args.window or [])

    base = with_step_kind(replay(data.events, *stills[0]), data.scripts)
    with pd.option_context("display.width", 120, "display.max_columns", None):
        print("[손→펜 간격 (ms): 손가락이 닿아 있던 펜 다운만]")
        print(interval_table(base).round(0))
        print("\n[기준별 인식 수: switch 는 많을수록, copy 는 적을수록 좋음]")
        print(threshold_table(data.events, data.scripts, stills, windows).to_string(index=False))


if __name__ == "__main__":
    main()
