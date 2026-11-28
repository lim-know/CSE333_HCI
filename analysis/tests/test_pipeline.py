"""실행: analysis 폴더에서 python -m unittest discover -s tests

로그 형식 v1.2 (제시문형 과제) 기준. 시각은 테스트마다 직접 지정한다 (ms).
"""
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ANALYSIS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANALYSIS))

import collect  # noqa: E402
import make_sample_data  # noqa: E402
import stats  # noqa: E402
from build_steps import build_steps  # noqa: E402
from logdata import (  # noqa: E402
    EVENT_COLUMNS, SCHEMA_VERSION, SCRIPT_COLUMNS, load_dataset, parse_detail,
)
from replay_thresholds import replay, threshold_table  # noqa: E402
from validate_log import expected_order, validate  # noqa: E402

SAMPLE = ANALYSIS.parent / "data" / "sample"
warnings.filterwarnings("ignore", category=RuntimeWarning)


class Log:
    """테스트용 이벤트 작성기. step 은 지금 단계 (logger 의 stepId 처럼 이후 행에 붙는다)."""

    def __init__(self, condition="C3", phase="main", script_id="T", block=1, build="t"):
        self.meta = dict(schema_version=SCHEMA_VERSION, session_id="P01-1", participant="P01",
                         block=block, condition=condition, phase=phase, exp="exp2", script_id=script_id)
        self.rows, self.seq, self.step = [], 0, ""
        self.add(0, "block_start", detail=f"build={build};still_px=12;still_ms=120;epoch_ms=1")

    def add(self, t, event, **fields):
        self.seq += 1
        row = dict.fromkeys(EVENT_COLUMNS)
        row.update(self.meta)
        row.update(seq=self.seq, t_event=float(t), t_logged=float(t) + 1, event=event, step_id=self.step or None)
        row.update(fields)
        self.rows.append(row)
        return self

    def cue(self, t, step, slot=1, size=1.0):
        self.step = step
        return self.add(t, "cue_shown", slot=slot, size=size)

    def end(self, t, outcome="completed", slot=1, size=1.0):
        self.add(t, "step_end", slot=slot, size=size, detail=f"outcome={outcome}")
        self.step = ""
        return self

    def ink(self, t, slot, size, n_touch=0, n_still=0, length=50):
        self.add(t, "pointerdown", source="canvas", pointer_id=1, pointer_type="pen", x=1.0, y=1.0,
                 n_touch=n_touch, n_still=n_still, buttons=1)
        self.add(t + 1, "ink_start", source="pen", slot=slot, size=size)
        self.add(t + length, "pointerup", source="canvas", pointer_id=1, pointer_type="pen", x=2.0, y=1.0)
        return self.add(t + length + 1, "ink_end", source="pen", slot=slot, size=size)

    def touch(self, t, event, pid=10):
        return self.add(t, event, source="canvas", pointer_id=pid, pointer_type="touch", x=500.0, y=500.0)

    def gesture(self, t_finger, t_pen, slot, size, before, fingers=1, change_slot=False, commit_after=300):
        """손가락 → (C3 슬롯 변경) → ARMED → 펜 다운 activation → 끌기 → 확정 → 손가락 뗌 → IDLE."""
        for i in range(fingers):
            self.touch(t_finger + i, "pointerdown", pid=10 + i)
        if change_slot:
            self.add(t_finger + 130, "slot_change", source="gesture", slot=slot, size=before[1])
        self.add(t_finger + 131, "rec_state", source="gesture", rec_state="ARMED")
        self.add(t_pen, "pointerdown", source="canvas", pointer_id=1, pointer_type="pen", x=1.0, y=1.0,
                 n_touch=fingers, n_still=fingers, buttons=1)
        self.add(t_pen + 1, "activation", source="gesture", slot=slot, size=before[1], n_touch=fingers, n_still=fingers)
        self.add(t_pen + 2, "rec_state", source="gesture", rec_state="TUNING")
        if size != before[1]:
            self.add(t_pen + 100, "size_change", source="gesture", slot=slot, size=size)
        self.add(t_pen + commit_after, "pointerup", source="canvas", pointer_id=1, pointer_type="pen", x=1.0, y=1.0)
        self.add(t_pen + commit_after + 1, "gesture_commit", source="gesture", slot=slot, size=size)
        self.add(t_pen + commit_after + 2, "rec_state", source="gesture", rec_state="ARMED")
        for i in range(fingers):
            self.touch(t_pen + commit_after + 50 + i, "pointerup", pid=10 + i)
        return self.add(t_pen + commit_after + 60, "rec_state", source="gesture", rec_state="IDLE")

    def block_end(self, t):
        self.step = ""
        return self.add(t, "block_end")

    def frame(self):
        frame = pd.DataFrame(self.rows, columns=EVENT_COLUMNS).assign(source_file="events_test.csv")
        numeric = ("slot", "size", "n_touch", "n_still", "x", "y", "pointer_id", "buttons")
        return frame.astype({c: "float64" for c in numeric})


