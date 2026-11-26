"""원시 이벤트 + 단계표(script) → 단계별 분석 표(steps). 로그 형식 v1.2 (제시문형 과제) 기준.

판정 기준은 이 파일에만 둔다. 기준이 바뀌면 재수집 없이 다시 실행하면 된다.
정의는 docs/analysis-plan.md 4장과 같다. 바꾸면 그 문서도 같이 고친다.

사용법:
    python build_steps.py <데이터 폴더> [출력 CSV 경로]

한 단계 안의 시각 (analysis-plan.md 4.1):

    이전 상태로 필기 ... [이전 상태 마지막 획 끝] → [첫 조작] ... [마지막 조작] → [목표 상태 첫 획 시작]
                          t_prev_ink_end          t_first_action  t_last_action   t_first_correct

- 이전 상태: 바로 앞 단계의 목표 상태 (블록 첫 단계는 본문 상태 = 검정 1pt).
  앞 단계를 못 끝냈으면(skipped·timeout) 그 단계가 끝날 때의 펜 상태. 브라우저(task.js)와 같은 규칙이다.
- t_prev_ink_end: 목표 상태 첫 획보다 앞에서, **이전 상태로 그은 마지막 획**이 끝난 때.
  제시문형에서는 지시가 뜬 뒤에도 본문을 이어 쓰고, 조작을 해 보다가 되돌려 본문을 더 쓰기도 해서
  (11/20 파일럿) "본문을 마지막으로 쓴 때"를 기준점으로 잡는다. 블록 안에 그런 획이 없으면 지시 시각(cue_shown)을 쓰고
  prev_ink_fallback=True 로 표시한다 (6장 민감도 분석).
- 조작: 펜 상태를 바꾸려는 입력. 툴바 누름, 슬라이더, 제스처(펜 다운 activation, 확정 gesture_commit,
  손가락만으로 생긴 슬롯 변경). C2·C3 제스처의 시작 시각은 그 제스처를 만든 손가락이 닿은 때로 본다.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from logdata import BASE_STATE, block_builds, canvas_pen_downs, load_dataset, parse_detail

# 잠정값: 파일럿 후 확정 (analysis-plan.md 7장). 브라우저 task.js 의 SIZE_TOL 과 같아야 한다.
SIZE_TOL_RATIO = 1.10   # 목표 굵기 대비 이 비율 안이면 같은 굵기

# 펜 상태를 바꾸려는 입력. slot_change 는 손가락만으로 생긴 것(source=gesture)만 조작으로 본다
# (툴바 slot_change 는 toolbar_tap 과 같은 순간이라 겹친다).
ACTION_EVENTS = {"toolbar_tap", "slider_start", "slider_end", "activation", "gesture_commit"}
GESTURE_START_EVENTS = {"activation", "slot_change"}
ERASER_BUTTONS = 32 | 2   # 펜 옆 버튼을 누른 채 그으면 지우개 (script.js erasing())


def same_size(size: float, target: float) -> bool:
    if pd.isna(size) or pd.isna(target) or size <= 0 or target <= 0:
        return False
    ratio = size / target
    return 1 / SIZE_TOL_RATIO <= ratio <= SIZE_TOL_RATIO


def same_state(slot: float, size: float, state: tuple[float, float] | None) -> bool:
    """펜 상태 비교: 슬롯이 같고 굵기가 허용 범위 안이면 같다 (task.js sameState 와 같은 규칙)."""
    if state is None:
        return False
    return slot == state[0] and same_size(size, state[1])


def _in_state(strokes: pd.DataFrame, state: tuple[float, float]) -> np.ndarray:
    """획 표에서 주어진 펜 상태로 그은 획인지 (불리언 배열). 빈 표에서도 안전하다."""
    return np.array([same_state(s.slot, s.size, state) for s in strokes.itertuples()], dtype=bool)


def _log2_error(size: float, target: float) -> float:
    if pd.isna(size) or pd.isna(target) or size <= 0:
        return np.nan
    return float(np.log2(size / target))


# ---------- 블록 단위 전처리 ----------

def _strokes(block: pd.DataFrame) -> pd.DataFrame:
    """ink_start 와 그 뒤 ink_end 를 짝지어 획 표를 만든다. 끝이 없는 획(블록이 끊긴 경우)은 t_end=NaN."""
    rows = []
    current = None
    for row in block[block["event"].isin(["ink_start", "ink_end"])].itertuples():
        if row.event == "ink_start":
            if current is not None:
                rows.append(current)
            current = {"step_id": row.step_id, "t_start": row.t_event, "t_end": np.nan,
                       "slot": row.slot, "size": row.size}
        elif current is not None:
            current["t_end"] = row.t_event
            rows.append(current)
            current = None
    if current is not None:
        rows.append(current)
    return pd.DataFrame(rows, columns=["step_id", "t_start", "t_end", "slot", "size"])


def _touch_starts(block: pd.DataFrame) -> list[tuple[float, float, float]]:
    """손가락 터치마다 (닿은 시각, 뗀 시각, pointer_id). 떼지 않았으면 뗀 시각 = inf."""
    touches = block[(block["pointer_type"] == "touch")
                    & block["event"].isin(["pointerdown", "pointerup", "pointercancel"])]
    open_: dict[float, float] = {}
    spans = []
    for row in touches.itertuples():
        if row.event == "pointerdown":
            open_[row.pointer_id] = row.t_event
        elif row.pointer_id in open_:
            spans.append((open_.pop(row.pointer_id), row.t_event, row.pointer_id))
    spans += [(t0, np.inf, pid) for pid, t0 in open_.items()]
    return spans


def _finger_down_time(spans: list[tuple[float, float, float]], t: float) -> float:
    """시각 t 에 닿아 있던 손가락 중 가장 먼저 닿은 시각. 없으면 NaN."""
    downs = [t0 for t0, t1, _ in spans if t0 <= t < t1]
    return min(downs) if downs else np.nan


def _gesture_episodes(block: pd.DataFrame, strokes: pd.DataFrame) -> pd.DataFrame:
    """제스처 한 번 = 인식기가 IDLE 를 떠났다가 다시 IDLE 로 돌아올 때까지 (rec_state 이벤트).

    분류 (의도치 않은 발동 후보, analysis-plan.md 4.3):
    - no_change : 펜을 댔지만(activation) 상태가 그대로. 획 하나가 제스처로 먹힌 경우일 수 있다
    - reverted : 상태가 바뀌었는데, 그 뒤 첫 획이 제스처 전 상태 (되돌려서 하던 필기를 이어감)
    - used : 상태가 바뀌었고 바뀐 상태(또는 다른 상태)로 다음 획을 썼다
    - rest : 손가락만 올렸다 뗐다 (activation 도 상태 변화도 없음). 세지 않는다
    penless=True 는 펜을 대지 않고(activation 없음) 손가락만으로 슬롯이 바뀐 경우다 (C3, PR #11 0cf62ef 이후).
    C3 의 펜만 바꾸는 단계에서는 이게 정상적인 조작이므로, penless 이면서 used 가 아닌 것만 후보 ②로 센다.
    """
    rows = []
    state = (BASE_STATE[0], BASE_STATE[1])
    rec = "IDLE"
    episode = None
    for row in block.itertuples():
        # 펜 상태 추적: 상태를 바꾸는 이벤트는 바뀐 뒤의 slot/size 를 남긴다.
        before = state
        if row.event in ("slot_change", "size_change") and pd.notna(row.slot):
            state = (row.slot, row.size)
        if row.event == "slot_change" and row.source == "gesture" and episode is None:
            # C3: IDLE → ARMED 순간의 슬롯 변경이 rec_state 행보다 먼저 남는다.
            episode = {"step_id": row.step_id, "t_start": row.t_event, "before": before,
                       "activation": False, "t_activation": np.nan}
        if row.event == "rec_state":
            if row.rec_state != "IDLE" and rec == "IDLE" and episode is None:
                episode = {"step_id": row.step_id, "t_start": row.t_event, "before": before,
                           "activation": False, "t_activation": np.nan}
            rec = row.rec_state
        if row.event == "activation" and episode is not None and not episode["activation"]:
            episode["activation"] = True
            episode["t_activation"] = row.t_event
        if row.event == "activation" and episode is None:
            # rec_state 가 없는 오래된 로그 대비: activation 을 시작으로 본다.
            episode = {"step_id": row.step_id, "t_start": row.t_event, "before": before,
                       "activation": True, "t_activation": row.t_event}
        if episode is not None and row.event == "rec_state" and row.rec_state == "IDLE":
            episode["t_end"] = row.t_event
            episode["after"] = state
            rows.append(episode)
            episode = None
    if episode is not None:
        episode["t_end"] = np.inf
        episode["after"] = state
        rows.append(episode)

    out = []
    for ep in rows:
        changed = not same_state(ep["after"][0], ep["after"][1], ep["before"])
        later = strokes[strokes["t_start"] > ep["t_end"]] if np.isfinite(ep["t_end"]) else strokes.iloc[0:0]
        if not changed:
            kind = "no_change" if ep["activation"] else "rest"
        elif len(later) and same_state(later.iloc[0]["slot"], later.iloc[0]["size"], ep["before"]):
            kind = "reverted"
        else:
            kind = "used"
        out.append({"step_id": ep["step_id"], "t_start": ep["t_start"], "kind": kind,
                    "penless": not ep["activation"] and changed})
    return pd.DataFrame(out, columns=["step_id", "t_start", "kind", "penless"])


# ---------- 단계 요약 ----------

def _blank_times() -> dict:
    keys = ["t_prev_ink_end", "t_first_action", "t_first_action_event", "t_last_action",
            "t_first_attempt", "t_first_correct", "t_end"]
    return dict.fromkeys(keys, np.nan)


def _summarize_block(block: pd.DataFrame, spec: pd.DataFrame, meta: dict) -> list[dict]:
    block = block.sort_values("seq")
    strokes = _strokes(block)
    spans = _touch_starts(block)
    episodes = _gesture_episodes(block, strokes)
    cues = block[block["event"] == "cue_shown"].drop_duplicates("step_id").set_index("step_id")
    ends = block[block["event"] == "step_end"].drop_duplicates("step_id", keep="last").set_index("step_id")
    seq_next = dict(zip(block["seq"].iloc[:-1], block["event"].iloc[1:]))
    pen_down_rows = block[canvas_pen_downs(block)]

    rows = []
    prev_state = (BASE_STATE[0], BASE_STATE[1])
    for step in spec.sort_values("step_id").itertuples():
        target = (step.target_slot, step.target_size)
        row = {**meta, "step_id": step.step_id, "step_type": step.step_type, "task_type": step.task_type,
               "target_slot": step.target_slot, "target_size": step.target_size, "on_preset": step.on_preset,
               "prev_slot": prev_state[0], "prev_size": prev_state[1],
               # 앞 단계를 건너뛰어 이전 상태가 이미 목표 상태면 바꿀 게 없다 → 시간 분석에서 뺀다
               "needs_change": not same_state(target[0], target[1], prev_state),
               **_blank_times()}
        if step.step_id not in cues.index:
            # 표시를 남긴 채 완료를 눌러 지시가 나오지 않은 단계 (또는 블록이 끊김)
            rows.append({**row, "outcome": "not_reached", "skipped_by": "", "prev_ink_fallback": False})
            continue
        cue = cues.loc[step.step_id]
        t_cue = cue["t_event"]
        in_step = block[block["step_id"] == step.step_id]
        step_strokes = strokes[strokes["step_id"] == step.step_id]

        end = ends.loc[step.step_id] if step.step_id in ends.index else None
        outcome = parse_detail(end["detail"]).get("outcome", "unknown") if end is not None else "missing"
        t_end = end["t_event"] if end is not None else np.nan
        skipped_by = ""
        if outcome == "skipped":
            # 완료를 일찍 누르면 step_end 바로 다음 행이 block_end (log-schema v1.2 4번). 아니면 진행자 건너뛰기.
            skipped_by = "participant" if seq_next.get(end["seq"]) == "block_end" else "experimenter"

        correct = step_strokes[_in_state(step_strokes, target)]
        t_first_correct = correct["t_start"].iloc[0] if len(correct) else np.nan
        horizon = t_first_correct if pd.notna(t_first_correct) else (t_end if pd.notna(t_end) else np.inf)

        # 이전 상태 마지막 획: 블록 전체에서 찾는다 (앞 단계의 정답 획이 이 단계의 '이전 상태' 획이다)
        prev_strokes = strokes[(strokes["t_start"] < horizon).to_numpy() & _in_state(strokes, prev_state)]
        if len(prev_strokes) and pd.notna(prev_strokes["t_end"].iloc[-1]):
            t_prev_ink_end, fallback = prev_strokes["t_end"].iloc[-1], False
        else:
            t_prev_ink_end, fallback = t_cue, True

        window = in_step[(in_step["t_event"] > t_prev_ink_end) & (in_step["t_event"] <= horizon)]
        is_action = window["event"].isin(ACTION_EVENTS) | (
            (window["event"] == "slot_change") & (window["source"] == "gesture"))
        actions = window[is_action]
        t_first_action_event = actions["t_event"].min() if len(actions) else np.nan
        t_last_action = actions["t_event"].max() if len(actions) else np.nan
        t_first_action = t_first_action_event
        if len(actions) and actions.iloc[0]["event"] in GESTURE_START_EVENTS:
            # 제스처는 손가락이 닿은 때부터 조작으로 본다. 본문 획을 쓰는 중에 손가락을 먼저 올렸으면
            # 그 획이 끝난 때(t_prev_ink_end)로 자른다.
            finger = _finger_down_time(spans, t_first_action_event)
            if pd.notna(finger):
                t_first_action = max(finger, t_prev_ink_end)

        # 첫 시도: 이전 상태 마지막 획 뒤의 첫 획 (정답 획일 수도 있다)
        attempts = step_strokes[step_strokes["t_start"] > t_prev_ink_end]
        first = attempts.iloc[0] if len(attempts) else None

        # 오답 획: 이전 상태도 목표 상태도 아닌 펜·굵기로 그은 획. 이전 상태로 쓴 본문 획은 오답이 아니다.
        # 정답 획이 나온 뒤(마지막 단계는 완료 버튼까지 열려 있다)에는 목표 상태만 맞는 상태다 (task.js 와 같음).
        wrong_slot = wrong_size = body = 0
        for s in step_strokes.itertuples():
            if same_state(s.slot, s.size, target):
                continue
            after_correct = pd.notna(t_first_correct) and s.t_start >= t_first_correct
            if not after_correct and same_state(s.slot, s.size, prev_state):
                body += 1
                continue
            if s.slot != target[0]:
                wrong_slot += 1
            else:
                wrong_size += 1

        step_eps = episodes[episodes["step_id"] == step.step_id]
        pen_downs = pen_down_rows[pen_down_rows["step_id"] == step.step_id]
        buttons = pd.to_numeric(pen_downs["buttons"], errors="coerce").fillna(0).astype(int)

        row.update({
            "outcome": outcome,
            "skipped_by": skipped_by,
            "t_cue": t_cue,
            "start_slot": cue["slot"],
            "start_size": cue["size"],
            "t_prev_ink_end": t_prev_ink_end,
            "prev_ink_fallback": fallback,
            "t_first_action": t_first_action,
            "t_first_action_event": t_first_action_event,
            "t_last_action": t_last_action,
            "t_first_attempt": first["t_start"] if first is not None else np.nan,
            "t_first_correct": t_first_correct,
            "t_end": t_end,
            # 주 지표 (H1·H2): 이전 상태 마지막 획 끝 → 목표 상태 첫 획 시작
            "time_prev_ink_to_correct": t_first_correct - t_prev_ink_end,
            "time_cue_to_correct": t_first_correct - t_cue,
            "time_reaction": t_first_action - t_prev_ink_end,
            "time_manipulate": t_last_action - t_first_action,
            "time_acquire": t_first_correct - t_last_action,
            "duration": t_end - t_cue,
            # 첫 시도 (H3): 조작 뒤 첫 획
            "first_slot": first["slot"] if first is not None else np.nan,
            "first_size": first["size"] if first is not None else np.nan,
            "first_correct": bool(first is not None and same_state(first["slot"], first["size"], target)),
            "first_size_log2_err": _log2_error(first["size"], target[1]) if first is not None else np.nan,
            # 오류 (H4)
            "n_ink": len(step_strokes),
            "n_body_strokes": body,
            "n_wrong_slot": wrong_slot,
            "n_wrong_size": wrong_size,
            "n_wrong_strokes": wrong_slot + wrong_size,
            "n_pen_downs": len(pen_downs),
            "n_eraser_downs": int(((buttons & ERASER_BUTTONS) != 0).sum()),
            "n_toolbar_taps": int((in_step["event"] == "toolbar_tap").sum()),
            "n_slider_drags": int((in_step["event"] == "slider_start").sum()),
            "n_activations": int((in_step["event"] == "activation").sum()),
            "n_gestures": int((in_step["event"] == "gesture_commit").sum()),
            "n_gesture_used": int((step_eps["kind"] == "used").sum()),
            "n_gesture_reverted": int((step_eps["kind"] == "reverted").sum()),
            "n_gesture_no_change": int((step_eps["kind"] == "no_change").sum()),
            "n_penless_slot_change": int((step_eps["penless"].astype(bool) & (step_eps["kind"] != "used")).sum()),
            # 손가락이 닿아 있는데 정지로 판정되지 않은 펜 다운: 인식 실패 후보 (펜 pointerdown 줄의 n_still)
            "n_possible_missed": int(((pen_downs["n_touch"] >= 1) & (pen_downs["n_still"] == 0)).sum()),
            "n_pointercancel": int((in_step["event"] == "pointercancel").sum()),
        })
        rows.append(row)

        # 다음 단계의 '이전 상태' (task.js finish() 와 같은 규칙)
        if outcome == "completed":
            prev_state = target
        elif end is not None and pd.notna(end["slot"]):
            prev_state = (end["slot"], end["size"])
    return rows


def build_steps(events: pd.DataFrame, scripts: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    """단계마다 한 줄. 단계표에 있는데 지시가 안 나온 단계도 outcome=not_reached 로 남긴다.

    단계표가 없는 블록(브라우저가 연습 제시문 단계표는 저장하지 않는다)은 건너뛴다.
    """
    orders = {row.session_id: str(row.condition_order).split("-") for row in sessions.itertuples()}
    builds = block_builds(events)
    # pointermove 는 단계 요약에 쓰지 않는다 (행 수가 대부분이라 미리 뺀다)
    events = events[events["event"] != "pointermove"]
    specs = {script_id: frame for script_id, frame in scripts.groupby("script_id")}
    rows = []
    for (session_id, block_no), block in events.groupby(["session_id", "block"], sort=True):
        first = block.iloc[0]
        if first["script_id"] not in specs:
            continue
        order = orders.get(session_id, [])
        meta = {
            "session_id": session_id, "participant": first["participant"], "block": block_no,
            "condition": first["condition"], "phase": first["phase"], "exp": first["exp"],
            "script_id": first["script_id"],
            "order_index": order.index(first["condition"]) + 1 if first["condition"] in order else np.nan,
            "build": builds.get((session_id, block_no), pd.NA),
        }
        rows += _summarize_block(block, specs[first["script_id"]], meta)
    return pd.DataFrame(rows)


def main(root: str, out: str | None) -> None:
    data = load_dataset(root)
    steps = build_steps(data.events, data.scripts, data.sessions)
    if out:
        steps.to_csv(out, index=False)
        print(f"{len(steps)}개 단계 저장: {out}")
    else:
        print(steps.head(20).to_string())


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("사용법: python build_steps.py <데이터 폴더> [출력 CSV 경로]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
