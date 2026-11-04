"""기록된 터치 궤적으로 손가락 정지 임계값을 바꿔 다시 계산한다.

파일럿 뒤 STILL_PX, STILL_MS 를 정할 때 쓴다. 재수집이 필요 없는 이유가 이 스크립트다.
판정 규칙은 tools/touch-probe.html 과 같다: 처음 닿은 위치에서 still_px 를 넘게 움직이면
그 손가락은 뗄 때까지 정지가 아니고, 닿은 지 still_ms 가 지나야 정지로 센다.

사용법:
    python replay_thresholds.py <데이터 폴더> [still_px still_ms ...]
    예: python replay_thresholds.py ../data/sample 12 120 8 80 20 200
"""
from __future__ import annotations

import math
import sys

import pandas as pd

from logdata import load_dataset


def replay_block(block: pd.DataFrame, still_px: float, still_ms: float) -> pd.DataFrame:
    """펜 다운마다 임계값을 적용한 정지 손가락 수를 돌려준다."""
    touches: dict[float, dict] = {}
    rows = []
    for row in block.sort_values("seq").itertuples():
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
        elif row.pointer_type == "pen" and row.event == "pointerdown":
            n_still = sum(
                not touch["moved"] and row.t_event - touch["t0"] >= still_ms
                for touch in touches.values()
            )
            rows.append({
                "session_id": row.session_id,
                "block": row.block,
                "step_id": row.step_id,
                "seq": row.seq,
                "condition": row.condition,
                "n_touch": len(touches),
                "n_still_logged": row.n_still,
                "n_still_replay": n_still,
            })
    return pd.DataFrame(rows)


def replay(events: pd.DataFrame, still_px: float, still_ms: float) -> pd.DataFrame:
    frames = [replay_block(block, still_px, still_ms) for _, block in events.groupby(["session_id", "block"])]
    return pd.concat(frames, ignore_index=True)


def main(root: str, pairs: list[tuple[float, float]]) -> None:
    events = load_dataset(root).events
    for still_px, still_ms in pairs:
        result = replay(events, still_px, still_ms)
        with_touch = result[result["n_touch"] >= 1]
        same = (with_touch["n_still_logged"] == with_touch["n_still_replay"]).sum()
        print(f"STILL_PX={still_px:g}, STILL_MS={still_ms:g}: "
              f"손가락이 닿은 펜 다운 {len(with_touch)}회, 기록과 일치 {same}회, "
              f"정지 손가락 평균 {with_touch['n_still_replay'].mean():.2f}개")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or len(args) % 2 == 0:
        sys.exit("사용법: python replay_thresholds.py <데이터 폴더> [still_px still_ms ...]")
    numbers = [float(a) for a in args[1:]] or [12.0, 120.0]
    main(args[0], list(zip(numbers[::2], numbers[1::2])))
