"""가설 검정 (docs/analysis-plan.md 5·6장). build_steps.py 가 만든 단계 표를 받는다.

방침 (analysis-plan.md 1장):
- 가설마다 조건(C1·C2·C3) 하나짜리 one-way 반복측정. two-way 는 쓰지 않는다.
- 참가자 × 조건 한 칸에 값 하나. 시간은 로그로 바꾼 뒤 평균한다 (= 기하평균).
- 시간은 RM-ANOVA 가 주, Friedman 으로 확인. 오류·설문(H4·H5)은 비모수가 주.
- 사후 비교는 가설 하나 안에서만 Holm 보정.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pingouin as pg

from logdata import PREFERENCE_ITEM, TLX_ITEMS

TIME = "time_prev_ink_to_correct"   # 주 지표: 이전 상태 마지막 획 끝 → 목표 상태 첫 획
OUTLIER_MAD = 3.0                   # 6장: 참가자 × 조건 × 단계 종류 안에서 로그 시간이 중앙값 ± 3 MAD 밖
MAD_SCALE = 1.4826                  # MAD 를 정규분포 표준편차와 같은 단위로 맞추는 상수 (Leys et al., 2013 관례)
MAX_EXCLUDED_SHARE = 0.25           # 6장: 한 조건에서 본과제 단계의 25% 넘게 빠지면 그 참가자를 뺀다
TOST_BOUND = np.log(1.25)           # H2 동등성 마진: 로그 시간 차이 ±ln(1.25)
NONINF_MARGIN = np.log2(1.10)       # H3 비열등성 마진: 굵기 허용 범위와 같은 폭
# H4 의 '의도치 않은 발동' 정의. 파일럿 영상과 맞춰 본 뒤 확정한다 (analysis-plan.md 4.3).
# 잠정: 후보 ① 되돌린 발동 (build_steps 의 n_gesture_reverted. 펜 없이 슬롯이 바뀐 뒤 되돌린 경우도 포함)
UNINTENDED_COLUMNS = ["n_gesture_reverted"]
CONDITION_ORDER = ["C1", "C2", "C3"]


# ---------- 제외와 이상치 (6장) ----------

def prepare(steps: pd.DataFrame) -> pd.DataFrame:
    """본과제 단계만 남기고, 시간 분석에 쓸 수 있는지(time_ok)와 이상치(is_outlier)를 표시한다.

    time_ok 인 단계: 끝까지 맞춘 단계(completed), 바꿀 게 있던 단계, 정답 획까지 시간이 있는 단계.
    timeout·skipped·not_reached 는 시간에서 빠지고 오류·완료율에는 남는다.
    """
    main = steps[steps["phase"] == "main"].copy()
    main["needs_change"] = main["needs_change"].astype("boolean").fillna(True).astype(bool)
    main["prev_ink_fallback"] = main["prev_ink_fallback"].astype("boolean").fillna(False).astype(bool)
    main["time_ok"] = (
        (main["outcome"] == "completed") & main["needs_change"] & (main[TIME] > 0)
    )
    main["log_t"] = np.where(main["time_ok"], np.log(main[TIME].where(main[TIME] > 0)), np.nan)
    main["is_outlier"] = False
    for _, group in main[main["time_ok"]].groupby(["participant", "condition", "step_type", "task_type"]):
        center = group["log_t"].median()
        spread = MAD_SCALE * (group["log_t"] - center).abs().median()
        if spread > 0:
            main.loc[group.index, "is_outlier"] = (group["log_t"] - center).abs() > OUTLIER_MAD * spread
    main["used_for_time"] = main["time_ok"] & ~main["is_outlier"]
    return main


def without_fallback(prepared: pd.DataFrame) -> pd.DataFrame:
    """6장 민감도 분석: 앞선 본문 획이 없어 지시 시각을 기준으로 쓴 단계를 시간 분석에서 뺀다."""
    out = prepared.copy()
    out["used_for_time"] = out["used_for_time"] & ~out["prev_ink_fallback"]
    return out


def exclusion_table(prepared: pd.DataFrame) -> pd.DataFrame:
    """조건별로 시간 분석에서 빠진 단계 수와 이유 (8장 보고용 표)."""
    p = prepared
    reasons = pd.DataFrame({
        "condition": p["condition"],
        "전체": 1,
        "skipped_참가자완료": (p["outcome"] == "skipped") & (p["skipped_by"] == "participant"),
        "skipped_진행자": (p["outcome"] == "skipped") & (p["skipped_by"] == "experimenter"),
        "timeout": p["outcome"] == "timeout",
        "not_reached": p["outcome"] == "not_reached",
        "바꿀것없음": (p["outcome"] == "completed") & ~p["needs_change"],
        "이상치": p["is_outlier"],
        "앞선본문획없음(포함)": p["prev_ink_fallback"] & p["time_ok"],
        "시간분석사용": p["used_for_time"],
    })
    return reasons.groupby("condition").sum(numeric_only=True).astype(int)


def participants_to_drop(prepared: pd.DataFrame) -> pd.DataFrame:
    """한 조건에서 본과제 단계의 25% 넘게 시간 분석에서 빠진 참가자 (보충 모집 대상)."""
    share = 1 - prepared.groupby(["participant", "condition"])["used_for_time"].mean()
    bad = share[share > MAX_EXCLUDED_SHARE].rename("excluded_share").reset_index()
    return bad


# ---------- 공통 ----------

def cell_means(prepared: pd.DataFrame, step_type: str, dv: str = "log_t") -> pd.DataFrame:
    """가설 하나에 쓸 표: 참가자 × 조건마다 값 하나 (긴 형식). 본문 복귀(return) 단계는 보조 분석으로 뺀다."""
    use = prepared[(prepared["task_type"] != "return") & (prepared["step_type"] == step_type)
                   & prepared["used_for_time"]]
    return use.groupby(["participant", "condition"], as_index=False)[dv].mean()


def complete_cases(cells: pd.DataFrame, dv: str) -> tuple[pd.DataFrame, list[str]]:
    """세 조건 모두 값이 있는 참가자만 남긴다. RM-ANOVA 는 빈 칸이 있으면 그 참가자 전체가 빠진다 (6장)."""
    wide = cells.pivot(index="participant", columns="condition", values=dv)
    keep = wide.dropna().index
    dropped = sorted(set(wide.index) - set(keep))
    return cells[cells["participant"].isin(keep)], dropped


def one_way(cells: pd.DataFrame, dv: str, parametric: bool = True) -> dict:
    """조건 하나짜리 반복측정 분석. parametric=True 면 RM-ANOVA + 대응 t(Holm), 항상 Friedman + Wilcoxon(Holm)."""
    common = dict(data=cells, dv=dv, within="condition", subject="participant")
    out = {
        "friedman": pg.friedman(**common),
        "pairs_np": pg.pairwise_tests(**common, parametric=False, padjust="holm"),
    }
    if parametric:
        # correction=True: 구형성이 깨졌을 때 쓰는 Greenhouse-Geisser 보정 p값(p_GG_corr)도 같이 낸다
        out["anova"] = pg.rm_anova(**common, correction=True, effsize="ng2")
        out["pairs"] = pg.pairwise_tests(**common, padjust="holm", effsize="hedges")
    return out


def wide(cells: pd.DataFrame, dv: str) -> pd.DataFrame:
    return cells.pivot(index="participant", columns="condition", values=dv)


def descriptives(cells: pd.DataFrame, dv: str, back_transform: bool = False) -> pd.DataFrame:
    """조건별 평균·표준편차·n. back_transform=True 면 로그 평균을 ms 로 되돌린 기하평균도 낸다."""
    table = cells.groupby("condition")[dv].agg(["mean", "std", "count"]).reindex(CONDITION_ORDER)
    if back_transform:
        table["geo_mean_ms"] = np.exp(table["mean"])
    return table


# ---------- 가설 (5장) ----------

def h1(prepared: pd.DataFrame) -> dict:
    """H1 펜+굵기 단계: C3가 C1·C2보다 빠름. switch_size 표시 단계의 로그 전환 시간."""
    cells, dropped = complete_cases(cell_means(prepared, "switch_size"), "log_t")
    return {"desc": descriptives(cells, "log_t", True), "dropped": dropped, **one_way(cells, "log_t")}


def h2(prepared: pd.DataFrame) -> dict:
    """H2 굵기만 단계: C2 ≈ C3 (TOST), 둘 다 C1보다 빠름. size_only 표시 단계의 로그 전환 시간."""
    cells, dropped = complete_cases(cell_means(prepared, "size_only"), "log_t")
    result = {"desc": descriptives(cells, "log_t", True), "dropped": dropped, **one_way(cells, "log_t")}
    # H2 는 C1–C2, C1–C3 만 본다 → 세 쌍 표에서 그 두 쌍만 Holm 으로 다시 보정한다
    w = wide(cells, "log_t")
    pairs = []
    for a, b in (("C1", "C2"), ("C1", "C3")):
        test = pg.ttest(w[a], w[b], paired=True)
        pairs.append({"A": a, "B": b, "T": test["T"].iloc[0], "dof": test["dof"].iloc[0],
                      "p_unc": test["p_val"].iloc[0] if "p_val" in test else test["p-val"].iloc[0],
                      "hedges": pg.compute_effsize(w[a], w[b], paired=True, eftype="hedges")})
    pairs = pd.DataFrame(pairs)
    pairs["p_holm"] = pg.multicomp(pairs["p_unc"].to_numpy(), method="holm")[1]
    result["pairs_h2"] = pairs
    # C2 ≈ C3 동등성. pval < .05 이면 "차이가 ±ln(1.25) 안"이라고 말할 수 있다
    result["tost"] = pg.tost(w["C2"], w["C3"], bound=TOST_BOUND, paired=True)
    return result


def first_attempt_cells(prepared: pd.DataFrame) -> pd.DataFrame:
    """H3: 굵기를 바꾸는 표시 단계의 첫 시도. 참가자 × 조건마다 |log2 오차| 평균과 첫 시도 정답률."""
    use = prepared[prepared["step_type"].isin(["switch_size", "size_only"]) & (prepared["task_type"] != "return")
                   & prepared["needs_change"] & prepared["first_size_log2_err"].notna()].copy()
    use["abs_log2_err"] = use["first_size_log2_err"].abs()
    use["first_correct"] = use["first_correct"].astype(float)
    return use.groupby(["participant", "condition"], as_index=False)[["abs_log2_err", "first_correct"]].mean()


def h3(prepared: pd.DataFrame) -> dict:
    """H3 굵기 오차: C3가 C1보다 나쁘지 않음 (비열등성, 단측). 확인용: 첫 시도 정답률 Friedman."""
    cells, dropped = complete_cases(first_attempt_cells(prepared), "abs_log2_err")
    w = wide(cells, "abs_log2_err")
    # 귀무: (C3 − C1) ≥ margin. C3 에서 margin 을 빼고 C1 과 단측(less) 대응 t 검정
    noninf = pg.ttest(w["C3"] - NONINF_MARGIN, w["C1"], paired=True, alternative="less")
    return {
        "desc": descriptives(cells, "abs_log2_err").join(
            cells.groupby("condition")["first_correct"].mean().rename("first_correct_rate")),
        "dropped": dropped,
        "noninferiority": noninf,
        "friedman_first_correct": pg.friedman(data=cells, dv="first_correct", within="condition",
                                              subject="participant"),
    }


def error_cells(prepared: pd.DataFrame, unintended: list[str] = UNINTENDED_COLUMNS) -> pd.DataFrame:
    """H4: 참가자 × 조건마다 필기 영역 펜 다운 100회당 (오답 획 + 의도치 않은 발동).

    timeout·skipped 단계도 넣는다 (6장: 오류에는 넣는다). not_reached 는 기록이 없어 빠진다.
    """
    use = prepared[prepared["outcome"] != "not_reached"]
    sums = use.groupby(["participant", "condition"])[
        ["n_wrong_strokes", "n_pen_downs", "n_gesture_reverted", "n_gesture_no_change",
         "n_penless_slot_change"]].sum()
    sums["n_unintended"] = sums[unintended].sum(axis=1)
    sums["errors_per_100"] = 100 * (sums["n_wrong_strokes"] + sums["n_unintended"]) / sums["n_pen_downs"].replace(0, np.nan)
    return sums.reset_index()


def h4(prepared: pd.DataFrame) -> dict:
    """H4 모드 오류: C3가 C1보다 많음 (예상되는 비용). Friedman → Wilcoxon (Holm)."""
    cells, dropped = complete_cases(error_cells(prepared), "errors_per_100")
    components = cells.groupby("condition")[
        ["n_wrong_strokes", "n_gesture_reverted", "n_gesture_no_change", "n_penless_slot_change", "n_pen_downs"]
    ].sum().reindex(CONDITION_ORDER)
    return {"desc": descriptives(cells, "errors_per_100"), "components": components, "dropped": dropped,
            **one_way(cells, "errors_per_100", parametric=False)}


def h5(questionnaire: pd.DataFrame) -> dict:
    """H5 작업 부하: C3가 낮고 선호됨. Raw TLX(6문항 평균)와 선호 순위, 둘 다 Friedman → Wilcoxon (Holm)."""
    if questionnaire.empty:
        return {}
    q = questionnaire.copy()
    q["value"] = pd.to_numeric(q["value"], errors="coerce")
    tlx = (q[q["item"].isin(TLX_ITEMS)].groupby(["participant", "condition"], as_index=False)["value"].mean()
           .rename(columns={"value": "tlx_raw"}))
    rank = (q[q["item"] == PREFERENCE_ITEM][["participant", "condition", "value"]]
            .rename(columns={"value": "preference_rank"}))
    tlx, dropped_tlx = complete_cases(tlx, "tlx_raw")
    rank, dropped_rank = complete_cases(rank, "preference_rank")
    out = {"tlx_desc": descriptives(tlx, "tlx_raw"), "dropped_tlx": dropped_tlx,
           "rank_desc": descriptives(rank, "preference_rank"), "dropped_rank": dropped_rank,
           "tlx_items": q[q["item"].isin(TLX_ITEMS)].groupby(["item", "condition"])["value"].mean().unstack()}
    out["tlx"] = one_way(tlx, "tlx_raw", parametric=False)
    out["rank"] = one_way(rank, "preference_rank", parametric=False)
    return out


# ---------- 보조 분석 (가설 검정 아님) ----------

def components(prepared: pd.DataFrame) -> pd.DataFrame:
    """반응 / 조작 / 획 시작으로 나눈 시간의 조건 × 단계 종류별 중앙값 (어디서 시간이 드는지)."""
    use = prepared[prepared["used_for_time"]]
    return use.groupby(["step_type", "task_type", "condition"])[
        ["time_reaction", "time_manipulate", "time_acquire", TIME]].median().round(0)


def order_effect(prepared: pd.DataFrame) -> dict:
    """조건 순서상 위치(첫째·둘째·셋째)를 요인으로 본 전환 시간 one-way (H1·H2 단계 합쳐서)."""
    use = prepared[prepared["used_for_time"] & (prepared["task_type"] != "return")]
    cells = use.groupby(["participant", "order_index"], as_index=False)["log_t"].mean()
    cells = cells.rename(columns={"order_index": "condition"})   # one_way 가 condition 열을 쓴다
    cells["condition"] = cells["condition"].astype(int).astype(str)
    cells, _ = complete_cases(cells, "log_t")
    return {"desc": cells.groupby("condition")["log_t"].mean().pipe(np.exp).rename("geo_mean_ms"),
            "anova": pg.rm_anova(data=cells, dv="log_t", within="condition", subject="participant")}
