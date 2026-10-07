import json
import inspect
import unittest
from datetime import date

import coach


RACE = {"name": "HYROX London", "date": "2026-12-02", "target_seconds": 3900,
        "baseline_seconds": 4252, "simulation_date": "2026-11-14", "plan_start": "2026-10-08"}


class CoachTests(unittest.TestCase):
    def setUp(self):
        self.profile = coach.default_profile("Kenza")
        self.today = date(2026, 10, 8)

    def test_plan_dates_and_actual_events(self):
        plan = coach.generate_plan(self.profile, RACE, [], {}, self.today)
        self.assertEqual(len(plan), 56)
        self.assertEqual(plan[0]["date"], "2026-10-08")
        self.assertEqual(plan[-1]["date"], "2026-12-02")
        self.assertEqual(len({x["id"] for x in plan}), 56)
        by_date = {x["date"]: x for x in plan}
        self.assertEqual(by_date["2026-11-14"]["type"], "simulation")
        self.assertNotEqual(by_date["2026-11-13"]["intensity"], "hard")
        self.assertEqual(by_date["2026-11-15"]["type"], "class")
        self.assertEqual(by_date["2026-11-15"]["intensity"], "easy")
        self.assertTrue(by_date["2026-11-15"]["external"])
        self.assertEqual(by_date["2026-11-16"]["type"], "recovery")
        self.assertEqual(by_date["2026-12-02"]["type"], "race")
        self.assertIn("foundation", {x["phase"] for x in plan})
        self.assertIn("taper", {x["phase"] for x in plan})
        for i in range(0, 56, 7):
            self.assertLessEqual(sum(x["intensity"] == "hard" for x in plan[i:i + 7]), 2)
        for i in range(50):
            self.assertLessEqual(sum(x["intensity"] == "hard" for x in plan[i:i + 7]), 2)
        json.dumps(plan, allow_nan=False)

    def test_fatigue_only_changes_near_future_not_history(self):
        now = date(2026, 10, 20)
        baseline = coach.generate_plan(self.profile, RACE, [], {}, now)
        fatigue = coach.generate_plan(self.profile, RACE, [], {"fatigue": 9, "pain": 5}, now)
        for old, new in zip(baseline, fatigue):
            if old["date"] < now.isoformat() or old["date"] > "2026-10-26":
                self.assertEqual(old, new)
        adjusted = next(x for x in fatigue if x["date"] == now.isoformat())
        self.assertEqual(adjusted["type"], "recovery")
        self.assertEqual(adjusted["duration"], 0)
        self.assertIn("adjustment", adjusted)

    def test_missed_workouts_do_not_compensate(self):
        clean = coach.generate_plan(self.profile, RACE, [], {}, self.today)
        missed = coach.generate_plan(self.profile, RACE,
                                     [{"date": "2026-10-08", "status": "missed", "duration": 100, "rpe": 10}],
                                     {}, self.today)
        self.assertEqual(clean, missed)

    def test_external_classes_and_athlete_pace(self):
        self.profile["optional_activities"] = ["BodyAttack", "tennis"]
        self.profile["benchmark_seconds"] = 3000
        self.profile["easy_pace_seconds"] = None
        self.profile["easy_pace"] = "Conversational effort"
        plan = coach.generate_plan(self.profile, RACE, [], {}, self.today)
        self.assertTrue(any("BodyAttack" in x["title"] for x in plan))
        self.assertTrue(any(x["type"] == "tennis" for x in plan))
        self.assertTrue(any("6:15/km" in " ".join(x["main"]) for x in plan))
        self.assertTrue(any("5:15/km" in " ".join(x["main"]) for x in plan))
        self.assertFalse(any(x["type"] == "class" and x["intensity"] == "hard"
                             for x in plan if x["phase"] == "taper"))
        for i in range(0, 56, 7):
            self.assertLessEqual(sum(x["intensity"] == "hard" for x in plan[i:i + 7]), 2)
        for i in range(50):
            self.assertLessEqual(sum(x["intensity"] == "hard" for x in plan[i:i + 7]), 2)

    def test_readiness_completed_only_and_window(self):
        logs = [{"date": "2026-10-08", "duration": 40, "rpe": 8, "status": "completed", "metrics": {"anything": {"x": 1}}},
                {"date": "2026-10-09", "duration": 90, "rpe": 10, "status": "completed"},
                {"date": "2026-10-01", "duration": 90, "rpe": 10, "status": "completed"},
                {"date": "2026-10-08", "duration": 100, "rpe": 10, "status": "missed"}]
        result = coach.readiness(logs, {}, self.today)
        self.assertEqual(result["load_7d"], 320)
        self.assertEqual(result["hard_sessions"], 1)
        self.assertEqual(coach.readiness([], {"pain": 4}, self.today)["color"], "red")
        self.assertEqual(coach.readiness([], {"fatigue": 8}, self.today)["color"], "red")

    def test_invalid_numbers_remain_json_safe(self):
        result = coach.readiness([{"date": "2026-10-08", "duration": float("inf"),
                                   "rpe": float("nan"), "status": "completed"}],
                                 {"pain": float("nan"), "fatigue": float("inf")}, self.today)
        self.assertEqual(result["load_7d"], 0)
        json.dumps(result, allow_nan=False)
        self.assertIsNone(coach.race_scenario(float("nan"), 500, 50)["seconds"])
        self.assertIsNone(coach.race_scenario(1e308, 1e308, 1e308)["seconds"])
        self.assertIsNone(coach.projection({"baseline_seconds": 1e308}, [], [], {})["seconds"])

    def test_projection_no_fabricated_improvement(self):
        projected = coach.projection(RACE, [], [], {})
        self.assertEqual(projected["seconds"], 4252)
        self.assertEqual(projected["status"], "baseline")
        self.assertLess(projected["low"], projected["seconds"])
        self.assertGreater(projected["high"], projected["seconds"])
        simulations = [{"date": "2026-11-14", "total_seconds": 4100},
                       {"date": "2026-10-24", "total_seconds": 4200}]
        self.assertEqual(coach.projection(RACE, simulations, [], {})["seconds"], 4100)
        tired = coach.projection(RACE, simulations, [], {"fatigue": 9})
        fresh = coach.projection(RACE, simulations, [], {})
        self.assertEqual(tired["seconds"], fresh["seconds"])
        self.assertGreater(tired["high"], fresh["high"])
        self.assertIsNone(coach.projection({}, [], [], {})["seconds"])

    def test_simulation_analysis_only_measured_splits(self):
        simulations = [{"date": "2026-10-24", "total_seconds": 4252,
                        "runs": [300, 310], "stations": {"ski": 240, "row": 250}, "transitions": [20]},
                       {"date": "2026-11-14", "total_seconds": 4100,
                        "runs": [290], "stations": {"ski": 220}, "transitions": [18]}]
        result = coach.simulation_analysis(RACE, simulations)
        self.assertEqual(result["improvement"], 152)
        self.assertEqual(result["gap"], 200)
        self.assertEqual(result["split_improvements"]["stations"], {"ski": 20})
        self.assertEqual(result["split_improvements"]["runs"], [{"index": 1, "seconds": 10}])
        absent = coach.simulation_analysis(RACE, [{"date": "2026-11-14", "total_seconds": 4100}])
        self.assertEqual(absent["split_improvements"]["stations"], {})
        self.assertEqual(absent["opportunities"], [])

    def test_strategy_unknown_and_measured(self):
        unknown = coach.strategy({})
        self.assertEqual(len(unknown), 8)
        self.assertTrue(all(x["kenza_share"] is None for x in unknown))
        measurements = {"ski": {"kenza_seconds": 200, "rob_seconds": 300,
                                 "preferred_share": .5, "transition_seconds": 10}}
        result = coach.strategy(measurements)
        self.assertEqual(result[0]["kenza_share"], .5)
        self.assertEqual(result[0]["seconds"], 260)
        self.assertEqual(result[1]["confidence"], "unavailable")
        self.assertIsNone(coach.strategy({"ski": {"kenza_seconds": float("inf"), "rob_seconds": 200}})[0]["seconds"])

    def test_race_scenario_all_eight_kilometres(self):
        result = coach.race_scenario(300, {"ski": 200, "row": 200}, [20, 30])
        self.assertEqual(result["seconds"], 2850)
        self.assertEqual(result["breakdown"]["runs"], 2400)
        self.assertEqual(result["breakdown"]["run_km"], 8)
        self.assertIn("Both partners", result["rationale"])

    def test_weekly_summary_counts_recorded_not_future(self):
        logs = [{"date": "2026-10-08", "status": "completed", "duration": 40, "rpe": 8},
                {"date": "2026-10-09", "status": "completed", "duration": 80, "rpe": 8},
                {"date": "2026-10-07", "status": "missed", "duration": 40, "rpe": 8}]
        plan = coach.generate_plan(self.profile, RACE, [], {}, self.today)
        summary = coach.weekly_summary(logs, plan, self.today)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["duration"], 40)
        self.assertEqual(summary["load"], 320)
        self.assertEqual(summary["missed"], 1)

    def test_safe_reply_and_reference_loads(self):
        response = coach.coach_reply("How much insulin?", self.profile, RACE, [], {}, [])
        self.assertIn("cannot", response["answer"])
        self.assertIn("healthcare", response["answer"])
        self.assertEqual(coach.STATIONS[1]["load"], 152)
        self.assertTrue(coach.STATIONS[1]["includes_sled"])
        self.assertIn("verify", coach.STATIONS[1]["reference"])
        self.assertIsInstance(self.profile["goals"], str)
        self.assertIsInstance(self.profile["fuelling_preferences"], str)

    def test_completed_log_signals_and_current_checkin_precedence(self):
        logs = [{"date": "2026-10-08", "status": "completed", "duration": 20,
                 "rpe": 4, "pain": 5, "sleep": 5, "soreness": 6, "energy": 2}]
        state = coach.readiness(logs, {}, self.today)
        self.assertEqual(state["color"], "red")
        self.assertTrue(any("last recorded pain" in x for x in state["reasons"]))
        recovered = coach.readiness(logs, {"pain": 0, "sleep": 8, "soreness": 0,
                                          "fatigue": 0, "energy": 9}, self.today)
        self.assertEqual(recovered["color"], "green")
        missed = [dict(logs[0], status="missed")]
        self.assertEqual(coach.readiness(missed, {}, self.today)["color"], "green")

    def test_four_readiness_colors_and_public_signatures(self):
        cases = [({}, "green"), ({"fatigue": 6}, "yellow"),
                 ({"fatigue": 6, "soreness": 6}, "orange"), ({"pain": 4}, "red")]
        for checkin, expected in cases:
            self.assertEqual(coach.readiness([], checkin, self.today)["color"], expected)
        expected = {
            "readiness": ["logs", "checkin", "today"],
            "generate_plan": ["profile", "race", "logs", "checkin", "today", "stations"],
            "projection": ["race", "simulations", "logs", "checkin"],
            "simulation_analysis": ["race", "simulations"],
            "strategy": ["measurements", "stations"],
            "race_scenario": ["run_pace_seconds", "station_seconds", "transition_seconds"],
            "coach_reply": ["question", "profile", "race", "logs", "checkin", "simulations"],
            "weekly_summary": ["logs", "plan", "today"],
        }
        for name, parameters in expected.items():
            self.assertEqual(list(inspect.signature(getattr(coach, name)).parameters), parameters)

    def test_custom_station_loads_feed_programming(self):
        stations = [dict(x) for x in coach.STATIONS]
        stations[1]["load"] = 125
        stations[2]["load"] = 85
        plan = coach.generate_plan(self.profile, RACE, [], {}, self.today, stations=stations)
        hyrox = next(x for x in plan if x["type"] == "hyrox")
        text = " ".join(hyrox["main"])
        self.assertIn("Sled push: 125 kg including sled", text)
        self.assertIn("Sled pull: 85 kg including sled", text)
        self.assertNotIn("152", text)
        self.assertEqual(coach.STATIONS[1]["load"], 152)

    def test_projection_comparable_evidence_and_goal_status(self):
        today = date.today().isoformat()
        simulation = {"date": "2026-09-01", "total_seconds": 4252,
                      "stations": {"ski": 240}, "runs": [300] * 8}
        logs = [{"date": today, "status": "completed", "duration": 30, "rpe": 4,
                 "metrics": {"station": "ski", "station_seconds": 220, "distance": 1000,
                             "comparable_to_simulation": "yes"}}]
        result = coach.projection(RACE, [simulation], logs, {})
        self.assertEqual(result["seconds"], 4232)
        self.assertEqual(result["goal_status"], "behind_target")
        self.assertEqual(result["evidence"]["log_adjustment_seconds"], -20)
        logs[0]["metrics"]["distance"] = 500
        self.assertEqual(coach.projection(RACE, [simulation], logs, {})["seconds"], 4252)
        logs[0]["metrics"]["distance"] = 1000
        logs[0]["metrics"]["comparable_to_simulation"] = False
        self.assertEqual(coach.projection(RACE, [simulation], logs, {})["seconds"], 4252)
        self.assertEqual(coach.projection(dict(RACE, baseline_seconds=3900), [], [], {})["goal_status"], "on_track")
        self.assertEqual(coach.projection(dict(RACE, baseline_seconds=3700), [], [], {})["goal_status"], "ahead_target")

    def test_old_fatigue_does_not_widen_current_projection(self):
        old = [{"date": "2026-09-01", "status": "completed", "duration": 80,
                "rpe": 9, "pain": 8, "energy": 1}]
        self.assertEqual(coach.projection(RACE, [], old, {})["high"],
                         coach.projection(RACE, [], [], {})["high"])

    def test_projection_running_evidence_bounded_and_scaled_excluded(self):
        simulation = {"date": "2026-09-01", "total_seconds": 4252, "runs": [300] * 8}
        logs = [{"date": date.today().isoformat(), "status": "completed", "duration": 30,
                 "rpe": 4, "metrics": {"runs": [200] * 8, "run_distance_km": 8, "comparable": True}}]
        result = coach.projection(RACE, [simulation], logs, {})
        self.assertAlmostEqual(result["evidence"]["log_adjustment_seconds"], -127.6)
        self.assertEqual(result["seconds"], 4124)
        logs[0]["metrics"] = {"run_seconds": 1600, "run_distance_km": 8, "comparable": "yes"}
        self.assertEqual(coach.projection(RACE, [simulation], logs, {})["seconds"], 4124)
        self.assertEqual(coach.projection(RACE, [dict(simulation, scaled=True)], [], {})["status"], "baseline")

    def test_custom_race_outside_default_window_is_actual_race_day(self):
        race = dict(RACE, date="2026-12-15")
        plan = coach.generate_plan(self.profile, race, [], {}, self.today)
        self.assertEqual(len(plan), 56)
        self.assertEqual(plan[-1]["date"], "2026-12-15")
        self.assertEqual(plan[-1]["type"], "race")

    def test_seeded_athlete_facts(self):
        kenza, rob = coach.default_profile("Kenza"), coach.default_profile("Rob")
        self.assertEqual(kenza["benchmark_seconds"], 2645)
        self.assertEqual(kenza["benchmark_5k_seconds"], 1330)
        self.assertEqual(kenza["easy_pace"], "5:15–5:30/km, conversational effort")
        self.assertEqual(rob["benchmark_seconds"], 2955)
        self.assertTrue(rob["back_pain_history"])
        self.assertEqual(kenza["station_ratings"]["ski"], "2–3")
        self.assertIn("farmers", kenza["strengths"])
        self.assertIn("burpees", rob["weaknesses"])
        self.assertEqual(kenza["weekend_classes"], {"saturday": "HYROX", "sunday": "HYROX"})

    def test_actual_weekday_schedule_and_thursday_progression(self):
        plan = coach.generate_plan(self.profile, RACE, [], {}, self.today)
        by_date = {x["date"]: x for x in plan}
        self.assertIn("BodyAttack", by_date["2026-10-12"]["title"])
        self.assertEqual(by_date["2026-10-12"]["intensity"], "moderate")
        self.assertEqual(by_date["2026-10-13"]["type"], "recovery")
        self.assertIn("drop spin", by_date["2026-10-13"]["title"])
        self.assertEqual(by_date["2026-10-14"]["type"], "strength")
        self.assertIn("tennis", by_date["2026-10-16"]["title"])
        for day in ("2026-10-10", "2026-10-11"):
            self.assertEqual(by_date[day]["type"], "class")
            self.assertIn("HYROX", by_date[day]["title"])
            self.assertIn("instructor structure is unknown", " ".join(by_date[day]["main"]))
        self.assertEqual(by_date["2026-10-10"]["intensity"], "moderate")
        self.assertEqual(by_date["2026-10-11"]["intensity"], "hard")
        for day in ("2026-10-08", "2026-10-15", "2026-10-22", "2026-10-29", "2026-11-05", "2026-11-19"):
            self.assertEqual(by_date[day]["type"], "hyrox")
            self.assertEqual(by_date[day]["intensity"], "hard")
        early = " ".join(by_date["2026-10-08"]["main"])
        later = " ".join(by_date["2026-11-05"]["main"])
        self.assertIn("2 rounds: 500 m", early)
        self.assertIn("2 rounds: 500 m", later)
        self.assertIn("no automatic week-index load increase", later)
        self.assertIn("5:15–5:30/km", early)
        self.assertIn("4:40/km", early)
        self.assertIn("5:10/km", early)

    def test_progressive_strength_library_and_personal_safety(self):
        logs = [{"date": day, "status": "completed", "duration": 45, "rpe": 6, "type": "strength"}
                for day in ("2026-10-14", "2026-10-21", "2026-10-28", "2026-11-04")]
        plan = coach.generate_plan(self.profile, RACE, logs, {}, date(2026, 11, 18))
        by_date = {x["date"]: x for x in plan}
        first = " ".join(by_date["2026-10-14"]["main"])
        specific = " ".join(by_date["2026-11-18"]["main"])
        self.assertIn("2 × 8", first)
        self.assertIn("3 × 8", specific)
        self.assertIn("2 × 10", " ".join(by_date["2026-11-04"]["main"]))
        for name in ("squat", "split squat", "Romanian deadlift", "row", "assisted pull-up", "press", "farmers carry"):
            self.assertIn(name, first)
        self.assertIn("no 1RM", first)
        rob_plan = coach.generate_plan(coach.default_profile("Rob"), RACE, [], {}, self.today)
        rob_strength = next(x for x in rob_plan if x["type"] == "strength")
        self.assertIn("back-pain history", " ".join(rob_strength["main"]))
        fuel = by_date["2026-11-14"]["fuelling"]
        self.assertIn("evening reminder", fuel["after"])
        self.assertNotIn("g/hour", str(fuel))
        self.assertNotIn("30–60", str(fuel))

    def test_yellow_volume_orange_recovery_and_seven_day_horizon(self):
        baseline = coach.generate_plan(self.profile, RACE, [], {}, self.today)
        yellow = coach.generate_plan(self.profile, RACE, [], {"fatigue": 6}, self.today)
        self.assertEqual(yellow[0]["intensity"], baseline[0]["intensity"])
        self.assertEqual(yellow[0]["duration"], round(baseline[0]["duration"] * .8))
        self.assertIn("20%", yellow[0]["adjustment"]["what"])
        orange = coach.generate_plan(self.profile, RACE, [], {"fatigue": 6, "soreness": 6}, self.today)
        self.assertEqual(orange[0]["intensity"], "easy")
        self.assertEqual(orange[0]["type"], "recovery")
        self.assertEqual(orange[2]["type"], "class")
        self.assertGreater(orange[3]["duration"], 0)
        self.assertEqual(orange[4]["duration"], 0)
        self.assertGreater(orange[6]["duration"], 0)
        for old, new in zip(baseline[7:], orange[7:]):
            self.assertEqual(old, new)
        red_race = coach.generate_plan(self.profile, RACE, [], {"pain": 5}, date(2026, 12, 2))[-1]
        self.assertEqual(red_race["type"], "race")
        self.assertEqual(red_race["duration"], 0)

    def test_progression_requires_completed_easy_enough_prior_evidence(self):
        logs = [{"date": day, "status": "completed", "duration": 45, "rpe": 6, "type": "hyrox"}
                for day in ("2026-10-08", "2026-10-15", "2026-10-22", "2026-10-29")]
        now = date(2026, 11, 5)
        good = coach.generate_plan(self.profile, RACE, logs, {}, now)
        workout = next(x for x in good if x["date"] == now.isoformat())
        self.assertIn("4 rounds: 900 m", " ".join(workout["main"]))
        logs[-1]["rpe"] = 9
        poor = coach.generate_plan(self.profile, RACE, logs, {}, now)
        self.assertIn("2 rounds: 500 m", " ".join(next(x for x in poor if x["date"] == now.isoformat())["main"]))
        logs[-1]["rpe"] = 6
        yellow = coach.generate_plan(self.profile, RACE, logs, {"fatigue": 6}, now)
        self.assertIn("2 rounds: 500 m", " ".join(next(x for x in yellow if x["date"] == now.isoformat())["main"]))

    def test_weekly_summary_actual_distance_class_and_strength_counts(self):
        logs = [{"date": "2026-10-14", "status": "completed", "duration": 45, "rpe": 6},
                {"date": "2026-10-15", "status": "completed", "duration": 45, "rpe": 7,
                 "metrics": {"run_distance_km": 2.5}},
                {"date": "2026-10-17", "status": "completed", "duration": 50, "rpe": 6},
                {"date": "2026-10-18", "status": "completed", "duration": 50, "rpe": 7,
                 "metrics": {"station": "ski", "distance": 1000, "unit": "m"}}]
        plan = coach.generate_plan(self.profile, RACE, [], {}, self.today)
        result = coach.weekly_summary(logs, plan, date(2026, 10, 18))
        self.assertEqual(result["strength_sessions"], 1)
        self.assertEqual(result["classes"], 2)
        self.assertEqual(result["hyrox_sessions"], 1)
        self.assertEqual(result["distance_km"], 2.5)
        self.assertEqual(result["running_sessions"], 1)


if __name__ == "__main__":
    unittest.main()