def script(*steps, script_id="T"):
    """steps: (step_id, step_type, task_type, target_slot, target_size)"""
    rows = [dict.fromkeys(SCRIPT_COLUMNS) | dict(
        script_id=script_id, step_id=step_id, exp="exp2", step_type=step_type, task_type=task_type,
        language="ko", target_slot=slot, target_size=size, on_preset=1)
        for step_id, step_type, task_type, slot, size in steps]
    return pd.DataFrame(rows, columns=SCRIPT_COLUMNS).astype({"target_slot": "float64", "target_size": "float64"})


SESSIONS = pd.DataFrame([dict(session_id="P01-1", participant="P01", condition_order="C2-C3-C1")])
ONE_STEP = script(("01", "switch_size", "underline", 2, 4.0))


def steps_of(log, spec=ONE_STEP):
    return build_steps(log.frame(), spec, SESSIONS)


class BuildStepsTest(unittest.TestCase):
    def test_times_are_measured_from_the_last_body_stroke(self):
        log = Log()
        log.cue(1000, "01")
        log.ink(1200, 1, 1.0).ink(1500, 1, 1.0)              # 본문 (이전 상태) 획, 마지막 끝 = 1551
        log.gesture(2000, 2300, 2, 4.0, before=(1, 1.0), fingers=2, change_slot=True)
        log.ink(3000, 2, 4.0)                                 # 정답 획 시작 = 3001
        log.end(3051, slot=2, size=4.0).block_end(3100)
        row = steps_of(log).iloc[0]
        self.assertEqual(row.t_prev_ink_end, 1551)
        self.assertFalse(row.prev_ink_fallback)
        self.assertEqual(row.time_prev_ink_to_correct, 3001 - 1551)
        self.assertEqual(row.time_cue_to_correct, 2001)
        self.assertEqual(row.t_first_action_event, 2130)      # C3 슬롯 변경(손가락 정지)이 첫 조작
        self.assertEqual(row.time_reaction, 2000 - 1551)      # 제스처는 손가락이 닿은 때부터
        self.assertEqual(row.time_acquire, 3001 - 2601)       # 마지막 조작 = gesture_commit
        self.assertEqual(row.n_body_strokes, 2)
        self.assertEqual(row.n_wrong_strokes, 0)
        self.assertTrue(row.first_correct)
        self.assertEqual(row.order_index, 2)

    def test_finger_down_during_a_body_stroke_is_clipped(self):
        log = Log()
        log.cue(1000, "01")
        log.touch(1100, "pointerdown")                        # 본문 획(1200~1251) 전에 손가락이 먼저 닿음
        log.ink(1200, 1, 1.0)
        log.add(1300, "slot_change", source="gesture", slot=2, size=1.0)
        log.add(1301, "rec_state", source="gesture", rec_state="ARMED")
        log.touch(1400, "pointerup").add(1401, "rec_state", source="gesture", rec_state="IDLE")
        log.ink(1600, 2, 4.0)
        log.end(1700).block_end(1800)
        row = steps_of(log, script(("01", "switch_only", "underline", 2, 4.0))).iloc[0]
        self.assertEqual(row.t_first_action, row.t_prev_ink_end)
        self.assertEqual(row.time_reaction, 0)

    def test_body_strokes_are_not_errors_but_wrong_states_are(self):
        log = Log(condition="C1")
        log.cue(1000, "01")
        log.ink(1100, 1, 1.0)                                 # 본문
        log.add(1300, "slot_change", source="toolbar", slot=2, size=1.0).add(1301, "toolbar_tap", source="toolbar", slot=2, size=1.0)
        log.ink(1500, 2, 1.0)                                 # 펜은 맞고 굵기가 틀림 → 첫 시도
        log.add(1700, "slider_start", source="slider").add(1800, "size_change", source="slider", slot=2, size=4.0)
        log.add(1900, "slider_end", source="slider", slot=2, size=4.0)
        log.ink(2100, 2, 4.0)
        log.end(2200, slot=2, size=4.0).block_end(2300)
        row = steps_of(log).iloc[0]
        self.assertEqual((row.n_body_strokes, row.n_wrong_slot, row.n_wrong_size), (1, 0, 1))
        self.assertFalse(row.first_correct)
        self.assertEqual(row.first_size_log2_err, -2.0)       # 1pt / 목표 4pt
        self.assertEqual(row.t_first_attempt, 1501)
        self.assertEqual(row.time_manipulate, 1900 - 1301)

    def test_trying_a_gesture_then_writing_more_body_moves_the_start(self):
        """11/20 파일럿: 블록 시작에 굵기를 안 바꾼 제스처(unchanged) → 본문을 더 씀 → 그 뒤 진짜 전환."""
        log = Log(condition="C2")
        log.cue(1000, "01")
        log.gesture(1100, 1300, 1, 1.0, before=(1, 1.0))      # 굵기 그대로
        log.ink(2000, 1, 1.0)                                 # 본문 (끝 2051)
        log.gesture(2500, 2700, 1, 4.0, before=(1, 1.0))
        log.ink(3200, 1, 4.0)
        log.end(3300, slot=1, size=4.0).block_end(3400)
        row = steps_of(log, script(("01", "size_only", "word", 1, 4.0))).iloc[0]
        self.assertEqual(row.t_prev_ink_end, 2051)
        self.assertEqual(row.t_first_action, 2500)
        self.assertEqual(row.n_gesture_unchanged, 1)
        self.assertEqual(row.n_gesture_used, 1)

    def test_no_previous_stroke_falls_back_to_the_cue(self):
        log = Log()
        log.cue(1000, "01")
        log.gesture(1200, 1400, 2, 4.0, before=(1, 1.0), fingers=2, change_slot=True)
        log.ink(2000, 2, 4.0)
        log.end(2100).block_end(2200)
        row = steps_of(log).iloc[0]
        self.assertTrue(row.prev_ink_fallback)
        self.assertEqual(row.time_prev_ink_to_correct, 1001)

    def test_previous_state_follows_the_previous_target(self):
        spec = script(("01", "size_only", "word", 1, 4.0), ("02", "size_only", "return", 1, 1.0))
        log = Log(condition="C2")
        log.cue(1000, "01").ink(1100, 1, 1.0)
        log.gesture(1300, 1500, 1, 4.0, before=(1, 1.0))
        log.ink(2000, 1, 4.0).end(2051, slot=1, size=4.0)    # 정답 획이 끝나면 다음 단계
        log.cue(2052, "02").ink(2200, 1, 4.0)                 # 표시 단어를 마저 씀 = 02 의 이전 상태 획
        log.gesture(2400, 2600, 1, 1.0, before=(1, 4.0))
        log.ink(3100, 1, 1.0).end(3200).block_end(3300)
        rows = steps_of(log, spec).set_index("step_id")
        self.assertEqual((rows.loc["02", "prev_slot"], rows.loc["02", "prev_size"]), (1, 4.0))
        self.assertEqual(rows.loc["02", "t_prev_ink_end"], 2251)
        self.assertEqual(rows.loc["02", "n_body_strokes"], 1)
        self.assertEqual(rows.loc["02", "n_wrong_strokes"], 0)

    def test_early_done_and_experimenter_skip(self):
        spec = script(("01", "size_only", "word", 1, 4.0), ("02", "size_only", "return", 1, 1.0),
                      ("03", "switch_size", "underline", 2, 2.0))
        # 진행자 건너뛰기: step_end(skipped) 다음이 cue_shown
        log = Log()
        log.cue(1000, "01").ink(1100, 1, 1.0).end(5000, "skipped", slot=1, size=1.0)
        log.cue(5001, "02").ink(5100, 1, 1.0).end(5200)       # 이전 상태(검정 1pt)가 이미 목표 → 바꿀 게 없음
        log.cue(5201, "03").ink(5300, 1, 1.0)
        log.add(5400, "pointerdown", source="ui", pointer_id=1, pointer_type="pen", x=0.0, y=0.0, n_touch=0, n_still=0)
        log.end(5450, "skipped").block_end(5451)              # 참가자가 표시를 남긴 채 완료
        rows = steps_of(log, spec).set_index("step_id")
        self.assertEqual((rows.loc["01", "outcome"], rows.loc["01", "skipped_by"]), ("skipped", "experimenter"))
        self.assertFalse(rows.loc["02", "needs_change"])
        self.assertEqual((rows.loc["03", "outcome"], rows.loc["03", "skipped_by"]), ("skipped", "participant"))
        self.assertEqual(rows.loc["03", "n_pen_downs"], 1)    # 완료 버튼(ui) 펜 탭은 세지 않는다

        spec4 = pd.concat([spec, script(("04", "switch_only", "highlight", 3, 4.0))])
        rows = steps_of(log, spec4).set_index("step_id")
        self.assertEqual(rows.loc["04", "outcome"], "not_reached")

    def test_size_tolerance_uses_ratio_on_both_sides(self):
        for size, expected in ((4.3, True), (3.7, True), (4.5, False), (3.5, False)):
            log = Log(condition="C1")
            log.cue(1000, "01").ink(1100, 1, 1.0)
            log.add(1200, "slot_change", source="toolbar", slot=2, size=size).add(1201, "toolbar_tap", source="toolbar")
            log.ink(1500, 2, size).end(1600).block_end(1700)
            row = steps_of(log).iloc[0]
            self.assertEqual(pd.notna(row.t_first_correct), expected, size)

    def test_penless_slot_change_is_counted_only_when_not_used(self):
        # 옷자락: 손가락만 닿아 슬롯 3으로 바뀌었다가, 되돌리고(검정) 본문을 이어 씀
        log = Log()
        log.cue(1000, "01").ink(1100, 1, 1.0)
        log.touch(1200, "pointerdown", 10).touch(1201, "pointerdown", 11).touch(1202, "pointerdown", 12)
        log.add(1330, "slot_change", source="gesture", slot=3, size=4.0).add(1331, "rec_state", source="gesture", rec_state="ARMED")
        for pid in (10, 11, 12):
            log.touch(1400, "pointerup", pid)
        log.add(1401, "rec_state", source="gesture", rec_state="IDLE")
        log.touch(1500, "pointerdown", 10).add(1630, "slot_change", source="gesture", slot=1, size=1.0)
        log.add(1631, "rec_state", source="gesture", rec_state="ARMED").touch(1700, "pointerup", 10)
        log.add(1701, "rec_state", source="gesture", rec_state="IDLE")
        log.ink(1800, 1, 1.0)
        # 진짜 전환: C3 펜만 바꾸는 단계에서는 손가락만으로 바꾸는 것이 정상 조작 (used)
        log.touch(2000, "pointerdown", 10).touch(2001, "pointerdown", 11)
        log.add(2130, "slot_change", source="gesture", slot=2, size=4.0).add(2131, "rec_state", source="gesture", rec_state="ARMED")
        log.touch(2200, "pointerup", 10).touch(2201, "pointerup", 11).add(2202, "rec_state", source="gesture", rec_state="IDLE")
        log.ink(2400, 2, 4.0).end(2500).block_end(2600)
        row = steps_of(log, script(("01", "switch_only", "underline", 2, 4.0))).iloc[0]
        self.assertEqual(row.n_penless_slot_change, 1)
        self.assertEqual(row.n_gesture_reverted, 1)
        self.assertEqual(row.n_gesture_used, 2)               # 되돌리기 + 진짜 전환
        self.assertEqual(row.t_prev_ink_end, 1851)

    def test_eraser_possible_missed_and_ui_taps(self):
        log = Log()
        log.cue(1000, "01").ink(1100, 1, 1.0)
        log.add(1200, "pointerdown", source="canvas", pointer_id=1, pointer_type="pen", x=1.0, y=1.0,
                n_touch=0, n_still=0, buttons=33)             # 지우개 (옆 버튼 32 + 접촉 1)
        log.ink(1400, 1, 1.0, n_touch=1, n_still=0)           # 손가락이 닿았는데 정지 아님 → 인식 실패 후보
        log.add(1600, "pointerdown", source="ui", pointer_id=1, pointer_type="pen", x=1.0, y=1.0, n_touch=2, n_still=2)
        log.add(1601, "slot_change", source="toolbar", slot=2, size=4.0).add(1602, "toolbar_tap", source="toolbar")
        log.ink(1800, 2, 4.0).end(1900).block_end(2000)
        row = steps_of(log).iloc[0]
        self.assertEqual(row.n_eraser_downs, 1)
        self.assertEqual(row.n_possible_missed, 1)
        self.assertEqual(row.n_pen_downs, 4)                  # 본문 2 + 지우개 1 + 정답 1 (툴바 탭 제외)

    def test_blocks_without_a_script_are_skipped(self):
        log = Log(phase="practice", script_id="practice")
        log.cue(1000, "01").ink(1100, 1, 1.0).end(1200).block_end(1300)
        self.assertTrue(steps_of(log).empty)

    def test_parse_detail(self):
        self.assertEqual(parse_detail("outcome=timeout;still_px=12"), {"outcome": "timeout", "still_px": "12"})
        self.assertEqual(parse_detail(None), {})


