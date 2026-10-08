# HYROX Coach — Kenza & Rob

A mobile-first, offline-capable coach for Mixed Doubles: individual training and
readiness, shared simulations and race strategy, and explainable coaching rules.
The London race on **December 2, 2026** is the initial use case, not a prediction
of future performance. No LLM, external analytics, or paid services are required.

## Run

Requires Python **3.12+**. No third-party Python/npm runtime dependencies.
Optional local board-photo OCR uses the system Tesseract executable.

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

### Additional workouts

Use **Log additional workout** on Home, Plan, Progress, or a workout's detail
page to record a second (or third) session, including on dates without a plan.
Give each session its own title, type, date, duration, RPE, optional time and
notes. Find and edit it in **Progress → Session history**. Additional sessions
save offline and sync with your account, just like planned workout logs.
They all contribute to training totals, weekly load and readiness, but do not
replace or mark the scheduled workout complete. **Add / edit class** still
replaces the planned session; choose an additional workout to keep both.

### Private board photos and local OCR

**Log this workout**, **Log additional workout**, and **Add / edit class** accept
one optional board photo per log/class. Choose JPEG, PNG or WebP, or use the
camera option on supported phones. The browser rejects sources over 12 MB,
12,000 pixels per side or 40 megapixels, strips metadata by re-encoding to JPEG,
and reduces to at most 1600 pixels per side and 200 KB. Keep the board tightly
framed for readable text. Replace/remove a photo in the same form and save;
cancel leaves the stored photo unchanged. Photos are SQLite blobs, never public
files, and only the originating athlete can retrieve them (not their teammate).

**Extract board text** is optional local OCR on your own server. Review the
editable text, correct handwriting, reps and loads, then explicitly **Apply
reviewed text** to instructions and save the form. It does not guess exercises,
duration or RPE, or change completion status. Adding a class updates the plan,
not the completion log. Instructions remain editable manually if OCR is absent,
unreadable, offline or times out. OCR output is limited to 8,000 characters;
class instructions allow 30 lines of at most 1,000 characters each.

Install the optional system engine **on the server/deployment host**:

```sh
# Debian / Ubuntu / Codespaces (also install in your deployment image):
sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
# macOS:
brew install tesseract
```

On Windows, install Tesseract with English language data and add its executable
directory to the server process's `PATH`. Restart the server after changing
`PATH`. No Python/npm packages, external OCR APIs, CDNs or photo transfers to
third parties are used. The server enforces authenticated, CSRF-protected OCR,
an 8-second timeout, 20 attempts per athlete per hour, and one running request
per athlete (two globally). Maintain the system engine's security updates.

Workout photos/instructions save in the athlete-scoped offline queue and sync
with the log. Saved photos are cached privately in IndexedDB when uploaded or
viewed; a never-viewed photo needs a connection initially. Class creation/edit
and OCR require a connection. Private API responses bypass service-worker
caches. Signing out clears private device data, including photos and the queue.
Back up the database to preserve photos together with workout records.

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

### If the forwarded page shows HTTP 401

The app's home page does not require a login. A browser error page showing
**HTTP 401** at the forwarded root URL usually means GitHub's private-port
authentication rejected the browser, not that you need an app account.

1. Open the Codespace in a browser signed into the GitHub account that owns it,
   then use **Ports → 8000 → Open in Browser** in that same browser profile.
   A copied URL in another browser, account, or private window may not have the
   required GitHub session.
2. Keep port visibility **Private** and its **Port Protocol** set to **HTTP**:
   the Python server speaks HTTP inside the container; GitHub supplies HTTPS
   for the external browser URL.
3. If it still fails, sign into GitHub again and reopen the port from the Ports
   tab. Check whether browser privacy settings or extensions block the GitHub
   authentication flow. Do not paste access tokens into URLs or share them.
4. In the Codespace terminal, check the server separately from GitHub's gateway:

   ```sh
   curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/
   ```

   Expect **200** without an app login. If the connection fails, inspect
   `/tmp/hyrox-coach.log`, then stop/start the Codespace. If it predates the
   dev-container configuration, pull this branch's changes and run
   **Codespaces: Rebuild Container** from the command palette.

