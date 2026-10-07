import http.client
import json
from datetime import date, timedelta
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import server


class APITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.db_patch = patch.object(server, "DB_PATH", Path(cls.temp.name) / "test.sqlite3")
        cls.db_patch.start()
        server.initialize()
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.host = "127.0.0.1:" + str(cls.httpd.server_port)
        cls.host_patch = patch.object(server, "ALLOWED_HOSTS", {cls.host})
        cls.host_patch.start()
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()
        cls.host_patch.stop()
        cls.db_patch.stop()
        cls.temp.cleanup()

    def setUp(self):
        with server.connect() as db:
            for table in ("coach_adjustments", "nutrition_logs", "external_activities", "team_strategy",
                          "station_specs", "simulation_results", "readiness_logs", "mutation_keys",
                          "workout_completions", "workouts", "training_plans", "reset_tokens",
                          "sessions", "auth_limits", "team_members", "athletes", "races", "users", "teams"):
                db.execute(f"DELETE FROM {table}")

    def request(self, path, method="GET", data=None, session=None, csrf=True, extra=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=10)
        headers = {"Content-Type": "application/json"}
        if session:
            headers["Cookie"] = session["cookie"]
            if csrf:
                headers["X-CSRF-Token"] = session["csrf_token"]
        headers.update(extra or {})
        conn.request(method, path, json.dumps(data) if data is not None else None, headers)
        response = conn.getresponse()
        raw = response.read()
        result = json.loads(raw)
        cookie = response.getheader("Set-Cookie")
        if cookie and isinstance(result, dict):
            result["cookie"] = cookie.split(";")[0]
        status = response.status
        conn.close()
        return status, result

    def signup(self, email="kenza@example.test", person="Kenza", invite=""):
        status, session = self.request("/api/signup", "POST", {
            "email": email, "password": "test-only-long-passphrase", "person": person, "invite_code": invite,
        })
        self.assertEqual(status, 200, session)
        return session

    def test_authentication_session_and_csrf(self):
        self.assertEqual(self.request("/api/dashboard")[0], 401)
        session = self.signup()
        self.assertEqual(self.request("/api/session", session=session)[1]["profile"]["name"], "Kenza")
        self.assertEqual(self.request("/api/readiness", "POST", {"sleep": 8}, session, csrf=False)[0], 403)
        self.assertEqual(self.request("/api/readiness", "POST", {"sleep": 8}, session,
                                      extra={"Origin": "https://untrusted.example"})[0], 403)
        self.assertEqual(self.request("/api/logout", "POST", {}, session)[0], 200)
        self.assertEqual(self.request("/api/session", session=session)[0], 401)
        self.assertEqual(self.request("/api/login", "POST", {"email": "kenza@example.test", "password": "incorrect-password"})[0], 401)
        self.assertEqual(self.request("/api/login", "POST", {"email": "kenza@example.test", "password": "test-only-long-passphrase"})[0], 200)

    def test_private_team_and_shared_simulations(self):
        ken = self.signup()
        rob = self.signup("rob@example.test", "Rob", ken["team"]["invite_code"])
        outsider = self.signup("other@example.test")
        self.assertEqual(ken["team"]["id"], rob["team"]["id"])
        self.assertNotEqual(ken["team"]["id"], outsider["team"]["id"])
        data = {"date": "2026-09-06", "total_seconds": 4200, "runs": [300], "stations": {"sled_push": 100}, "transitions": [5]}
        self.assertEqual(self.request("/api/simulations", "POST", data, ken)[0], 200)
        with server.connect() as db:
            self.assertEqual(len(server.context(db, rob["user"]["id"], rob["csrf_token"])["simulations"]), 2)
            self.assertEqual(len(server.context(db, outsider["user"]["id"], outsider["csrf_token"])["simulations"]), 1)

    def test_logging_is_idempotent_persistent_and_athlete_scoped(self):
        ken = self.signup()
        rob = self.signup("rob@example.test", "Rob", ken["team"]["invite_code"])
        log = {"client_id": "offline-event-1", "date": "2026-10-07", "status": "completed",
               "duration": 60, "rpe": 7, "sleep": 8, "metrics": {"distance": 5}, "notes": "Intervals"}
        self.assertEqual(self.request("/api/workouts/log", "POST", log, ken)[0], 200)
        log["duration"] = 90
        self.assertTrue(self.request("/api/workouts/log", "POST", log, ken)[1]["duplicate"])
        with server.connect() as db:
            state = server.context(db, ken["user"]["id"], ken["csrf_token"])
            self.assertEqual(state["logs"][0]["duration"], 60)
            self.assertIsNone(state["logs"][0]["energy"])
            self.assertEqual(server.context(db, rob["user"]["id"], rob["csrf_token"])["logs"], [])
        log["client_id"] = "offline-event-2"
        self.assertEqual(self.request("/api/workouts/log", "POST", log, ken)[0], 200)
        self.assertTrue(Path(server.DB_PATH).exists())

    def test_password_reset_one_use_and_session_invalidation(self):
        session = self.signup()
        with server.connect() as db:
            token = server.mint_reset(db, "kenza@example.test")
        status, result = self.request("/api/password-reset/confirm", "POST", {"token": token, "password": "replacement-passphrase"})
        self.assertEqual(status, 200, result)
        self.assertEqual(self.request("/api/session", session=session)[0], 401)
        self.assertEqual(self.request("/api/password-reset/confirm", "POST", {"token": token, "password": "replacement-passphrase"})[0], 400)
        self.assertEqual(self.request("/api/login", "POST", {"email": "kenza@example.test", "password": "replacement-passphrase"})[0], 200)
        status, response = self.request("/api/password-reset", "POST", {"email": "absent@example.test"})
        self.assertEqual(status, 200)
        self.assertNotIn("token", response)

    def test_invalid_input_and_static_isolation(self):
        session = self.signup()
        for rpe in (-1, 11, "seven"):
            self.assertEqual(self.request("/api/workouts/log", "POST", {"client_id": "bad", "date": "2026-10-07",
                "status": "completed", "duration": 60, "rpe": rpe}, session)[0], 400)
        self.assertEqual(self.request("/api/readiness", "POST", {"sleep": float("nan")}, session)[0], 400)
        self.assertEqual(self.request("/api/simulations", "POST", {"date": "2026-09-06",
            "total_seconds": 600, "runs": [500, 500]}, session)[0], 400)
        self.assertEqual(self.request("/api/workouts/log", "POST", {"client_id": "bad", "date": "2026-02-30",
            "status": "started"}, session)[0], 400)
        for path in ("/server.py", "/../server.py", "/data/coach.sqlite3"):
            self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request("/api/session", session=session, extra={"Host": "attacker.example"})[0], 400)

    def test_signup_duplicates_rollback_and_no_default_accounts(self):
        session = self.signup()
        status, _ = self.request("/api/signup", "POST", {"email": "another@example.test",
            "password": "test-only-long-passphrase", "person": "Kenza", "invite_code": session["team"]["invite_code"]})
        self.assertEqual(status, 409)
        with server.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM users").fetchone()[0], 1)
            self.assertNotIn("test-only", db.execute("SELECT password FROM users").fetchone()[0])

    def test_dashboard_persists_plan_and_configurable_station_loads(self):
        session = self.signup()
        status, dashboard = self.request("/api/dashboard", session=session)
        self.assertEqual(status, 200, dashboard)
        self.assertEqual(len(dashboard["plan"]), 56)
        self.assertEqual(len(dashboard["stations"]), 8)
        with server.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM workouts").fetchone()[0], 56)
        stations = dashboard["stations"]
        next(s for s in stations if s["id"] == "sled_push")["load"] = 145
        self.assertEqual(self.request("/api/stations", "PUT", {"stations": stations}, session)[0], 200)
        status, changed = self.request("/api/dashboard", session=session)
        self.assertEqual(status, 200, changed)
        self.assertEqual(next(s for s in changed["stations"] if s["id"] == "sled_push")["load"], 145)

    def test_external_class_cannot_bypass_pain_modification(self):
        session = self.signup()
        start = date.today()
        race = {"plan_start": start.isoformat(), "simulation_date": (start + timedelta(days=37)).isoformat(),
                "date": (start + timedelta(days=55)).isoformat()}
        self.assertEqual(self.request("/api/race", "PUT", race, session)[0], 200)
        tomorrow = (start + timedelta(days=1)).isoformat()
        self.assertEqual(self.request("/api/workouts/external", "POST", {
            "date": tomorrow, "title": "Hard class", "duration": 90, "intensity": "hard", "main": ["Heavy sled intervals"],
        }, session)[0], 200)
        self.assertEqual(self.request("/api/readiness", "POST", {"sleep": 8, "pain": 8}, session)[0], 200)
        status, dashboard = self.request("/api/dashboard", session=session)
        self.assertEqual(status, 200, dashboard)
        workout = next(w for w in dashboard["plan"] if w["date"] == tomorrow)
        self.assertEqual(workout["duration"], 0)
        self.assertNotEqual(workout["intensity"], "hard")
        self.assertIn("adjustment", workout)
        self.assertEqual(self.request("/api/workouts/external", "POST", {
            "date": race["simulation_date"], "title": "Class", "duration": 60,
        }, session)[0], 400)

    def test_personal_profile_and_measured_team_scenario(self):
        ken = self.signup()
        rob = self.signup("rob@example.test", "Rob", ken["team"]["invite_code"])
        self.assertEqual(self.request("/api/profile", "PUT", {"goals": "Sustainable sled technique",
            "fuelling_preferences": "Review my own evening routine"}, ken)[0], 200)
        self.assertEqual(self.request("/api/session", session=ken)[1]["profile"]["goals"], "Sustainable sled technique")
        self.assertNotEqual(self.request("/api/session", session=rob)[1]["profile"]["goals"], "Sustainable sled technique")
        measurements = {"sled_push": {"kenza_seconds": 200, "rob_seconds": 120,
                                      "kenza_fatigue": 5, "rob_fatigue": 3, "transition_seconds": 4}}
        status, result = self.request("/api/measurements", "PUT", {"measurements": measurements}, ken)
        self.assertEqual(status, 200, result)
        scenario = {"run_pace_seconds": 300, "station_seconds": [100] * 8, "transition_seconds": [10] * 8}
        status, result = self.request("/api/scenario", "POST", scenario, rob)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["seconds"], 3280)
        with server.connect() as db:
            self.assertEqual(server.context(db, rob["user"]["id"], rob["csrf_token"])["measurements"], measurements)

    def test_auth_rate_limit_and_password_length(self):
        self.assertEqual(self.request("/api/signup", "POST", {"email": "kenza@example.test",
            "password": "short", "person": "Kenza"})[0], 400)
        with server.connect() as db:
            self.assertTrue(server.limited(db, "test-auth-key", maximum=2))
            self.assertTrue(server.limited(db, "test-auth-key", maximum=2))
            self.assertFalse(server.limited(db, "test-auth-key", maximum=2))


if __name__ == "__main__":
    unittest.main()
