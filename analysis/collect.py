"""브라우저가 내려받은 파일을 분석 폴더 구조로 정리한다. 세션이 끝날 때마다 실행한다.

브라우저(prototype)는 세션 하나에 파일 35개를 다운로드 폴더에 내려받는다 (docs/device-setup.md):
    events_<세션>_bNN.csv   블록마다 1개 (세션당 18개)
    script_<제시문>.csv      조건 끝마다 본과제 제시문 5개 (세션당 15개, 같은 세트면 참가자끼리 내용이 같다)
    session_<세션>.csv       세션 끝에 1개
    participant_<참가자>.csv 세션 끝에 1개

이 스크립트는 그 파일들을 분석 코드(logdata.load_dataset)가 읽는 구조로 옮긴다:
    <출력>/events/events_*.csv
    <출력>/scripts/script_*.csv
    <출력>/sessions.csv        (session_*.csv 를 한 줄씩 합침)
    <출력>/participants.csv    (participant_*.csv 를 합침)

- 원본 파일은 지우거나 바꾸지 않는다 (복사만 한다).
- Chrome 이 같은 이름을 다시 받으면 "events_P01-1_b01 (1).csv" 처럼 번호가 붙는다.
  내용이 같으면 하나로 합치고, 다르면 block_end 가 있는 것 중 행이 가장 많은 것을 쓰고 보고한다.
- 출력 폴더에 같은 이름인데 내용이 다른 파일이 이미 있으면 덮어쓰지 않고 오류로 보고한다.
- 출력 폴더는 참가자 데이터라 커밋하면 안 된다 (기본값 data/raw 는 .gitignore 에 있다).

사용법:
    python collect.py <다운로드 폴더> [출력 폴더, 기본값 ../data/raw]
    예: python collect.py "C:/Users/me/Downloads"
"""
from __future__ import annotations

import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

from logdata import EXPECTED_FILES, PARTICIPANT_COLUMNS, SESSION_COLUMNS, read_csv

PATTERNS = {
    "events": re.compile(r"^(events_(?P<session>.+)_b(?P<block>\d+))(?: \(\d+\))?\.csv$"),
    "script": re.compile(r"^(script_.+?)(?: \(\d+\))?\.csv$"),
    "session": re.compile(r"^(session_(?P<session>.+?))(?: \(\d+\))?\.csv$"),
    "participant": re.compile(r"^(participant_(?P<participant>.+?))(?: \(\d+\))?\.csv$"),
}


def _classify(folder: Path) -> dict[str, dict[str, list[Path]]]:
    """종류 → 원래 이름(번호 뗀 것) → 그 이름의 사본들."""
    found: dict[str, dict[str, list[Path]]] = {kind: defaultdict(list) for kind in PATTERNS}
    for path in sorted(folder.glob("*.csv")):
        for kind, pattern in PATTERNS.items():
            match = pattern.match(path.name)
            if match:
                found[kind][match.group(1) + ".csv"].append(path)
                break
    return found


def _pick_events(copies: list[Path], notes: list[str]) -> Path:
    """같은 블록 사본 중 하나를 고른다. 내용이 모두 같으면 아무거나, 다르면 끝까지 기록된 것."""
    contents = {path.read_bytes() for path in copies}
    if len(contents) == 1:
        return copies[0]
    scored = []
    for path in copies:
        frame = pd.read_csv(path, usecols=["event"])
        scored.append(((frame["event"] == "block_end").any(), len(frame), path))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    chosen = scored[0][2]
    notes.append(f"[주의] 내용이 다른 사본 {len(copies)}개 → {chosen.name} 사용 "
                 f"(block_end 있음={scored[0][0]}, {scored[0][1]}행). 나머지: {[p.name for _, _, p in scored[1:]]}")
    return chosen


