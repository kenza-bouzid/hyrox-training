"""HYROX Coach: same-origin API and PWA with a persistent SQLite store."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import secrets
import smtplib
import sqlite3
import ssl
import time
from urllib.parse import urlsplit

import coach

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", str(ROOT / "data" / "coach.sqlite3")))
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8000").rstrip("/")
SECURE_COOKIE = PUBLIC_URL.startswith("https://")
ALLOWED_HOSTS = set(os.environ.get("ALLOWED_HOSTS", urlsplit(PUBLIC_URL).netloc + ",127.0.0.1:8000").split(","))
DEFAULT_RACE = {
    "name": "HYROX London", "date": "2026-12-02", "target_seconds": 3900,
    "baseline_seconds": 4252, "simulation_date": "2026-11-14", "plan_start": "2026-10-08",
}
STATIC_ASSETS = {
    "/index.html": (ROOT / "static" / "index.html", "text/html"),
    "/app.js": (ROOT / "static" / "app.js", "text/javascript"),
    "/style.css": (ROOT / "static" / "style.css", "text/css"),
    "/sw.js": (ROOT / "static" / "sw.js", "text/javascript"),
    "/manifest.webmanifest": (ROOT / "static" / "manifest.webmanifest", "application/manifest+json"),
    "/icon.svg": (ROOT / "static" / "icon.svg", "image/svg+xml"),
}
SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS teams(id TEXT PRIMARY KEY, name TEXT NOT NULL, invite_code TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS athletes(user_id TEXT PRIMARY KEY REFERENCES users(id), profile TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS team_members(user_id TEXT PRIMARY KEY REFERENCES users(id), team_id TEXT NOT NULL REFERENCES teams(id), person TEXT NOT NULL, UNIQUE(team_id,person));
CREATE TABLE IF NOT EXISTS races(team_id TEXT PRIMARY KEY REFERENCES teams(id), config TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), csrf TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS reset_tokens(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS auth_limits(key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS training_plans(user_id TEXT PRIMARY KEY REFERENCES users(id), race_config TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workouts(user_id TEXT NOT NULL REFERENCES users(id), date TEXT NOT NULL, planned TEXT NOT NULL, PRIMARY KEY(user_id,date));
CREATE TABLE IF NOT EXISTS workout_completions(user_id TEXT NOT NULL REFERENCES users(id), date TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(user_id,date));
CREATE TABLE IF NOT EXISTS additional_workouts(user_id TEXT NOT NULL REFERENCES users(id), session_id TEXT NOT NULL, date TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(user_id,session_id));
CREATE TABLE IF NOT EXISTS mutation_keys(user_id TEXT NOT NULL REFERENCES users(id), client_id TEXT NOT NULL, PRIMARY KEY(user_id,client_id));
CREATE TABLE IF NOT EXISTS readiness_logs(id INTEGER PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS simulation_results(id TEXT PRIMARY KEY, team_id TEXT NOT NULL REFERENCES teams(id), date TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(team_id,date));
CREATE TABLE IF NOT EXISTS station_specs(team_id TEXT PRIMARY KEY REFERENCES teams(id), data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS team_strategy(team_id TEXT PRIMARY KEY REFERENCES teams(id), measurements TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS external_activities(user_id TEXT NOT NULL REFERENCES users(id), date TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(user_id,date));
CREATE TABLE IF NOT EXISTS nutrition_logs(user_id TEXT NOT NULL REFERENCES users(id), date TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(user_id,date));
CREATE TABLE IF NOT EXISTS coach_adjustments(user_id TEXT NOT NULL REFERENCES users(id), date TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(user_id,date));
"""


class Invalid(ValueError):
    pass


