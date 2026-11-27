"""Count & Tune 로그 분석 (담당: 정원준). 로그 형식 v1.2, 분석 계획 docs/analysis-plan.md.

사용법:
    python analyze.py <데이터 폴더> [출력 폴더, 기본값 analysis/output]

순서:
1. 로그 점검 (validate_log). 오류가 있으면 분석하지 않는다.
2. 단계 표 만들기 (build_steps) → 제외·이상치 표시 (stats.prepare)
3. 6장 참가자 제외 규칙 확인: 해당자가 있으면 알리고 그 참가자를 빼고 분석한다 (보충 모집 대상)
4. H1~H5 검정과 보조 분석을 화면에 출력하고, 표를 출력 폴더에 CSV로 저장한다

출력 폴더에는 참가자별 값이 들어가므로 커밋하지 않는다 (analysis/output/ 은 .gitignore 에 있다).
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd

import stats
from build_steps import build_steps
from logdata import load_dataset
from validate_log import validate


def _show(title: str, value) -> None:
    print(f"\n[{title}]")
    if isinstance(value, (pd.DataFrame, pd.Series)):
        print(value.round(4).to_string())
    else:
        print(value)


def _report(name: str, result: dict, out: Path) -> None:
    """가설 하나의 결과를 출력하고, 표마다 <가설>_<항목>.csv 로 저장한다."""
    print(f"\n========== {name} ==========")
    for key, value in result.items():
        if isinstance(value, dict):
            _report(f"{name} {key}", value, out)
            continue
        if isinstance(value, list):
            if value:
                print(f"\n[{key}] 세 조건 중 빈 칸이 있어 빠진 참가자: {value}")
            continue
        _show(key, value)
        if isinstance(value, (pd.DataFrame, pd.Series)):
            value.to_csv(out / f"{name.replace(' ', '_')}_{key}.csv")


def main(root: str, out_dir: str | None = None) -> int:
    out = Path(out_dir) if out_dir else Path(__file__).resolve().parent / "output"
    out.mkdir(parents=True, exist_ok=True)
    data = load_dataset(root)
    errors, warnings = validate(data)
    print(f"로그 점검: 오류 {len(errors)}건, 주의 {len(warnings)}건 (자세한 내용: python validate_log.py {root})")
    for message in errors:
        print(f"[오류] {message}")
    if errors:
        return 1

    steps = build_steps(data.events, data.scripts, data.sessions)
    steps.to_csv(out / "steps.csv", index=False)
    prepared = stats.prepare(steps)
    print(f"참가자 {prepared['participant'].nunique()}명, 본과제 {len(prepared)}단계 "
          f"(build: {sorted(map(str, prepared['build'].dropna().unique()))})")

    exclusions = stats.exclusion_table(prepared)
    _show("6장 제외 단계 (조건별)", exclusions)
    exclusions.to_csv(out / "exclusions.csv")
    drop = stats.participants_to_drop(prepared)
    if len(drop):
        _show("6장 규칙: 한 조건에서 25% 넘게 빠진 참가자 → 분석에서 빼고 같은 순서로 보충 모집", drop)
        drop.to_csv(out / "participants_dropped.csv", index=False)
        prepared = prepared[~prepared["participant"].isin(drop["participant"])]

    _report("H1", stats.h1(prepared), out)
    _report("H2", stats.h2(prepared), out)
    # 6장 민감도: 앞선 본문 획이 없는 단계(블록 맨 앞 표시)를 빼도 결론이 같은지
    _report("민감도_H1", stats.h1(stats.without_fallback(prepared)), out)
    _report("민감도_H2", stats.h2(stats.without_fallback(prepared)), out)
    _report("H3", stats.h3(prepared), out)
    _report("H4", stats.h4(prepared), out)
    h5 = stats.h5(data.questionnaire[~data.questionnaire["participant"].isin(drop.get("participant", []))])
    if h5:
        _report("H5", h5, out)
    else:
        print("\n[H5] questionnaire.csv 가 없어 건너뜀")

    _show("보조: 시간 나누기 (중앙값, ms)", stats.components(prepared))
    _report("보조_순서효과", stats.order_effect(prepared), out)
    print(f"\n표 저장: {out}")
    return 0


if __name__ == "__main__":
    # 값이 모두 같은 칸(예: 오류 0)에서 scipy·pingouin 이 0으로 나누기 경고를 많이 낸다.
    # 결과표에는 NaN 으로 남으므로 화면 경고만 끈다.
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    if len(sys.argv) not in (2, 3):
        sys.exit("사용법: python analyze.py <데이터 폴더> [출력 폴더]")
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None))
