"""Count & Tune 로그 분석 (담당: 정원준)

사용법:
    python analyze.py <로그 CSV 경로>

현재는 형식 확인용 뼈대. 로그 형식은 docs/log-schema.md 참고.
- 파일럿: 가설 검정 없이 기술통계와 그래프만 확인
- 본실험: RM-ANOVA (전환 시간), Friedman / ART (NASA-TLX), TOST (H3 굵기 오차 비열등성)
"""
import sys
import pandas as pd


def main(path: str) -> None:
    df = pd.read_csv(path)
    main_trials = df[df["phase"] == "main"]
    print(f"전체 {len(df)}행, 본 시행 {len(main_trials)}행")
    switch_steps = main_trials[main_trials["step_type"] != "copy"]
    switching = switch_steps.assign(switch_time=switch_steps["t_first_correct"] - switch_steps["t_cue"])
    print(switching.groupby(["condition", "step_type"])["switch_time"].describe())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("사용법: python analyze.py <로그 CSV 경로>")
    main(sys.argv[1])