@contextmanager
def connect():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Create privately before SQLite can create WAL files with inherited permissions.
    fd = os.open(DB_PATH, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    os.chmod(DB_PATH, 0o600)
    with connect() as db:
        db.executescript(SCHEMA)


def encoded(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def password_hash(password):
    salt = secrets.token_hex(16)
    derived = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return salt + ":" + derived.hex()


def password_matches(password, stored):
    salt, expected = stored.split(":")
    derived = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return hmac.compare_digest(derived.hex(), expected)


def text(value, name, maximum=2000, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise Invalid(f"Invalid {name}.")
    return value.strip()


def number(value, name, low=0, high=100000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise Invalid(f"{name} must be between {low} and {high}.")
    return value


def iso_date(value):
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except ValueError:
        raise Invalid("Use a date in YYYY-MM-DD format.") from None
    return value


def email_value(value):
    value = text(value, "email", 254, True).lower()
    if value.count("@") != 1 or "." not in value.split("@")[1] or any(c.isspace() for c in value):
        raise Invalid("Enter a valid email address.")
    return value


def new_password(value):
    value = text(value, "password", 256, True)
    if len(value) < 10:
        raise Invalid("Use a password with at least 10 characters.")
    return value


def limited(db, key, maximum=30):
    key = digest(key)
    now = time.time()
    db.execute("DELETE FROM auth_limits WHERE expires < ?", (now,))
    db.execute(
        "INSERT INTO auth_limits VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1",
        (key, now + 3600),
    )
    count = db.execute("SELECT count FROM auth_limits WHERE key=?", (key,)).fetchone()[0]
    db.commit()
    return count <= maximum


def mint_reset(db, email):
    user = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if not user:
        return None
    token = secrets.token_urlsafe(32)
    db.execute("DELETE FROM reset_tokens WHERE user_id=? OR expires<?", (user["id"], time.time()))
    db.execute("INSERT INTO reset_tokens VALUES (?,?,?)", (digest(token), user["id"], time.time() + 1800))
    return token


def send_reset(email, token):
    host = os.environ.get("SMTP_HOST")
    if not host:
        return
    message = EmailMessage()
    message["Subject"] = "Reset your HYROX Coach password"
    message["From"] = os.environ.get("SMTP_FROM", "coach@localhost")
    message["To"] = email
    message.set_content(f"Reset your password within 30 minutes:\n{PUBLIC_URL}/?reset={token}\n\nIf you did not request this, ignore this email.")
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if os.environ.get("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)


def session_data(db, user_id, csrf):
    row = db.execute(
        "SELECT u.id,u.email,a.profile,t.id team_id,t.name,t.invite_code,r.config "
        "FROM users u JOIN athletes a ON a.user_id=u.id JOIN team_members m ON m.user_id=u.id "
        "JOIN teams t ON t.id=m.team_id JOIN races r ON r.team_id=t.id WHERE u.id=?", (user_id,),
    ).fetchone()
    return {
        "user": {"id": row["id"], "email": row["email"]},
        "profile": json.loads(row["profile"]),
        "team": {"id": row["team_id"], "name": row["name"], "invite_code": row["invite_code"]},
        "race": json.loads(row["config"]), "csrf_token": csrf,
    }


def context(db, user_id, csrf):
    state = session_data(db, user_id, csrf)
    logs = [json.loads(r[0]) for r in db.execute("SELECT data FROM workout_completions WHERE user_id=? ORDER BY date", (user_id,))]
    logs.extend(json.loads(r[0]) for r in db.execute("SELECT data FROM additional_workouts WHERE user_id=? ORDER BY date,session_id", (user_id,)))
    logs.sort(key=lambda log: (log["date"], log.get("session_time", ""), log.get("session_id", "")))
    row = db.execute("SELECT data,created_at FROM readiness_logs WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    # Old readiness is not evidence of current readiness.
    checkin = json.loads(row["data"]) if row and row["created_at"][:10] == date.today().isoformat() else {}
    team_id = state["team"]["id"]
    simulations = [json.loads(r[0]) for r in db.execute("SELECT data FROM simulation_results WHERE team_id=? ORDER BY date", (team_id,))]
    specs = db.execute("SELECT data FROM station_specs WHERE team_id=?", (team_id,)).fetchone()
    stations = json.loads(specs[0]) if specs else coach.STATIONS
    measurements = db.execute("SELECT measurements FROM team_strategy WHERE team_id=?", (team_id,)).fetchone()
    state.update(logs=logs, checkin=checkin, simulations=simulations, stations=stations,
                 measurements=json.loads(measurements[0]) if measurements else {})
    return state


def dashboard(db, user_id, csrf):
    state = context(db, user_id, csrf)
    profile, race, logs, checkin = (state[k] for k in ("profile", "race", "logs", "checkin"))
    config = encoded({"race": race, "stations": state["stations"], "profile": profile})
    stored = db.execute("SELECT race_config FROM training_plans WHERE user_id=?", (user_id,)).fetchone()
    if not stored or stored[0] != config:
        base = coach.generate_plan(profile, race, [], {}, stations=state["stations"])
        db.execute("DELETE FROM workouts WHERE user_id=? AND date>=?", (user_id, date.today().isoformat()))
        for workout in base:
            db.execute("INSERT OR IGNORE INTO workouts VALUES (?,?,?)", (user_id, workout["date"], encoded(workout)))
        db.execute("INSERT INTO training_plans VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET race_config=excluded.race_config", (user_id, config))
    plan = coach.generate_plan(profile, race, logs, checkin, stations=state["stations"])
    saved = {r["date"]: json.loads(r["planned"]) for r in db.execute("SELECT date,planned FROM workouts WHERE user_id=?", (user_id,))}
    external = {r["date"]: json.loads(r["data"]) for r in db.execute("SELECT date,data FROM external_activities WHERE user_id=?", (user_id,))}
    for i, workout in enumerate(plan):
        day = workout["date"]
        if day < date.today().isoformat() and day in saved:
            plan[i] = saved[day]
        if day in external:
            protected_phase = plan[i].get("phase") in ("taper", "simulation") or plan[i]["type"] in ("recovery", "rest")
            safety = dict(plan[i]) if plan[i].get("adjustment") or protected_phase else None
            if safety and not safety.get("adjustment"):
                safety["adjustment"] = {
                    "what": "Retain recovery or phase-specific class limits",
                    "why": "Entered class content cannot replace simulation recovery or taper protections.",
                    "effect": "Keep the planned duration and effort; ask the instructor to scale the class.",
                }
            plan[i] = {**plan[i], **external[day]}
            if safety:
                for key in ("title", "type", "intensity", "duration", "main", "adjustment"):
                    plan[i][key] = safety[key]
        adjustment = plan[i].get("adjustment")
        if adjustment:
            db.execute("INSERT INTO coach_adjustments VALUES (?,?,?) ON CONFLICT(user_id,date) DO UPDATE SET data=excluded.data", (user_id, day, encoded(adjustment)))
    # Instructor-entered content must not bypass the rolling intensity limit.
    accepted = []
    for workout in sorted((w for w in plan if w["intensity"] == "hard"),
                          key=lambda w: (w["type"] not in ("race", "simulation"), w["date"])):
        day = date.fromisoformat(workout["date"])
        dates = sorted(accepted + [day])
        if any(sum(0 <= (other - start).days <= 6 for other in dates) > 2 for start in dates):
            if workout["date"] >= date.today().isoformat():
                workout.update(intensity="easy", duration=min(25, workout["duration"]),
                               main=["Easy movement only. Ask the instructor to remove intervals and heavy station work."],
                               adjustment={"what": "Reduce class intensity and duration",
                                           "why": "No more than two planned hard sessions in a rolling seven days.",
                                           "effect": "Preserve recovery rather than adding intensity from external classes."})
                db.execute("INSERT INTO coach_adjustments VALUES (?,?,?) ON CONFLICT(user_id,date) DO UPDATE SET data=excluded.data",
                           (user_id, workout["date"], encoded(workout["adjustment"])))
        else:
            accepted.append(day)
    state.update(
        plan=plan, readiness=coach.readiness(logs, checkin),
        projection=coach.projection(race, state["simulations"], logs, checkin),
        analysis=coach.simulation_analysis(race, state["simulations"]),
        strategy=coach.strategy(state["measurements"], state["stations"]),
        weekly=coach.weekly_summary(logs, plan),
        adjustments=[{"date": r[0], **json.loads(r[1])} for r in db.execute("SELECT date,data FROM coach_adjustments WHERE user_id=? ORDER BY date", (user_id,))],
    )
    return state


class Handler(BaseHTTPRequestHandler):
    server_version = "HYROXCoach"

    def log_message(self, fmt, *args):
        # Do not log query strings, reset tokens, or personal workout information.
        print(f"{self.command} {urlsplit(self.path).path} {args[1] if len(args) > 1 else ''}", flush=True)

    def respond(self, status, value, cookie=None):
        data = encoded(value).encode()
        self.send_response(status)
        self.headers_common()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def headers_common(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; worker-src 'self'; manifest-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        if SECURE_COOKIE:
            self.send_header("Strict-Transport-Security", "max-age=31536000")

    def auth(self, db):
        jar = SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
            token = jar["session"].value if "session" in jar else ""
        except Exception:
            return None
        return db.execute("SELECT user_id,csrf FROM sessions WHERE token_hash=? AND expires>?", (digest(token), time.time())).fetchone()

    def cookie(self, token="", age=604800):
        return f"session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={age}" + ("; Secure" if SECURE_COOKIE else "")

    def begin_session(self, db, user_id):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
        db.execute("INSERT INTO sessions VALUES (?,?,?,?)", (digest(token), user_id, csrf, time.time() + 604800))
        db.commit()
        self.respond(200, session_data(db, user_id, csrf), self.cookie(token))

    def body(self):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise Invalid("Send JSON request data.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 100000:
                raise Invalid("Request body must be between 1 and 100000 bytes.")
            value = json.loads(self.rfile.read(length), parse_constant=lambda _: (_ for _ in ()).throw(Invalid("Non-finite number.")))
            if not isinstance(value, dict):
                raise Invalid("Expected a JSON object.")
            return value
        except (ValueError, UnicodeError):
            raise Invalid("Invalid JSON request.") from None

    def dispatch(self):
        if self.headers.get("Host", "") not in ALLOWED_HOSTS:
            return self.respond(400, {"error": "Unrecognised host."})
        path = urlsplit(self.path).path
        if not path.startswith("/api/"):
            return self.static(path)
        if self.command not in ("GET", "POST", "PUT"):
            return self.respond(405, {"error": "Method not allowed."})
        origin = self.headers.get("Origin")
        if self.command != "GET" and origin and origin not in {PUBLIC_URL, "http://" + self.headers.get("Host", "") if not SECURE_COOKIE else PUBLIC_URL}:
            return self.respond(403, {"error": "Cross-origin requests are not allowed."})
        try:
            with connect() as db:
                data = self.body() if self.command != "GET" else {}
                if self.command == "POST" and path in {"/api/signup", "/api/login", "/api/password-reset", "/api/password-reset/confirm"}:
                    return self.public_api(db, path, data)
                auth = self.auth(db)
                if not auth:
                    return self.respond(401, {"error": "Please log in."})
                if self.command != "GET" and not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), auth["csrf"]):
                    return self.respond(403, {"error": "Refresh your session before saving."})
                if self.command == "GET":
                    if path == "/api/session":
                        return self.respond(200, session_data(db, auth["user_id"], auth["csrf"]))
                    if path == "/api/dashboard":
                        result = dashboard(db, auth["user_id"], auth["csrf"])
                        db.commit()
                        return self.respond(200, result)
                if path == "/api/logout" and self.command == "POST":
                    jar = SimpleCookie(self.headers.get("Cookie", ""))
                    db.execute("DELETE FROM sessions WHERE token_hash=?", (digest(jar["session"].value),))
                    db.commit()
                    return self.respond(200, {"ok": True}, self.cookie(age=0))
                result = self.private_api(db, auth, path, data)
                db.commit()
                return self.respond(200, result)
        except Invalid as error:
            return self.respond(400, {"error": str(error)})
        except sqlite3.IntegrityError:
            return self.respond(409, {"error": "That account, athlete, or event already exists."})
        except Exception as error:
            print(f"Request failed: {type(error).__name__}", flush=True)
            return self.respond(500, {"error": "Unable to save right now. Your offline queue can be retried."})

    def public_api(self, db, path, data):
        if not limited(db, self.client_address[0] + path, 5 if path == "/api/password-reset" else 30):
            return self.respond(429, {"error": "Too many attempts. Please try again in an hour."})
        if path == "/api/password-reset/confirm":
            token = text(data.get("token"), "reset token", 100, True)
            password = new_password(data.get("password"))
            row = db.execute("SELECT user_id FROM reset_tokens WHERE token_hash=? AND expires>?", (digest(token), time.time())).fetchone()
            if not row:
                raise Invalid("Reset link is invalid or expired.")
            db.execute("UPDATE users SET password = ? WHERE id=?", (password_hash(password), row[0]))
            db.execute("DELETE FROM reset_tokens WHERE user_id=?", (row[0],))
            db.execute("DELETE FROM sessions WHERE user_id=?", (row[0],))
            db.commit()
            return self.respond(200, {"ok": True})
        email = email_value(data.get("email"))
        if path == "/api/password-reset":
            token = mint_reset(db, email)
            db.commit()
            if token:
                try:
                    send_reset(email, token)
                except (OSError, smtplib.SMTPException):
                    print("Password reset email delivery failed.", flush=True)
            return self.respond(200, {"message": "If this account exists, a reset link will be sent. Local installations require the administrator's reset-password command."})
        password = new_password(data.get("password"))
        if path == "/api/login":
            user = db.execute("SELECT id,password FROM users WHERE email=?", (email,)).fetchone()
            # Perform the same expensive comparison for unknown accounts.
            stored = user["password"] if user else "00" * 16 + ":" + "00" * 64
            if not password_matches(password, stored) or not user:
                return self.respond(401, {"error": "Email or password is incorrect."})
            return self.begin_session(db, user["id"])
        person = data.get("person")
        if person not in ("Kenza", "Rob"):
            raise Invalid("Choose Kenza or Rob.")
        invite = text(data.get("invite_code", ""), "invite code", 100)
        if invite:
            team = db.execute("SELECT id FROM teams WHERE invite_code=?", (invite,)).fetchone()
            if not team:
                raise Invalid("Invalid team invitation.")
            team_id = team["id"]
        else:
            team_id = secrets.token_hex(16)
            db.execute("INSERT INTO teams VALUES (?,?,?)", (team_id, "Kenza + Rob", secrets.token_urlsafe(18)))
            db.execute("INSERT INTO races VALUES (?,?)", (team_id, encoded(DEFAULT_RACE)))
            baseline = {"date": "2026-09-05", "total_seconds": 4252, "runs": [], "stations": {}, "transitions": [],
                        "allocations": {"sled_push": 40}, "rpe": None, "race_standard_weights": True,
                        "notes": "September baseline. Sled push allocation approximately Kenza 40%, Rob 60%; splits not recorded."}
            db.execute("INSERT INTO simulation_results VALUES (?,?,?,?)", (secrets.token_hex(16), team_id, baseline["date"], encoded(baseline)))
        user_id = secrets.token_hex(16)
        db.execute("INSERT INTO users VALUES (?,?,?)", (user_id, email, password_hash(password)))
        db.execute("INSERT INTO athletes VALUES (?,?)", (user_id, encoded(coach.default_profile(person))))
        db.execute("INSERT INTO team_members VALUES (?,?,?)", (user_id, team_id, person))
        return self.begin_session(db, user_id)

    def private_api(self, db, auth, path, data):
        user_id = auth["user_id"]
        state = context(db, user_id, auth["csrf"])
        team_id = state["team"]["id"]
        method = self.command
        if path == "/api/workouts/log" and method == "POST":
            if data.get("athlete_id") != user_id:
                raise Invalid("Workout account changed. Sign in as the athlete who recorded it before retrying.")
            client_id = text(data.get("client_id"), "client ID", 100, True)
            kind = data.get("kind", "planned")
            if kind not in ("planned", "additional"):
                raise Invalid("Invalid session kind.")
            day = iso_date(data.get("date"))
            session_id = text(data.get("session_id"), "session ID", 100, True) if kind == "additional" else "planned:" + day
            if db.execute("SELECT 1 FROM mutation_keys WHERE user_id=? AND client_id=?", (user_id, client_id)).fetchone():
                row = db.execute("SELECT data FROM additional_workouts WHERE user_id=? AND session_id=?", (user_id, session_id)).fetchone() if kind == "additional" else db.execute("SELECT data FROM workout_completions WHERE user_id=? AND date=?", (user_id, day)).fetchone()
                return {"ok": True, "duplicate": True, "log": json.loads(row[0]) if row else None}
            # Allow one day for athletes whose local date is ahead of the server's.
            if kind == "additional" and day > (date.today() + timedelta(days=1)).isoformat():
                raise Invalid("Record additional workouts on or after their session date.")
            status = data.get("status")
            if status not in ("completed", "started", "skipped", "modified"):
                raise Invalid("Invalid workout status.")
            log = {"id": session_id, "session_id": session_id, "kind": kind, "client_id": client_id, "date": day, "status": status}
            if kind == "additional":
                log["title"] = text(data.get("title"), "session title", 150, True)
                log["type"] = text(data.get("type"), "session type", 60, True).lower()
            for key, high in (("duration", 600), ("rpe", 10), ("energy", 10), ("soreness", 10), ("sleep", 24), ("pain", 10)):
                value = data.get(key, 0 if key in ("duration", "rpe") else None)
                log[key] = None if value is None and key not in ("duration", "rpe") else number(value, key, 0, high)
            if (status == "completed" or status == "modified" and log["duration"] > 0) and (log["duration"] <= 0 or log["rpe"] < 1):
                raise Invalid("Completed sessions need a positive duration and RPE 1–10.")
            for key in ("notes", "modification", "pre_session_food", "glucose_notes"):
                log[key] = text(data.get(key, ""), key, 4000)
            log["session_time"] = text(data.get("session_time", ""), "session time", 30)
            if kind == "additional" and log["session_time"] and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", log["session_time"]):
                raise Invalid("Use a session time in HH:MM format.")
            metrics = data.get("metrics", {})
            if not isinstance(metrics, dict) or len(metrics) > 40:
                raise Invalid("Invalid session metrics.")
            for key, value in metrics.items():
                text(key, "metric name", 60, True)
                if isinstance(value, (int, float)):
                    number(value, key)
                elif isinstance(value, str):
                    text(value, key, 4000)
                elif key == "splits" and isinstance(value, list) and len(value) <= 100:
                    for split in value:
                        number(split, "split seconds", 0, 86400)
                else:
                    raise Invalid("Metrics must be numbers, text, or measured numeric split arrays.")
            log["metrics"] = metrics
            db.execute("INSERT INTO mutation_keys VALUES (?,?)", (user_id, client_id))
            if kind == "additional":
                db.execute("INSERT INTO additional_workouts VALUES (?,?,?,?) ON CONFLICT(user_id,session_id) DO UPDATE SET date=excluded.date,data=excluded.data", (user_id, session_id, day, encoded(log)))
            else:
                db.execute("INSERT INTO workout_completions VALUES (?,?,?) ON CONFLICT(user_id,date) DO UPDATE SET data=excluded.data", (user_id, day, encoded(log)))
                nutrition = {k: log[k] for k in ("session_time", "pre_session_food", "glucose_notes")}
                db.execute("INSERT INTO nutrition_logs VALUES (?,?,?) ON CONFLICT(user_id,date) DO UPDATE SET data=excluded.data", (user_id, day, encoded(nutrition)))
            if day == date.today().isoformat():
                signals = {k: log[k] for k in ("sleep", "soreness", "pain") if log[k] is not None}
                if log["energy"] is not None:
                    signals["fatigue"] = 10 - log["energy"]
                if signals:
                    signals = {**state["checkin"], **signals}
                    db.execute("INSERT INTO readiness_logs(user_id,created_at,data) VALUES (?,?,?)",
                               (user_id, datetime.now(timezone.utc).isoformat(), encoded(signals)))
            return {"ok": True, "log": log}
        if path == "/api/readiness" and method == "POST":
            checkin = {k: number(data[k], k, 0, 24 if k == "sleep" else 10)
                       for k in ("sleep", "soreness", "fatigue", "pain") if k in data and data[k] is not None}
            if not checkin:
                raise Invalid("Enter at least one readiness measurement.")
            checkin = {**state["checkin"], **checkin}
            db.execute("INSERT INTO readiness_logs(user_id,created_at,data) VALUES (?,?,?)", (user_id, datetime.now(timezone.utc).isoformat(), encoded(checkin)))
            return {"ok": True, "readiness": coach.readiness(state["logs"], checkin)}
        if path == "/api/profile" and method == "PUT":
            profile = state["profile"]
            for key in ("name", "goals", "fuelling_preferences", "notes", "easy_pace"):
                if key in data:
                    profile[key] = text(data[key], key, 4000)
            if "easy_pace" in data:
                profile["easy_pace_override"] = True
                pace = re.match(r"^(\d{1,2}):([0-5]\d)", profile["easy_pace"])
                if pace:
                    profile["easy_pace_seconds"] = number(int(pace[1]) * 60 + int(pace[2]), "easy pace seconds/km", 180, 1200)
                else:
                    profile.pop("easy_pace_seconds", None)
            if "easy_pace_seconds" in data:
                profile["easy_pace_seconds"] = number(data["easy_pace_seconds"], "easy pace seconds/km", 180, 1200)
                if "easy_pace" not in data:
                    profile["easy_pace_override"] = False
            if "benchmark_seconds" in data:
                profile["benchmark_seconds"] = number(data["benchmark_seconds"], "10K benchmark seconds", 600, 14400)
            db.execute("UPDATE athletes SET profile=? WHERE user_id=?", (encoded(profile), user_id))
            db.execute("DELETE FROM training_plans WHERE user_id=?", (user_id,))
            return {"ok": True, "profile": profile}
        if path == "/api/race" and method == "PUT":
            race = state["race"]
            for key in ("date", "plan_start", "simulation_date"):
                if key in data:
                    race[key] = iso_date(data[key])
            if "name" in data:
                race["name"] = text(data["name"], "race name", 100, True)
            if "target_seconds" in data:
                race["target_seconds"] = number(data["target_seconds"], "race target seconds", 600, 18000)
            if not race["plan_start"] < race["simulation_date"] < race["date"]:
                raise Invalid("Plan start must precede simulation, which must precede race.")
            db.execute("UPDATE races SET config=? WHERE team_id=?", (encoded(race), team_id))
            return {"ok": True, "race": race}
        if path == "/api/team" and method == "PUT":
            db.execute("UPDATE teams SET name=? WHERE id=?", (text(data.get("name"), "team name", 100, True), team_id))
            return {"ok": True}
        if path == "/api/stations" and method == "PUT":
            supplied = data.get("stations")
            if not isinstance(supplied, list) or len(supplied) != len(coach.STATIONS):
                raise Invalid("Supply all eight station specifications.")
            specs = []
            for default in coach.STATIONS:
                matches = [s for s in supplied if isinstance(s, dict) and s.get("id") == default["id"]]
                if len(matches) != 1:
                    raise Invalid("Each station must appear exactly once.")
                incoming = matches[0]
                spec = dict(default)
                for key in ("load", "distance"):
                    if key in incoming:
                        spec[key] = None if key == "load" and incoming[key] is None else number(incoming[key], key, 0, 2000)
                if "notes" in incoming:
                    spec["notes"] = text(incoming["notes"], "station notes", 2000)
                specs.append(spec)
            db.execute("INSERT INTO station_specs VALUES (?,?) ON CONFLICT(team_id) DO UPDATE SET data=excluded.data", (team_id, encoded(specs)))
            return {"ok": True}
        if path == "/api/measurements" and method == "PUT":
            measurements = data.get("measurements")
            if not isinstance(measurements, dict):
                raise Invalid("Invalid station measurements.")
            allowed = {s["id"] for s in coach.STATIONS}
            clean = {}
            for station, values in measurements.items():
                if station not in allowed or not isinstance(values, dict):
                    raise Invalid("Unknown station.")
                clean[station] = {}
                for key, value in values.items():
                    if key not in ("kenza_seconds", "rob_seconds", "kenza_fatigue", "rob_fatigue", "transition_seconds", "preferred_share"):
                        raise Invalid("Unknown measurement.")
                    if value is not None and value != "":
                        clean[station][key] = number(value, key, 0, 1 if key == "preferred_share" else 10 if "fatigue" in key else 3600)
            db.execute("INSERT INTO team_strategy VALUES (?,?) ON CONFLICT(team_id) DO UPDATE SET measurements=excluded.measurements", (team_id, encoded(clean)))
            return {"ok": True, "strategy": coach.strategy(clean, state["stations"])}
        if path == "/api/simulations" and method == "POST":
            sim = {"date": iso_date(data.get("date")), "total_seconds": number(data.get("total_seconds"), "simulation total seconds", 600, 18000)}
            if sim["date"] > date.today().isoformat():
                raise Invalid("Record results after the simulation, not before it.")
            for key in ("runs", "transitions"):
                values = data.get(key, [])
                if not isinstance(values, list) or len(values) > 8:
                    raise Invalid(f"{key} needs up to eight splits.")
                sim[key] = [number(v, key, 0, 3600) for v in values]
            allowed = {s["id"] for s in coach.STATIONS}
            for key in ("stations", "allocations"):
                values = data.get(key, {})
                if not isinstance(values, dict) or not set(values).issubset(allowed):
                    raise Invalid("Unknown station split.")
                sim[key] = {k: number(v, key, 0, 100 if key == "allocations" else 3600) for k, v in values.items()}
            measured = sum(sim["runs"]) + sum(sim["stations"].values()) + sum(sim["transitions"])
            if measured > sim["total_seconds"]:
                raise Invalid("Split totals cannot exceed the total time.")
            sim["rpe"] = number(data.get("rpe", 0), "RPE", 0, 10)
            sim["difficulty"] = number(data.get("difficulty", 0), "difficulty", 0, 10)
            for key in ("scaled", "comparable", "full_distance"):
                if key in data:
                    if not isinstance(data[key], bool):
                        raise Invalid(f"{key} must be true or false.")
                    sim[key] = data[key]
            for key in ("notes", "pacing_notes", "fuelling_notes", "transition_notes"):
                sim[key] = text(data.get(key, ""), key, 4000)
            db.execute("INSERT INTO simulation_results VALUES (?,?,?,?) ON CONFLICT(team_id,date) DO UPDATE SET data=excluded.data", (secrets.token_hex(16), team_id, sim["date"], encoded(sim)))
            return {"ok": True, "analysis": coach.simulation_analysis(state["race"], [s for s in state["simulations"] if s["date"] != sim["date"]] + [sim])}
        if path == "/api/workouts/external" and method == "POST":
            day = iso_date(data.get("date"))
            if day in (state["race"]["date"], state["race"]["simulation_date"]):
                raise Invalid("Race and simulation events cannot be replaced by a class.")
            intensity = data.get("intensity", "moderate")
            if intensity not in ("easy", "moderate", "hard", "recovery"):
                raise Invalid("Invalid class intensity.")
            main = data.get("main", [])
            if not isinstance(main, list) or len(main) > 30:
                raise Invalid("Invalid class structure.")
            workout = {"date": day, "title": text(data.get("title"), "class title", 150, True), "duration": number(data.get("duration", 60), "duration", 1, 180),
                       "intensity": intensity, "main": [text(v, "class instruction", 1000) for v in main], "type": "external"}
            db.execute("INSERT INTO external_activities VALUES (?,?,?) ON CONFLICT(user_id,date) DO UPDATE SET data=excluded.data", (user_id, day, encoded(workout)))
            return {"ok": True}
        if path == "/api/coach" and method == "POST":
            question = text(data.get("question"), "question", 2000, True)
            return coach.coach_reply(question, state["profile"], state["race"], state["logs"], state["checkin"], state["simulations"])
        if path == "/api/scenario" and method == "POST":
            pace = number(data.get("run_pace_seconds"), "run pace seconds/km", 120, 900)
            stations = data.get("station_seconds", [])
            transitions = data.get("transition_seconds", [])
            if not isinstance(stations, list) or len(stations) != 8 or not isinstance(transitions, list) or len(transitions) != 8:
                raise Invalid("Enter eight station times and eight transition times.")
            return coach.race_scenario(pace, [number(v, "station seconds", 1, 3600) for v in stations], [number(v, "transition seconds", 0, 600) for v in transitions])
        raise Invalid("Unknown endpoint or method.")

    def static(self, path):
        if self.command != "GET":
            return self.respond(405, {"error": "Method not allowed."})
        if path.startswith("/static/"):
            path = path[len("/static"):]
        path = "/index.html" if path == "/" else path
        # Explicit allowlist prevents traversal and exposing source/database files.
        if path not in STATIC_ASSETS:
            return self.respond(404, {"error": "Not found."})
        file, content_type = STATIC_ASSETS[path]
        if not file.is_file():
            return self.respond(404, {"error": "Not found."})
        content = file.read_bytes()
        self.send_response(200)
        self.headers_common()
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        if path == "/sw.js":
            self.send_header("Service-Worker-Allowed", "/")
        self.end_headers()
        self.wfile.write(content)

    do_GET = dispatch
    do_POST = dispatch
    do_PUT = dispatch
    do_DELETE = dispatch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["serve", "reset-password"], default="serve")
    parser.add_argument("email", nargs="?")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    initialize()
    if args.command == "reset-password":
        if not args.email:
            parser.error("reset-password requires the account email")
        with connect() as db:
            token = mint_reset(db, email_value(args.email))
        if token:
            print(f"{PUBLIC_URL}/?reset={token}")
        else:
            print("Account not found.")
        return
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.daemon_threads = True
    print(f"HYROX Coach listening on {args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