class ReplayTest(unittest.TestCase):
    def _log(self):
        log = Log()
        log.touch(0, "pointerdown", 10)
        log.add(50, "pointermove", pointer_id=10, pointer_type="touch", x=515.0, y=500.0)
        log.touch(100, "pointerdown", 11)
        log.add(200, "pointerdown", source="canvas", pointer_id=1, pointer_type="pen", x=5.0, y=5.0, n_touch=2, n_still=0)
        return log

    def test_thresholds_change_the_count_without_recollecting(self):
        events = self._log().frame()
        self.assertEqual(replay(events, 12, 120).iloc[0].n_still_replay, 0)  # 이동 초과, 유지 시간 부족
        self.assertEqual(replay(events, 20, 120).iloc[0].n_still_replay, 1)  # 첫 손가락만 정지
        self.assertEqual(replay(events, 20, 80).iloc[0].n_still_replay, 2)
        self.assertEqual(replay(events, 12, 80).iloc[0].n_still_replay, 1)

    def test_touch_to_pen_window_drops_resting_fingers(self):
        events = self._log().frame()
        self.assertEqual(replay(events, 20, 80).iloc[0].touch_to_pen_ms, 100)
        self.assertEqual(replay(events, 20, 80, touch_to_pen_ms=150).iloc[0].n_still_replay, 1)
        self.assertEqual(replay(events, 20, 80, touch_to_pen_ms=250).iloc[0].n_still_replay, 2)

    def test_threshold_table_splits_switch_and_writing(self):
        data = load_dataset(SAMPLE)
        steps = build_steps(data.events, data.scripts, data.sessions)
        table = threshold_table(data.events, steps, [(12, 120)], [None, 1]).set_index("touch_to_pen_ms")
        self.assertGreater(table.loc["없음", "switch_인식"], 0)
        self.assertEqual(table.loc["없음", "writing_인식"], 1)   # P01 C2 exp2B_0 의 unchanged 제스처
        self.assertEqual(table.loc["1", "switch_인식"], 0)


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.data = load_dataset(SAMPLE)

    def _check(self):
        return validate(self.data)

    def test_sample_is_valid(self):
        errors, warnings_ = self._check()
        self.assertEqual(errors, [])
        self.assertTrue(any("연습 블록 단계표" in w for w in warnings_))
        self.assertTrue(any("완료를 일찍 누름" in w for w in warnings_))

    def test_detects_missing_step_end(self):
        events = self.data.events
        self.data.events = events.drop(events[events["event"] == "step_end"].index[0])
        self.assertTrue(any("step_end 없음" in e for e in self._check()[0]))

    def test_detects_crashed_block(self):
        events = self.data.events
        main = events[(events["phase"] == "main")]
        key = main.iloc[0][["session_id", "block"]]
        same = (events["session_id"] == key["session_id"]) & (events["block"] == key["block"])
        last_cue = events.loc[same & (events["event"] == "cue_shown"), "seq"].max()
        self.data.events = events[~(same & (events["seq"] >= last_cue))]
        errors = self._check()[0]
        self.assertTrue(any("지시가 나오지 않은 단계" in e for e in errors))
        self.assertTrue(any("block_end" in e for e in errors))

    def test_detects_two_builds_in_one_session(self):
        events = self.data.events.copy()
        start = events[(events["event"] == "block_start") & (events["session_id"] == "P01-1")].index[-1]
        events.loc[start, "detail"] = events.loc[start, "detail"].replace("build=sample", "build=exp-2026-11-21")
        self.data.events = events
        self.assertTrue(any("build 가 여러 개" in e for e in self._check()[0]))

    def test_warns_on_unknown_build(self):
        events = self.data.events.copy()
        is_start = events["event"] == "block_start"
        events.loc[is_start, "detail"] = events.loc[is_start, "detail"].str.replace("build=sample", "build=exp-new")
        self.data.events = events
        errors, warnings_ = self._check()
        self.assertEqual(errors, [])
        self.assertTrue(any("처음 보는 build" in w for w in warnings_))

    def test_warns_when_order_differs_from_the_assignment(self):
        sessions = self.data.sessions.copy()
        sessions.loc[0, "condition_order"] = "C3-C2-C1"
        self.data.sessions = sessions
        self.assertTrue(any("배정표와 다른 순서" in w for w in self._check()[1]))
        self.assertEqual(expected_order("P03"), ("C1-C3-C2", "A-B-C"))
        self.assertEqual(expected_order("P13"), ("C1-C2-C3", "A-B-C"))

    def test_detects_duplicate_seq(self):
        events = self.data.events.copy()
        events.loc[events.index[1], "seq"] = events.loc[events.index[0], "seq"]
        self.data.events = events
        self.assertTrue(any("seq 중복" in e for e in self._check()[0]))

    def test_detects_wrong_schema_version(self):
        self.data.events = self.data.events.assign(schema_version="0.9")
        self.assertTrue(any("schema_version" in e for e in self._check()[0]))

    def test_detects_non_korean_native_speaker(self):
        participants = self.data.participants.copy()
        participants.loc[participants.index[0], "native_language"] = "en"
        self.data.participants = participants
        self.assertTrue(any("모국어" in e for e in self._check()[0]))

    def test_detects_unknown_task_type(self):
        scripts = self.data.scripts.copy()
        scripts.loc[scripts.index[0], "task_type"] = "copy"
        self.data.scripts = scripts
        self.assertTrue(any("task_type" in e for e in self._check()[0]))

    def test_detects_pen_down_without_source(self):
        events = self.data.events.copy()
        pen_down = events[(events["event"] == "pointerdown") & (events["pointer_type"] == "pen")].index[0]
        events.loc[pen_down, "source"] = pd.NA
        self.data.events = events
        self.assertTrue(any("source" in e for e in self._check()[0]))

    def test_missing_questionnaire_is_only_a_warning(self):
        self.data.questionnaire = self.data.questionnaire.iloc[0:0]
        errors, warnings_ = self._check()
        self.assertEqual(errors, [])
        self.assertTrue(any("questionnaire.csv 없음" in w for w in warnings_))


