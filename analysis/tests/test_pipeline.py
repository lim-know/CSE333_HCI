"""실행: analysis 폴더에서 python -m unittest discover -s tests"""
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ANALYSIS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANALYSIS))

import analyze  # noqa: E402
import make_sample_data  # noqa: E402
from build_steps import build_steps  # noqa: E402
from logdata import (  # noqa: E402
    EVENT_COLUMNS, SCHEMA_VERSION, SCRIPT_COLUMNS, Dataset, load_dataset, parse_detail,
)
from replay_thresholds import replay  # noqa: E402
from validate_log import validate  # noqa: E402

SAMPLE = ANALYSIS.parent / "data" / "sample"


class Log:
    """테스트용 이벤트 작성기: 시각을 직접 지정한다."""

    def __init__(self, condition="C3", phase="main", exp="exp2", script_id="T", block=1):
        self.meta = dict(schema_version=SCHEMA_VERSION, session_id="P01-1", participant="P01",
                         block=block, condition=condition, phase=phase, exp=exp, script_id=script_id)
        self.rows, self.seq = [], 0

    def add(self, t, event, **fields):
        self.seq += 1
        row = dict.fromkeys(EVENT_COLUMNS)
        row.update(self.meta)
        row.update(seq=self.seq, t_event=float(t), t_logged=float(t) + 1, event=event, **fields)
        self.rows.append(row)
        return self

    def start(self, t=0.0):
        return self.add(t, "block_start", detail="build=t;still_px=12;still_ms=120;epoch_ms=1")

    def ink(self, t, step, slot, size):
        self.add(t, "pointerdown", step_id=step, pointer_id=1, pointer_type="pen", x=1.0, y=1.0, n_touch=0, n_still=0)
        self.add(t, "ink_start", step_id=step, slot=slot, size=size)
        self.add(t + 50, "pointerup", step_id=step, pointer_id=1, pointer_type="pen", x=2.0, y=1.0)
        return self.add(t + 50, "ink_end", step_id=step, slot=slot, size=size)

    def frame(self):
        frame = pd.DataFrame(self.rows, columns=EVENT_COLUMNS).assign(source_file="events_test.csv")
        return frame.astype({c: "float64" for c in ("slot", "size", "n_touch", "n_still", "x", "y", "pointer_id")})


def script(*steps, script_id="T", exp="exp2"):
    rows = []
    for step_id, step_type, slot, size in steps:
        language = "ko" if step_type == "copy" else None
        rows.append(dict.fromkeys(SCRIPT_COLUMNS) | dict(
            script_id=script_id, step_id=step_id, exp=exp, step_type=step_type,
            task_type="t", language=language, target_slot=slot, target_size=size))
    frame = pd.DataFrame(rows, columns=SCRIPT_COLUMNS)
    return frame.astype({"target_slot": "float64", "target_size": "float64"})


SESSIONS = pd.DataFrame([dict(session_id="P01-1", participant="P01", condition_order="C2-C3-C1")])


def steps_of(log, spec):
    return build_steps(log.frame(), spec, SESSIONS)