def _copy(source: Path, target: Path, errors: list[str]) -> bool:
    """target 이 없으면 복사. 있는데 내용이 같으면 그대로, 다르면 오류 (덮어쓰지 않음)."""
    if target.exists():
        if target.read_bytes() != source.read_bytes():
            errors.append(f"[오류] {target} 가 이미 있고 내용이 다름 → 덮어쓰지 않음 (원본 {source.name})")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def _merge_rows(table_path: Path, new_files: list[Path], columns: list[str], key: str,
                errors: list[str]) -> int:
    """session_*.csv 같은 한 줄짜리 파일들을 key 기준으로 기존 표에 합친다. 추가된 줄 수를 돌려준다."""
    existing = read_csv(table_path, columns) if table_path.exists() else pd.DataFrame(columns=columns)
    added = 0
    for path in new_files:
        frame = read_csv(path, columns)[columns]
        for _, row in frame.iterrows():
            same = existing[existing[key] == row[key]]
            if len(same):
                old = same.iloc[0][columns].fillna("").astype(str).tolist()
                if old != row.fillna("").astype(str).tolist():
                    errors.append(f"[오류] {table_path.name} 에 {key}={row[key]} 가 이미 있고 내용이 다름 "
                                  f"({path.name}) → 그대로 둠. 다시 진행한 세션이면 표를 직접 확인")
                continue
            existing = pd.concat([existing, row.to_frame().T], ignore_index=True)
            added += 1
    if added:
        table_path.parent.mkdir(parents=True, exist_ok=True)
        existing.to_csv(table_path, index=False)
    return added


def collect(download: Path, out: Path) -> int:
    found = _classify(download)
    errors: list[str] = []
    notes: list[str] = []

    # events: 세션별로 블록 번호가 빠짐없이 있는지도 본다
    per_session: dict[str, list[int]] = defaultdict(list)
    copied = defaultdict(int)
    for name, copies in sorted(found["events"].items()):
        match = PATTERNS["events"].match(name)
        per_session[match.group("session")].append(int(match.group("block")))
        chosen = _pick_events(copies, notes) if len(copies) > 1 else copies[0]
        copied["events"] += _copy(chosen, out / "events" / name, errors)
    for name, copies in sorted(found["script"].items()):
        if len({p.read_bytes() for p in copies}) > 1:
            errors.append(f"[오류] {name}: 같은 이름인데 내용이 다른 단계표 사본 → 제시문이 바뀌었는지 확인")
            continue
        copied["script"] += _copy(copies[0], out / "scripts" / name, errors)

    first = lambda groups: [copies[0] for _, copies in sorted(groups.items())]  # noqa: E731
    copied["session"] = _merge_rows(out / "sessions.csv", first(found["session"]), SESSION_COLUMNS,
                                    "session_id", errors)
    copied["participant"] = _merge_rows(out / "participants.csv", first(found["participant"]),
                                        PARTICIPANT_COLUMNS, "participant", errors)

    print(f"다운로드 폴더: {download}")
    print(f"출력 폴더: {out}")
    for kind in PATTERNS:
        print(f"  {kind:12s} 찾음 {len(found[kind]):3d}개 (기대 세션당 {EXPECTED_FILES[kind]}개), 새로 넣음 {copied[kind]}개")
    for session, blocks in sorted(per_session.items()):
        blocks = sorted(blocks)
        missing = sorted(set(range(1, max(blocks) + 1)) - set(blocks))
        status = "OK" if len(blocks) == EXPECTED_FILES["events"] and not missing else "확인 필요"
        print(f"  세션 {session}: events {len(blocks)}개, 빠진 블록 {missing or '없음'} → {status}")
        if status != "OK":
            notes.append(f"[주의] 세션 {session}: events {len(blocks)}개 (기대 {EXPECTED_FILES['events']}개). "
                         "빠진 블록은 끝 화면의 '브라우저에 백업된 블록'에서 다시 받을 수 있는지 확인")
    for session in sorted(set(m.group("session") for n in found["session"]
                              if (m := PATTERNS["session"].match(n))) - set(per_session)):
        notes.append(f"[주의] 세션 {session}: session 파일은 있는데 events 가 없음")
    for message in notes + errors:
        print(message)
    print(f"정리 끝: 오류 {len(errors)}건, 주의 {len(notes)}건. 다음 단계: python validate_log.py {out}")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("사용법: python collect.py <다운로드 폴더> [출력 폴더]")
    default_out = Path(__file__).resolve().parent.parent / "data" / "raw"
    sys.exit(collect(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) == 3 else default_out))