class CollectTest(unittest.TestCase):
    def test_duplicates_and_merges(self):
        sample_events = sorted((SAMPLE / "events").glob("events_*.csv"))
        with tempfile.TemporaryDirectory() as tmp:
            download, out = Path(tmp) / "dl", Path(tmp) / "raw"
            download.mkdir()
            first, second = sample_events[0], sample_events[1]
            (download / first.name).write_bytes(first.read_bytes())
            (download / first.name.replace(".csv", " (1).csv")).write_bytes(first.read_bytes())   # 같은 내용
            full = second.read_bytes()
            cut = b"\n".join(full.split(b"\n")[:5]) + b"\n"                                       # 끊긴 사본
            (download / second.name).write_bytes(cut)
            (download / second.name.replace(".csv", " (1).csv")).write_bytes(full)
            script_file = next((SAMPLE / "scripts").glob("script_*.csv"))
            (download / script_file.name).write_bytes(script_file.read_bytes())
            sessions = pd.read_csv(SAMPLE / "sessions.csv", dtype=str)
            sessions.iloc[[0]].to_csv(download / "session_P01-1.csv", index=False)
            pd.read_csv(SAMPLE / "participants.csv", dtype=str).iloc[[0]].to_csv(
                download / "participant_P01.csv", index=False)

            self.assertEqual(collect.collect(download, out), 0)
            self.assertEqual(sorted(p.name for p in (out / "events").iterdir()), [first.name, second.name])
            self.assertEqual((out / "events" / second.name).read_bytes(), full)   # block_end 가 있는 사본
            self.assertEqual(len(pd.read_csv(out / "sessions.csv")), 1)
            self.assertEqual(collect.collect(download, out), 0)                    # 다시 돌려도 그대로
            self.assertEqual(len(pd.read_csv(out / "sessions.csv")), 1)

            (out / "events" / first.name).write_bytes(cut)                          # 출력 쪽이 다르면 덮어쓰지 않음
            self.assertEqual(collect.collect(download, out), 1)
            self.assertEqual((out / "events" / first.name).read_bytes(), cut)


class StatsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = load_dataset(SAMPLE)
        cls.steps = build_steps(data.events, data.scripts, data.sessions)
        cls.prepared = stats.prepare(cls.steps)
        cls.questionnaire = data.questionnaire

    def test_time_is_used_only_for_completed_steps_that_needed_a_change(self):
        p = self.prepared
        self.assertTrue((p.loc[p["used_for_time"], "outcome"] == "completed").all())
        self.assertFalse(p.loc[~p["needs_change"], "used_for_time"].any())
        self.assertTrue((p["phase"] == "main").all())

    def test_outlier_rule(self):
        frame = pd.DataFrame({
            "phase": "main", "participant": "P01", "condition": "C1", "step_type": "size_only",
            "task_type": "word", "outcome": "completed", "needs_change": True, "prev_ink_fallback": False,
            stats.TIME: [1000, 1050, 980, 1020, 9000],
        })
        flagged = stats.prepare(frame)["is_outlier"].tolist()
        self.assertEqual(flagged, [False, False, False, False, True])

    def test_participant_drop_rule(self):
        frame = self.prepared.copy()
        frame.loc[(frame["participant"] == "P01") & (frame["condition"] == "C1"), "used_for_time"] = False
        drop = stats.participants_to_drop(frame)
        self.assertEqual(drop[["participant", "condition"]].values.tolist(), [["P01", "C1"]])
        self.assertTrue(stats.participants_to_drop(self.prepared).empty)

    def test_drop_rule_ignores_no_change_steps(self):
        """블록 첫 본문(no_change)은 원래 시간을 안 재므로 25% 분모에 넣지 않는다."""
        frame = pd.DataFrame({
            "participant": "P01", "condition": "C1",
            "step_type": ["no_change", "size_only", "size_only", "switch_size"],
            "used_for_time": [False, True, True, True],
        })
        self.assertTrue(stats.participants_to_drop(frame).empty)   # 분모에 넣으면 25% (경계)
        frame.loc[1, "used_for_time"] = False
        self.assertEqual(len(stats.participants_to_drop(frame)), 1)   # 1/3 제외

    def test_cells_are_one_value_per_participant_and_condition(self):
        cells = stats.cell_means(self.prepared, "switch_size")
        self.assertFalse(cells.duplicated(["participant", "condition"]).any())
        self.assertEqual(len(cells), 4 * 3)

    def test_hypotheses_run_on_the_sample(self):
        h1 = stats.h1(self.prepared)
        self.assertIn("p_GG_corr", h1["anova"].columns)
        self.assertEqual(len(h1["pairs"]), 3)
        h2 = stats.h2(self.prepared)
        self.assertEqual(h2["pairs_h2"][["A", "B"]].values.tolist(), [["C1", "C2"], ["C1", "C3"]])
        self.assertIn("pval", h2["tost"].columns)
        h3 = stats.h3(self.prepared)
        self.assertEqual(h3["noninferiority"]["alternative"].iloc[0], "less")
        h4 = stats.h4(self.prepared)
        self.assertGreater(h4["components"].loc["C3", "n_wrong_strokes"], 0)
        h5 = stats.h5(self.questionnaire)
        self.assertEqual(h5["rank_desc"].loc["C1", "mean"], 3)
        self.assertEqual(stats.h5(self.questionnaire.iloc[0:0]), {})

    def test_error_rate_counts_unintended_activations(self):
        cells = stats.error_cells(self.prepared).set_index(["participant", "condition"])
        row = cells.loc[("P02", "C3")]
        self.assertEqual(row["n_gesture_reverted"], 1)       # 옷자락 사례
        self.assertEqual(row["n_unintended"], 1)
        expected = 100 * (row["n_wrong_strokes"] + row["n_unintended"]) / row["n_pen_downs"]
        self.assertAlmostEqual(row["errors_per_100"], expected)

    def test_sensitivity_drops_fallback_steps(self):
        sens = stats.without_fallback(self.prepared)
        self.assertFalse(sens.loc[sens["prev_ink_fallback"], "used_for_time"].any())
        self.assertTrue(self.prepared.loc[self.prepared["prev_ink_fallback"], "used_for_time"].any())