class BuildStepsTest(unittest.TestCase):
    def test_splits_time_into_phases(self):
        log = Log().start()
        log.ink(100, None, 1, 1.0)
        log.add(1000, "cue_shown", step_id="s1", slot=1, size=1.0)
        log.add(1400, "activation", step_id="s1", slot=1, size=1.0, n_touch=3, n_still=3)
        log.add(1900, "gesture_commit", step_id="s1", slot=3, size=2.0)
        log.ink(2200, "s1", 3, 2.0)
        log.add(2400, "step_end", step_id="s1", detail="outcome=completed")
        row = steps_of(log, script(("s1", "switch_size", 3, 2.0))).iloc[0]
        self.assertEqual(row.time_cue_to_correct, 1200)
        self.assertEqual(row.time_prev_ink_to_correct, 2200 - 150)
        self.assertEqual(row.time_reaction, 400)
        self.assertEqual(row.time_manipulate, 500)
        self.assertEqual(row.time_acquire, 300)
        self.assertEqual((row.start_slot, row.start_size), (1, 1.0))
        self.assertEqual(row.order_index, 2)

    def test_first_attempt_is_separate_from_first_correct(self):
        log = Log().start()
        log.add(1000, "cue_shown", step_id="s1", slot=1, size=1.0)
        log.ink(1500, "s1", 2, 8.0)   # 슬롯, 굵기 모두 틀림
        log.ink(1800, "s1", 3, 8.0)   # 굵기만 틀림
        log.ink(2500, "s1", 3, 2.0)
        log.add(2600, "step_end", step_id="s1", detail="outcome=completed")
        row = steps_of(log, script(("s1", "switch_size", 3, 2.0))).iloc[0]
        self.assertEqual(row.t_first_ink, 1500)
        self.assertEqual(row.t_first_correct, 2500)
        self.assertEqual((row.first_slot, row.first_size), (2, 8.0))
        self.assertEqual((row.n_wrong_slot, row.n_wrong_size), (1, 2))
        self.assertEqual(row.first_size_log2_err, 2.0)
        self.assertEqual(row.final_size_log2_err, 0.0)

    def test_unresolved_step_stays_in_the_denominator(self):
        log = Log().start()
        log.add(1000, "cue_shown", step_id="s1", slot=1, size=1.0)
        log.ink(1500, "s1", 2, 8.0)
        log.add(9000, "step_end", step_id="s1", detail="outcome=timeout")
        steps = steps_of(log, script(("s1", "switch_size", 3, 2.0)))
        row = steps.iloc[0]
        self.assertEqual(row.outcome, "timeout")
        self.assertTrue(pd.isna(row.time_cue_to_correct))
        summary = analyze.switching_summary(steps).iloc[0]
        self.assertEqual((summary.n_steps, summary.n_resolved, summary.n_unresolved), (1, 0, 1))

    def test_exp1_and_exp2_are_not_pooled(self):
        rows = []
        for block, exp, script_id, duration in ((1, "exp1", "E1", 9000), (2, "exp2", "E2", 1000)):
            log = Log(exp=exp, script_id=script_id, block=block).start()
            log.add(0, "cue_shown", step_id="s1", slot=1, size=1.0)
            log.ink(duration, "s1", 1, 2.0)
            log.add(duration + 100, "step_end", step_id="s1", detail="outcome=completed")
            rows.append(steps_of(log, script(("s1", "size_only", None, 2.0), script_id=script_id, exp=exp)))
        summary = analyze.switching_summary(pd.concat(rows))
        self.assertEqual(summary.loc[("exp1", "size_only", "C3"), "median_ms"], 9000)
        self.assertEqual(summary.loc[("exp2", "size_only", "C3"), "median_ms"], 1000)

    def test_eaten_stroke_without_slot_change_counts_as_unintended(self):
        log = Log().start()
        log.add(1000, "cue_shown", step_id="c1", slot=1, size=1.0)
        log.add(1100, "pointerdown", step_id="c1", pointer_id=1, pointer_type="pen", x=1.0, y=1.0, n_touch=1, n_still=1)
        log.add(1100, "activation", step_id="c1", slot=1, size=1.0, n_touch=1, n_still=1)
        log.add(1200, "pointerup", step_id="c1", pointer_id=1, pointer_type="pen", x=1.0, y=1.0)
        log.ink(1300, "c1", 1, 1.0)
        log.add(1400, "step_end", step_id="c1", detail="outcome=completed")
        row = steps_of(log, script(("c1", "copy", None, None))).iloc[0]
        self.assertEqual(row.n_unintended, 1)
        self.assertEqual(row.n_pen_downs, 2)
        self.assertEqual(row.n_ink, 1)
        self.assertTrue(pd.isna(row.t_first_correct))

    def test_activation_in_a_switch_step_is_not_unintended(self):
        log = Log().start()
        log.add(1000, "cue_shown", step_id="s1", slot=1, size=1.0)
        log.add(1100, "activation", step_id="s1", slot=1, size=1.0, n_touch=2, n_still=2)
        log.ink(1300, "s1", 2, 1.0)
        log.add(1400, "step_end", step_id="s1", detail="outcome=completed")
        row = steps_of(log, script(("s1", "switch_only", 2, None))).iloc[0]
        self.assertEqual((row.n_activations, row.n_unintended), (1, 0))

    def test_size_tolerance_uses_ratio_on_both_sides(self):
        for size, expected_correct in ((2.1, True), (1.85, True), (2.3, False), (1.7, False)):
            log = Log().start()
            log.add(1000, "cue_shown", step_id="s1", slot=1, size=1.0)
            log.ink(1500, "s1", 1, size)
            log.add(1600, "step_end", step_id="s1", detail="outcome=completed")
            row = steps_of(log, script(("s1", "size_only", None, 2.0))).iloc[0]
            self.assertEqual(pd.notna(row.t_first_correct), expected_correct, size)

    def test_possible_missed_only_in_switch_steps(self):
        for step_type, slot, expected in (("switch_only", 2, 1), ("copy", None, 0)):
            log = Log().start()
            log.add(1000, "cue_shown", step_id="s1", slot=1, size=1.0)
            log.add(1100, "pointerdown", step_id="s1", pointer_id=1, pointer_type="pen", x=1.0, y=1.0, n_touch=2, n_still=0)
            log.add(1200, "step_end", step_id="s1", detail="outcome=completed")
            row = steps_of(log, script(("s1", step_type, slot, None))).iloc[0]
            self.assertEqual(row.n_possible_missed, expected, step_type)

    def test_parse_detail(self):
        self.assertEqual(parse_detail("outcome=timeout;still_px=12"), {"outcome": "timeout", "still_px": "12"})
        self.assertEqual(parse_detail(None), {})


