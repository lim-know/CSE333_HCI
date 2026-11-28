"""구글 폼 설문 응답(CSV)을 분석용 questionnaire.csv 로 바꾼다.

폼은 tools/questionnaire-form.gs 로 만든다. 참가자는 조건이 끝날 때마다 한 번씩, 모두 세 번 낸다.
폼은 조건 이름을 묻지 않고 "방금 끝난 방법이 몇 번째인지"만 묻는다. 조건은 그 세션의 조건 순서로 찾는다:
1. 데이터 폴더의 sessions.csv 에 그 참가자의 condition_order 가 있으면 그것 (실제로 쓴 순서)
2. 없으면 참가자 번호로 배정표(validate_log.ORDERS)에서 찾는다

NASA-TLX 는 폼에서 0~10 으로 받으므로 10을 곱해 0~100 으로 맞춘다 (분석 계획 5장).
선호 순위는 1~3 (1 = 가장 선호).

사용법:
    1. 구글 폼 → 응답 → 점 세 개 → "응답 다운로드(.csv)" (zip 이면 풀기)
    2. python form_to_questionnaire.py <응답.csv> [--data ../data/raw]
       → <데이터 폴더>/questionnaire.csv 를 새로 쓴다 (응답 CSV 전체로 매번 다시 만든다)

P00(테스트)는 뺀다. 같은 참가자·같은 순번이 두 번 있으면 나중 응답을 쓰고 주의를 띄운다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

from logdata import PREFERENCE_ITEM, QUESTIONNAIRE_COLUMNS, TLX_ITEMS
from validate_log import expected_order

# 폼 문항 제목 → 분석 항목 (questionnaire-form.gs 의 TLX 와 같은 순서·제목)
TLX_TITLES = dict(zip(["정신적 요구", "신체적 요구", "시간적 요구", "수행", "노력", "좌절감"], TLX_ITEMS))
TLX_SCALE = 10                          # 폼 0~10 → 0~100
PARTICIPANT_TITLE = "참가자 번호"
ORDER_TITLE = "방금 끝난 방법은 몇 번째인가요?"
ORDER_CHOICES = {"첫 번째": 0, "두 번째": 1, "세 번째 (마지막)": 2}
PREFERENCE_TITLE = "선호 순위"
# 선호 순위 표의 행(방법 설명)에 들어 있는 말 → 조건
METHOD_KEYS = {"슬라이더": "C1", "손가락 굵기": "C2", "손가락 개수": "C3"}
RANKS = {"1위": 1, "2위": 2, "3위": 3}


def _preference_columns(columns: list[str]) -> dict[str, str]:
    """'선호 순위 [툴바 + 슬라이더 (...)]' 같은 열 → 조건."""
    out = {}
    for column in columns:
        match = re.fullmatch(rf"{PREFERENCE_TITLE} \[(.*)\]", column.strip())
        if not match:
            continue
        hits = [cond for key, cond in METHOD_KEYS.items() if key in match.group(1)]
        if len(hits) != 1:
            raise ValueError(f"선호 순위 열의 방법을 알 수 없음: {column}")
        out[column] = hits[0]
    return out


def session_orders(data_root: Path | None) -> dict[str, list[str]]:
    """sessions.csv 의 참가자별 실제 조건 순서. 없으면 빈 사전."""
    if data_root is None or not (data_root / "sessions.csv").exists():
        return {}
    sessions = pd.read_csv(data_root / "sessions.csv", dtype=str)
    return {row.participant.upper(): row.condition_order.split("-")
            for row in sessions.itertuples() if isinstance(row.condition_order, str)}


def convert(responses: pd.DataFrame, orders: dict[str, list[str]]) -> tuple[pd.DataFrame, list[str]]:
    """응답 표 → (questionnaire 긴 형식, 주의 목록)."""
    warnings: list[str] = []
    missing = [t for t in [PARTICIPANT_TITLE, ORDER_TITLE, *TLX_TITLES] if t not in responses.columns]
    if missing:
        raise ValueError(f"응답 CSV에 없는 열: {missing} (폼 문항 제목이 바뀌었으면 이 파일의 대응표를 고친다)")
    pref_columns = _preference_columns(list(responses.columns))

    rows = []
    seen: dict[tuple[str, int], int] = {}
    for index, r in responses.iterrows():
        participant = str(r[PARTICIPANT_TITLE]).strip().upper()
        if participant == "P00":
            continue
        position = ORDER_CHOICES.get(str(r[ORDER_TITLE]).strip())
        if position is None:
            warnings.append(f"{index + 2}행 {participant}: 순번 '{r[ORDER_TITLE]}'을 알 수 없음 → 뺌")
            continue
        order = orders.get(participant)
        if order is None:
            assigned = expected_order(participant)
            if assigned is None:
                warnings.append(f"{index + 2}행: 참가자 번호 '{participant}'를 알 수 없음 → 뺌")
                continue
            order = assigned[0].split("-")
            if orders:
                warnings.append(f"{participant}: sessions.csv에 없음 → 배정표 순서 {assigned[0]}로 봄")
        condition = order[position]
        key = (participant, position)
        if key in seen:
            warnings.append(f"{participant} {position + 1}번째 응답이 두 번 있음 → 나중 것({index + 2}행) 사용")
            rows = [row for row in rows if row["_key"] != key]
        seen[key] = index
        for title, item in TLX_TITLES.items():
            rows.append({"participant": participant, "condition": condition, "item": item,
                         "value": float(r[title]) * TLX_SCALE, "_key": key})
        ranks = {cond: RANKS.get(str(r[col]).strip()) for col, cond in pref_columns.items()}
        if position == 2:
            if sorted(v for v in ranks.values() if v is not None) != [1, 2, 3]:
                warnings.append(f"{participant}: 선호 순위가 1·2·3위로 하나씩이 아님 {ranks} → 순위 뺌")
            else:
                rows += [{"participant": participant, "condition": cond, "item": PREFERENCE_ITEM,
                          "value": float(rank), "_key": key} for cond, rank in ranks.items()]

    out = pd.DataFrame(rows, columns=[*QUESTIONNAIRE_COLUMNS, "_key"]).drop(columns="_key")
    for participant, group in out.groupby("participant"):
        got = set(group.loc[group["item"].isin(TLX_ITEMS), "condition"])
        if got != {"C1", "C2", "C3"}:
            warnings.append(f"{participant}: TLX가 있는 조건 {sorted(got)} (세 조건이 다 있어야 H5에 들어감)")
        if not (group["item"] == PREFERENCE_ITEM).any():
            warnings.append(f"{participant}: 선호 순위 없음")
    out = out.sort_values(["participant", "condition", "item"], ignore_index=True)
    return out, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("responses", help="구글 폼에서 내려받은 응답 CSV")
    parser.add_argument("--data", default="../data/raw", help="데이터 폴더 (sessions.csv 를 읽고 questionnaire.csv 를 씀)")
    args = parser.parse_args(argv)

    root = Path(args.data)
    responses = pd.read_csv(args.responses, dtype=str, encoding="utf-8-sig")
    out, warnings = convert(responses, session_orders(root))
    root.mkdir(parents=True, exist_ok=True)
    out.to_csv(root / "questionnaire.csv", index=False, lineterminator="\n")
    for message in warnings:
        print(f"[주의] {message}")
    print(f"questionnaire.csv: 참가자 {out['participant'].nunique()}명, {len(out)}행 → {root / 'questionnaire.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