class SampleTest(unittest.TestCase):
    def test_generator_matches_committed_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_sample_data.main(tmp)
            generated = sorted(p.relative_to(tmp) for p in Path(tmp).rglob("*.csv"))
            committed = sorted(p.relative_to(SAMPLE) for p in SAMPLE.rglob("*.csv"))
            self.assertEqual(generated, committed)
            for relative in generated:
                self.assertEqual((Path(tmp) / relative).read_bytes(), (SAMPLE / relative).read_bytes(), relative)

    def test_passage_steps_match_passage_js_rules(self):
        steps = make_sample_data.passage_steps(make_sample_data.PASSAGES[0])
        self.assertEqual([s["task_type"] for s in steps],
                         ["return", "word", "return", "word", "return", "underline", "highlight"])
        self.assertEqual([s["step_type"] for s in steps],
                         ["no_change", "size_only", "size_only", "size_only", "size_only", "switch_size",
                          "switch_size"])
        # 표시로 시작하면 no_change 가 없다 (실제 exp2B_1 과 같은 경우)
        steps = make_sample_data.passage_steps(make_sample_data.PASSAGES[1])
        self.assertEqual([s["task_type"] for s in steps], ["word", "return", "circle", "highlight"])

    def test_sample_contains_the_intended_edge_cases(self):
        data = load_dataset(SAMPLE)
        steps = build_steps(data.events, data.scripts, data.sessions)
        s = steps.set_index(["participant", "condition", "script_id", "step_id"])
        self.assertEqual(s.loc[("P01", "C3", "exp2C_0", "03"), "n_wrong_slot"], 1)
        self.assertFalse(s.loc[("P01", "C3", "exp2C_0", "03"), "first_correct"])
        self.assertEqual(s.loc[("P01", "C3", "exp2C_0", "05"), "n_possible_missed"], 1)
        self.assertEqual(s.loc[("P01", "C2", "exp2B_0", "01"), "n_gesture_unchanged"], 1)
        self.assertEqual(s.loc[("P02", "C3", "exp2C_0", "02"), "n_penless_slot_change"], 1)
        self.assertEqual(s.loc[("P02", "C1", "exp2A_1", "03"), "skipped_by"], "participant")
        self.assertEqual(s.loc[("P02", "C1", "exp2A_1", "04"), "outcome"], "not_reached")
        self.assertEqual(s.loc[("P03", "C2", "exp2C_0", "04"), "skipped_by"], "experimenter")
        self.assertEqual(s.loc[("P03", "C1", "exp2A_0", "02"), "n_eraser_downs"], 1)
        self.assertEqual(s.loc[("P04", "C2", "exp2C_1", "02"), "n_pointercancel"], 1)
        no_change = steps[steps["step_type"] == "no_change"]
        self.assertTrue((no_change["step_id"] == "01").all() and not no_change["needs_change"].any())
        fallback = steps[steps["prev_ink_fallback"] & (steps["step_type"] != "no_change")]
        self.assertTrue((fallback["step_id"] == "01").all() and fallback["script_id"].str.endswith("_1").all())
        self.assertTrue(np.isfinite(steps.loc[steps["outcome"] == "completed", "time_prev_ink_to_correct"]).all())


if __name__ == "__main__":
    unittest.main()