class ReplayTest(unittest.TestCase):
    def _log(self):
        log = Log().start()
        log.add(0, "pointerdown", pointer_id=10, pointer_type="touch", x=0.0, y=0.0)
        log.add(50, "pointermove", pointer_id=10, pointer_type="touch", x=15.0, y=0.0)
        log.add(100, "pointerdown", pointer_id=11, pointer_type="touch", x=99.0, y=0.0)
        log.add(200, "pointerdown", pointer_id=1, pointer_type="pen", x=5.0, y=5.0, n_touch=2, n_still=0)
        return log

    def test_thresholds_change_the_count_without_recollecting(self):
        events = self._log().frame()
        self.assertEqual(replay(events, 12, 120).iloc[0].n_still_replay, 0)  # 이동 초과, 유지 시간 부족
        self.assertEqual(replay(events, 20, 120).iloc[0].n_still_replay, 1)  # 첫 손가락만 정지
        self.assertEqual(replay(events, 20, 80).iloc[0].n_still_replay, 2)
        self.assertEqual(replay(events, 12, 80).iloc[0].n_still_replay, 1)

    def test_lifted_finger_is_not_counted(self):
        log = self._log()
        log.add(250, "pointerup", pointer_id=1, pointer_type="pen", x=5.0, y=5.0)
        log.add(260, "pointerup", pointer_id=11, pointer_type="touch", x=99.0, y=0.0)
        log.add(600, "pointerdown", pointer_id=1, pointer_type="pen", x=5.0, y=5.0, n_touch=1, n_still=0)
        result = replay(log.frame(), 20, 80)
        self.assertEqual(result.iloc[1].n_touch, 1)


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.data = load_dataset(SAMPLE)

    def _errors(self):
        return validate(self.data)[0]

    def test_sample_is_valid(self):
        self.assertEqual(self._errors(), [])

    def test_detects_missing_step_end(self):
        events = self.data.events
        index = events[events["event"] == "step_end"].index[0]
        self.data.events = events.drop(index)
        self.assertTrue(any("step_end 없음" in e for e in self._errors()))

    def test_detects_crashed_block(self):
        events = self.data.events
        first = events.iloc[0]
        same = (events["session_id"] == first["session_id"]) & (events["block"] == first["block"])
        cut = (events["event"] == "cue_shown") & same
        last_cue_seq = events.loc[cut, "seq"].max()
        self.data.events = events[~(same & (events["seq"] >= last_cue_seq))]
        errors = self._errors()
        self.assertTrue(any("지시가 나오지 않은 단계" in e for e in errors))
        self.assertTrue(any("block_end" in e for e in errors))

    def test_detects_duplicate_seq(self):
        events = self.data.events.copy()
        events.loc[events.index[1], "seq"] = events.loc[events.index[0], "seq"]
        self.data.events = events
        self.assertTrue(any("seq 중복" in e for e in self._errors()))

    def test_detects_wrong_schema_version(self):
        events = self.data.events.copy()
        events["schema_version"] = "0.9"
        self.data.events = events
        self.assertTrue(any("schema_version" in e for e in self._errors()))

    def test_detects_non_korean_native_speaker(self):
        participants = self.data.participants.copy()
        participants.loc[participants.index[0], "native_language"] = "en"
        self.data.participants = participants
        self.assertTrue(any("모국어" in e for e in self._errors()))

    def test_detects_step_outside_script(self):
        events = self.data.events.copy()
        cue = events[events["event"] == "cue_shown"].index[0]
        events.loc[cue, "step_id"] = "zzz"
        self.data.events = events
        self.assertTrue(any("스크립트에 없는 단계" in e for e in self._errors()))


class SampleTest(unittest.TestCase):
    def test_generator_matches_committed_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_sample_data.main(tmp)
            generated = sorted(p.relative_to(tmp) for p in Path(tmp).rglob("*.csv"))
            committed = sorted(p.relative_to(SAMPLE) for p in SAMPLE.rglob("*.csv"))
            self.assertEqual(generated, committed)
            for relative in generated:
                self.assertEqual((Path(tmp) / relative).read_bytes(), (SAMPLE / relative).read_bytes(), relative)

    def test_sample_contains_the_intended_edge_cases(self):
        data = load_dataset(SAMPLE)
        steps = build_steps(data.events, data.scripts, data.sessions)
        key = ["participant", "condition", "exp", "step_id"]
        indexed = steps.set_index(key)
        self.assertEqual(indexed.loc[("P00", "C3", "exp2", "s03"), "n_wrong_slot"], 1)
        self.assertEqual(indexed.loc[("P00", "C3", "exp2", "s04"), "n_unintended"], 1)
        self.assertEqual(indexed.loc[("P00", "C3", "exp2", "s05"), "n_possible_missed"], 1)
        unresolved = indexed.loc[("P01", "C3", "exp2", "s05")]
        self.assertEqual(unresolved["outcome"], "timeout")
        self.assertTrue(pd.isna(unresolved["time_cue_to_correct"]))
        self.assertEqual(indexed.loc[("P01", "C2", "exp2", "s02"), "n_pointercancel"], 1)
        self.assertEqual(set(steps.loc[steps["step_type"] == "copy", "language"]), {"ko", "en"})


if __name__ == "__main__":
    unittest.main()
