"""Count & Tune 로그 분석 (담당: 정원준)

사용법:
    python analyze.py <데이터 폴더>

로그를 먼저 점검하고, 오류가 있으면 분석하지 않는다.
현재는 파일럿용 기술통계만 낸다. 로그 형식은 docs/log-schema.md 참고.
- 본실험 계획: RM-ANOVA (전환 시간), Friedman (NASA-TLX), TOST (H2 동등성, H3 비열등성)
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from build_steps import build_steps
from logdata import load_dataset
from validate_log import validate


def switching_summary(steps: pd.DataFrame) -> pd.DataFrame:
    """exp를 섞지 않고, 끝내 맞추지 못한 단계도 분모에 남겨 요약한다."""
    switching = steps[(steps["phase"] == "main") & (steps["step_type"] != "copy")]
    by_participant = (
        switching.groupby(["exp", "step_type", "condition", "participant"])["time_cue_to_correct"]
        .median()
        .groupby(["exp", "step_type", "condition"])
        .median()
        .rename("median_ms")
    )
    table = switching.groupby(["exp", "step_type", "condition"]).agg(
        n_steps=("step_id", "size"),
        n_resolved=("time_cue_to_correct", "count"),
    )
    table["n_unresolved"] = table["n_steps"] - table["n_resolved"]
    return table.join(by_participant)


def activation_summary(steps: pd.DataFrame) -> pd.DataFrame:
    """따라쓰기 구간의 의도치 않은 발동을 펜 다운 100회당으로 계산한다."""
    copy = steps[(steps["phase"] == "main") & (steps["step_type"] == "copy")]
    table = copy.groupby(["condition", "language"]).agg(
        n_pen_downs=("n_pen_downs", "sum"),
        n_unintended=("n_unintended", "sum"),
    )
    table["per_100_pen_downs"] = 100 * table["n_unintended"] / table["n_pen_downs"].replace(0, np.nan)
    return table


def size_error_summary(steps: pd.DataFrame) -> pd.DataFrame:
    """굵기 오차를 log2 비율로 요약한다. 값 0이면 목표와 같다."""
    sized = steps[(steps["phase"] == "main") & steps["target_size"].notna()].copy()
    sized["abs_log2_err"] = sized["final_size_log2_err"].abs()
    return (
        sized.groupby(["exp", "condition", "participant"])["abs_log2_err"]
        .mean()
        .groupby(["exp", "condition"])
        .mean()
        .rename("mean_abs_log2_err")
        .to_frame()
    )


def main(root: str) -> int:
    data = load_dataset(root)
    errors, warnings = validate(data)
    print(f"로그 점검: 오류 {len(errors)}건, 주의 {len(warnings)}건")
    for message in errors:
        print(f"[오류] {message}")
    if errors:
        return 1

    steps = build_steps(data.events, data.scripts, data.sessions)
    main_steps = steps[steps["phase"] == "main"]
    print(f"참가자 {steps['participant'].nunique()}명, 전체 {len(steps)}단계, 본 시행 {len(main_steps)}단계")
    with pd.option_context("display.width", 120, "display.max_columns", None):
        print("\n[전환 시간: 지시 -> 첫 정답 획, 참가자별 중앙값의 중앙값]")
        print(switching_summary(steps).round(1))
        print("\n[의도치 않은 발동: 따라쓰기 구간]")
        print(activation_summary(steps).round(2))
        print("\n[굵기 오차: |log2(실제/목표)|]")
        print(size_error_summary(steps).round(3))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("사용법: python analyze.py <데이터 폴더>")
    sys.exit(main(sys.argv[1]))