### If the local check reports 000 or connection refused

`000` is curl's indication that it received no HTTP response, not an HTTP status
from the app. A listed forwarded port does not start a server. From the repository
root in the **Codespace terminal**, start the server in the foreground:

```sh
export PUBLIC_URL="https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
export ALLOWED_HOSTS="${PUBLIC_URL#https://},localhost:8000,127.0.0.1:8000"
python3 server.py --host 0.0.0.0 --port 8000
```

Leave that terminal running. Expect `HYROX Coach listening on 0.0.0.0:8000`.
In a second terminal, repeat the local curl check; once it returns **200**, open
port 8000 from **Ports**. This command retains the forwarded HTTPS origin and
secure cookies, unlike starting with the localhost defaults.
If the command exits, share the displayed error (without credentials), rather
than repeatedly reopening the browser. If it reports `Address already in use`,
do not start another copy: inspect the existing server and repeat the local
check. This recovery does not delete the database.

Do not make the port public to bypass authentication: that exposes this unfinished
preview to anyone with its URL. See GitHub's
[port-forwarding documentation](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace).

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

### Precise workout prescriptions and references

App-programmed sessions specify run metres or minutes, main distance totals for
intervals, each exercise's sets/reps or metres, effort, rest, and timed warm-up/
cooldown. Alternating Thursday sessions cover SkiErg/sled push/carries/lunges and
rowing/sled pull/burpee broad jumps/wall balls; these are scaled technique doses,
not full race volumes. Progression still requires comfortable recorded training
and recovery. Readiness reductions replace the actual quantities, not just the
duration label. Durations are estimates including work and rest, not deadlines.

These are **original, conservative app prescriptions**, not copied commercial
HYROX programmes. Internet programme/rulebook retrieval was unavailable during
this update; no external plan or current rule was verified. The full simulation
and race list all eight runs and configured station quantities/loads in order.
Existing `STATIONS` defaults are **unverified race references**, not recommended
novice loads: confirm your division's current
[official HYROX rulebook](https://hyrox.com/rulebooks/) and equipment before racing.
Choose pain-free, technically manageable training resistance on your actual sled
surface; record sled mass, kg per carry implement, ball load and target height.
Use the explicitly scaled rehearsal instead of a full simulation unless the full
distances and loads are already safely established; record it as scaled.

External classes remain content-pending until instructor instructions or reviewed
board-photo text supply exact distances/times, exercises, sets/reps, loads and
rest. Their attendance estimates do not invent an instructor's workout.

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

### Lowest-cost hosting choices

[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
hosts static HTML/CSS/JavaScript only. It cannot run this app's Python API,
authentication, coaching engine, or SQLite database. Publishing `static/` alone
would not produce a working app. A Pages-only, device-local app would require a
different architecture and would lose the current shared-team backend.

- **No hosting bill:** run locally on an existing computer for testing. This is
  not an always-on internet deployment. Codespaces is also a preview, with
  account quotas and possible usage charges.
- **Potential $0 internet hosting:** an
  [Oracle Cloud Always Free VM](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm)
  can run Python and persistent storage within its free allowances. Availability,
  account eligibility, and idle-instance reclamation make it a conditional
  option, not a guaranteed always-on service. You must maintain the VM, HTTPS,
  security updates, and off-server backups; avoid chargeable resources.
- **Low-maintenance paid option:** a Render Starter web service with a 1 GB
  persistent disk has an indicative base cost of **US$7.25/month**
  ($7 compute + $0.25 storage). Confirm
  [current pricing](https://render.com/pricing), taxes, and usage charges before
  purchase. A provider subdomain avoids buying a domain. Render's free service
  has no persistent disk and is unsuitable for keeping this SQLite database
  across restarts/deployments; see
  [persistent disks](https://render.com/docs/disks).

For the lowest cash cost, try the free VM only if you accept its maintenance and
availability limitations. For easier operation, budget for the paid managed
service rather than risking training data on ephemeral storage. Neither is
provisioned by this repository. Provider account setup and any charges require
your approval. Finish the outstanding app review fixes and security/end-to-end
checks before deploying real data. Keep a single app instance with persistent
SQLite storage and tested backups whichever host you choose.

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
