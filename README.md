# HYROX Coach — Kenza & Rob

A mobile-first, offline-capable coach for Mixed Doubles: individual training and
readiness, shared simulations and race strategy, and explainable coaching rules.
The London race on **December 2, 2026** is the initial use case, not a prediction
of future performance. No LLM, external analytics, or paid services are required.

## Run

Requires Python **3.12+**. There are no third-party runtime dependencies.

```sh
python3 server.py
# Alternatively: npm start
```

Open http://localhost:8000. Create Kenza's account, then give Rob the invitation
code shown on the Team screen. Rob signs up with his own email and password and
that code. Accounts without an invitation create separate, private teams. There
are **no default passwords** or publicly accessible athlete records.

Data lives in `data/coach.sqlite3`, survives restarts, and is excluded from Git.
Use `DATABASE_PATH` to choose a persistent volume. Back up this database using
SQLite's backup API (including live WAL data correctly); do not copy only the
main database file while the app is writing.

## Test in GitHub Codespaces

1. Open this pull request's branch on GitHub (not `main` until it is merged).
2. Select **Code → Codespaces → Create codespace on this branch**. Codespaces
   usage is subject to your account's quota and billing settings.
3. Wait for the development container to finish starting. It includes Python
   3.12 and automatically starts the app on port **8000**.
4. If the browser does not open automatically, open the **Ports** tab and click
   the forwarded address for port 8000. Keep port visibility **Private**.
   Use that HTTPS address, not `localhost:8000` on your own computer.
5. Create a test account, inspect the dashboard and training plan, log a workout,
   then refresh to check it persists. To test the shared team, create the second
   athlete's account using the invitation code from the Team screen.
6. To test offline workouts, first sign in and load the plan, then select
   **Offline** in browser developer tools' Network tab. View and log a cached
   workout, reconnect, and check that the sync indicator clears.

Run the automated tests in the Codespace terminal:

```sh
python3 -m unittest discover -s tests -v
```

Server output is in `/tmp/hyrox-coach.log`. The startup command configures
`PUBLIC_URL` and `ALLOWED_HOSTS` for the Codespace's forwarded HTTPS address so
signup, cookies, and origin checks work without disabling security protections.
Stopping and restarting the Codespace restarts the app; its database remains in
`data/coach.sqlite3`. Deleting the Codespace deletes that data, so use test data
and back up anything you want to keep. This is a development preview, not a
production deployment. Creating the Codespace requires your GitHub account;
the configuration does not provision one automatically.

## Features

- Signup/login/logout and one-use, expiring password reset.
- Seeded athlete profiles, September baseline (1:10:52), November 14 simulation,
  December 2 race, and target 1:05:00. Unknown splits remain unknown.
- An eight-week programme with gradual strength, sled and SkiErg development,
  compromised running, editable instructor-led weekend classes, simulation
  preparation, and taper. Race dates, goal, specifications and preferences are
  configurable.
- Start/modify/skip/complete workouts; session-specific metrics, perceived
  exertion, recovery, pain, timing and personal fuelling notes.
- Transparent readiness and incremental modifications, training load and weekly
  review. Missed sessions do not create catch-up training.
- Simulation comparison, measured station allocation, transitions, uncertain
  race projection and a what-if race calculator. Both partners run **all eight
  kilometres together**; running distance is never split between partners.
- Data-grounded conversational coaching without an LLM inventing workouts.
- Installable PWA with cached workout instructions and persistent offline logs.

## Gym mode

Open the application and sign in while online before leaving for the gym.
The app downloads the plan, station instructions/specifications, profile, targets
and recent history. The service worker caches the application shell, while
IndexedDB stores the signed-in athlete's data and pending workout events.
Cached workouts can be viewed and logged without a signal; pending saves retry
on reconnection. Check the sync indicator before signing out.
Each queued save is bound to its originating athlete and is rejected if the
authenticated account changes during replay.

Authenticated API responses are **not** put in the service-worker cache.
Device data is scoped to the last signed-in account. Signing out clears private
cached data; pending entries require confirmation before they are discarded.
Do not use offline storage on a shared/untrusted device: browser storage is not
an encrypted medical record. Clearing browser data removes unsynced logs.

On iPhone, use Safari's Share → Add to Home Screen. PWA installation and service
workers require HTTPS except on localhost. First-time signup, reset, team
updates, simulations and conversational coaching require connectivity; workout
viewing and logging are the offline core.

When deploying changes to frontend assets, update `SHELL_CACHE` in
`static/sw.js` too. This triggers an updated shell download for existing installs;
never add authenticated API URLs to that cache.

## Deployment and password reset

Run behind a TLS-terminating reverse proxy. The included Python HTTP server is
appropriate for this small private team, **not** a hardened public edge server.
The proxy should enforce request timeouts, connection/body limits and additional
rate limiting, preserve `Host`, and redirect HTTP to HTTPS.

```sh
PUBLIC_URL=https://coach.example.com \
ALLOWED_HOSTS=coach.example.com \
DATABASE_PATH=/var/lib/hyrox/coach.sqlite3 \
python3 server.py --host 127.0.0.1 --port 8000
```

`PUBLIC_URL` controls reset links, secure cookies, and origin checks.
`ALLOWED_HOSTS` is a comma-separated allowlist (include ports when applicable).
Never expose the database or source directory as a static web root. Keep the
SQLite volume access-controlled and supply configuration through environment
variables, not committed `.env` files.

For email delivery configure `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_FROM`,
and optionally `SMTP_USER` / `SMTP_PASSWORD`. SMTP uses verified STARTTLS.
Reset requests always return the same message, without exposing whether an
account exists or disclosing tokens. Links expire after 30 minutes; a successful
reset invalidates existing sessions.

For local development without SMTP, the administrator can generate a reset link:

```sh
python3 server.py reset-password athlete@example.com
```

Treat the output as a temporary credential and share it only with the athlete.
No password-reset tokens are logged by HTTP requests.

## Architecture

- `server.py`: same-origin HTTP API, authentication, input validation,
  ownership enforcement and SQLite persistence.
- `coach.py`: exercise/station library, phases, progression/readiness rules,
  simulation analytics, race projections, allocation and coaching explanations.
- `static/`: dependency-free responsive UI, IndexedDB offline queue, PWA shell.
- `tests/`: standard-library unit and HTTP integration tests.

Only comparable, full-distance simulations are race-projection anchors. Mark
scaled efforts accordingly: they remain in history without being presented as
full-race improvements. Comparable recent measurements can make a bounded,
explained adjustment; the displayed range is a heuristic, not a scientific
confidence interval.

Planned workouts, completions, readiness, personal nutrition notes, team
simulations, station specifications and coach adjustments have separate database
tables. Session-specific measurements are stored as structured JSON, so manual
entry can later share the same model with external activity import adapters.
Strava/Apple Health integrations and push notifications are **not implemented**;
the MVP does not depend on them.

```sh
python3 -m unittest discover -s tests -v
# Alternatively: npm test
```

The application is a fitness-planning tool, not medical care. It does not
diagnose injuries, prescribe insulin or make glucose-management decisions.
Follow your established diabetes-management plan and diabetes care team's
guidance. Significant pain should stop training; persistent or worsening pain
requires appropriate professional assessment. Fuelling reminders reflect
personal preferences, not medical prescriptions.
