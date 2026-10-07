"""Deterministic HYROX planning from declared preferences and recorded evidence.

Reference loads are mixed-doubles open assumptions, not event-rule verification.
Verify the current organiser rulebook and local sled mass/surface before loading.
"""

from datetime import date, timedelta
import math


STATIONS = [
    {"id": "ski", "name": "SkiErg", "distance": 1000, "unit": "m", "load": None,
     "exercises": ["SkiErg", "straight-arm pulldown"],
     "instruction": "Use relaxed hands, a hip hinge and smooth strokes; swap before form fades."},
    {"id": "sled_push", "name": "Sled push", "distance": 50, "unit": "m",
     "load": 152, "load_unit": "kg including sled", "includes_sled": True,
     "reference": "mixed doubles open assumption; verify event rules and actual sled mass",
     "exercises": ["sled push", "split squat"],
     "instruction": "Start light on your actual surface; short steps, stable trunk, no maximal testing."},
    {"id": "sled_pull", "name": "Sled pull", "distance": 50, "unit": "m",
     "load": 103, "load_unit": "kg including sled", "includes_sled": True,
     "reference": "mixed doubles open assumption; verify event rules and actual sled mass",
     "exercises": ["sled rope pull", "seated row"],
     "instruction": "Practise safe rope handling inside the lane and steady backward steps."},
    {"id": "burpees", "name": "Burpee broad jumps", "distance": 80, "unit": "m", "load": None,
     "exercises": ["burpee broad jump", "standing broad jump"],
     "instruction": "Use repeatable, controlled jumps; practise organiser movement standards."},
    {"id": "row", "name": "Row", "distance": 1000, "unit": "m", "load": None,
     "exercises": ["rowing", "hip hinge"],
     "instruction": "Legs, trunk, then arms; return arms, trunk, then legs without rushing."},
    {"id": "farmers", "name": "Farmers carry", "distance": 200, "unit": "m",
     "load": 24, "load_unit": "kg each", "implements": 2,
     "reference": "mixed doubles open assumption; verify event rules",
     "exercises": ["farmers carry", "grip holds"],
     "instruction": "Stay tall, keep implements close and plan controlled swaps."},
    {"id": "lunges", "name": "Sandbag lunges", "distance": 100, "unit": "m",
     "load": 20, "load_unit": "kg",
     "reference": "mixed doubles open assumption; verify event rules",
     "exercises": ["sandbag walking lunge", "reverse lunge"],
     "instruction": "Start with bodyweight; keep stable knees and practise current depth standards."},
    {"id": "wall_balls", "name": "Wall balls", "distance": 100, "unit": "reps",
     "load": 6, "load_unit": "kg",
     "reference": "mixed doubles open assumption; verify event rules and target heights",
     "exercises": ["wall ball", "goblet squat"],
     "instruction": "Choose manageable sets with clean depth and the correct athlete-specific target."},
]


def _number(value, default=None, minimum=None, maximum=None):
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return default
    if not math.isfinite(result):
        return default
    if minimum is not None and result < minimum:
        return default
    if maximum is not None and result > maximum:
        return default
    return result


def _date(value, default=None):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return default


def _affirmed(value):
    return value is True or value == 1 or isinstance(value, str) and value.lower() in ("yes", "true", "1")


def _completed(logs, start=None, end=None):
    return [log for log in logs if isinstance(log, dict)
            and (log.get("status") == "completed" or
                 log.get("status") == "modified"
                 and _number(log.get("duration"), 0, 0, 1440) > 0
                 and _number(log.get("rpe"), 0, 0, 10) >= 1)
            and _date(log.get("date")) is not None
            and (start is None or _date(log["date"]) >= start)
            and (end is None or _date(log["date"]) <= end)]


def default_profile(person):
    """Seed the supplied athlete history; benchmarks are not race predictions."""
    name = str(person or "Athlete")
    profile = {"name": name, "person": name,
            "goals": "Finish HYROX together; build sustainable running and station technique",
            "benchmark_seconds": None, "benchmark_distance_km": 10,
            "easy_pace": "Conversational effort; use a measured benchmark to personalise pace",
            "easy_pace_seconds": None, "weaknesses": ["sled technique", "SkiErg technique"],
            "fuelling_preferences": "Familiar carbohydrate-rich food; water to thirst; normal recovery meal",
            "optional_activities": ["BodyAttack", "tennis"],
            "weekend_classes": {"saturday": "HYROX", "sunday": "HYROX"},
            "station_loads": {}}
    if name.lower() == "kenza":
        profile.update(benchmark_seconds=2645, benchmark_5k_seconds=1330,
                       partner_benchmark_seconds=2955, easy_pace_seconds=315,
                       easy_pace="5:15–5:30/km, conversational effort",
                       weaknesses=["sled_push", "sled_pull", "ski", "row", "fatigue management"],
                       strengths=["running", "burpees", "farmers", "lunges"],
                       station_ratings={"sled_push": "3–4", "sled_pull": "3–4", "ski": "2–3", "row": "2"},
                       fuelling_preferences="Follow your established fuelling and meal plan; set an evening meal reminder and avoid accidentally skipping dinner.",
                       notes="Running and specified station strengths; build novice sled/Ski technique and monitor fatigue. No diagnosis or carbohydrate/medication dose prescription.")
    elif name.lower() == "rob":
        profile.update(benchmark_seconds=2955, partner_benchmark_seconds=2645,
                       weaknesses=["burpees", "running"],
                       strengths=["sled_push", "sled_pull", "ski", "row", "farmers", "lunges"],
                       back_pain_history=True,
                       notes="Reported back-pain history: use pain-free ranges and seek qualified advice for symptoms; no diagnosis.")
    return profile


def readiness(logs, checkin, today=None):
    today = _date(today, date.today())
    recent = _completed(logs, today - timedelta(days=6), today)
    load = sum((_number(log.get("duration"), 0, 0, 1440) *
                _number(log.get("rpe"), 0, 0, 10)) for log in recent)
    hard = sum(_number(log.get("rpe"), 0, 0, 10) >= 7 for log in recent)
    score, reasons = 100, []
    signals = dict(checkin)
    latest = sorted(recent, key=lambda x: _date(x["date"]), reverse=True)
    for key in ("sleep", "soreness", "fatigue", "pain", "energy"):
        if _number(signals.get(key), minimum=0, maximum=24 if key == "sleep" else 10) is not None:
            continue
        for log in latest:
            metrics = log.get("metrics") if isinstance(log.get("metrics"), dict) else {}
            value = _number(log.get(key, metrics.get(key)), minimum=0, maximum=24 if key == "sleep" else 10)
            if value is not None:
                signals[key] = value
                reasons.append(f"Using last recorded {key} from completed training on {log['date']}; not a current measurement.")
                break
    if _number(signals.get("fatigue"), minimum=0, maximum=10) is None:
        energy = _number(signals.get("energy"), minimum=0, maximum=10)
        if energy is not None:
            signals["fatigue"] = 10 - energy
            reasons.append("Low recorded energy is treated as a conservative fatigue signal.")
    sleep = _number(signals.get("sleep"), minimum=0, maximum=24)
    if sleep is not None and sleep < 7:
        score -= min(30, (7 - sleep) * 10)
        reasons.append("Sleep is below seven hours.")
    for key in ("soreness", "fatigue", "pain"):
        value = _number(signals.get(key), minimum=0, maximum=10)
        if value is not None and value > 0:
            score -= value * (6 if key == "pain" else 3)
            if value >= 4:
                reasons.append(f"Reported {key} is elevated ({value:g}/10).")
    if hard >= 3:
        score -= 15
        reasons.append("Three or more hard sessions recorded in the last seven days.")
    prior = _completed(logs, today - timedelta(days=13), today - timedelta(days=7))
    prior_load = sum(_number(x.get("duration"), 0, 0, 1440) * _number(x.get("rpe"), 0, 0, 10)
                     for x in prior)
    if prior_load > 0 and load > prior_load * 1.3:
        score -= 10
        reasons.append("Recorded seven-day load exceeds the preceding week by over 30%; not a diagnosis.")
    pain = _number(signals.get("pain"), 0, 0, 10)
    fatigue = _number(signals.get("fatigue"), 0, 0, 10)
    score = round(max(0, min(100, score)))
    color = ("red" if score < 45 or pain >= 4 or fatigue >= 8 else
             "orange" if score < 65 else "yellow" if score < 85 else "green")
    if not reasons:
        reasons.append("No elevated warning in available records; missing check-in values are not measured.")
    if pain >= 4:
        reasons.append("Stop painful exercise and seek qualified assessment; this is not a diagnosis.")
    return {"color": color, "score": score, "reasons": reasons,
            "load_7d": round(load, 1), "hard_sessions": hard}


def _pace(profile):
    declared = str(profile.get("easy_pace") or "")
    if profile.get("easy_pace_override") and declared.strip():
        return declared
    if "/km" in declared:
        return declared
    explicit = _number(profile.get("easy_pace_seconds"), minimum=180, maximum=1200)
    benchmark = _number(profile.get("benchmark_seconds"), minimum=600, maximum=14400)
    if explicit is not None:
        return f"{int(explicit) // 60}:{int(explicit) % 60:02d}/km, slower if not conversational"
    if benchmark is not None:
        pace = round(benchmark / 10 + 75)
        return f"about {pace // 60}:{pace % 60:02d}/km (10 km benchmark + 75 sec/km); conversational effort wins"
    return str(profile.get("easy_pace") or "Conversational effort; no measured pace available")


def _fuel(profile, duration):
    preferences = profile.get("fuelling_preferences") or {}
    if not isinstance(preferences, dict):
        preferences = {"before": str(preferences)}
    if str(profile.get("person", "")).lower() == "kenza":
        return {"before": str(preferences.get("before") or "Follow your established fuelling plan with familiar foods."),
                "during": str(preferences.get("during") or "Follow your established plan and drink to thirst; practise only tolerated foods, without new carbohydrate-dose prescriptions."),
                "after": str(preferences.get("after") or "Follow your established recovery meal plan; set an evening reminder so dinner is not accidentally skipped."),
                "note": "Personal meal reminder, not glucose management. Discuss glucose concerns with your care team; no medication or insulin advice."}
    return {"before": str(preferences.get("before") or "Familiar carbohydrate-rich food 1–3 hours beforehand"),
            "during": str(preferences.get("during") or
                          ("Practise tolerated carbohydrate, roughly 30–60 g/hour, and drink to thirst"
                           if duration > 60 else "Water to thirst; carbohydrate optional for a short session")),
            "after": str(preferences.get("after") or "Normal meal with carbohydrate and protein"),
            "note": "Practise familiar foods; individual needs vary. No medication or insulin guidance."}


def _progression(logs, kind, day, today, state):
    weekday = 2 if kind == "strength" else 3
    prior = []
    for log in _completed(logs, end=min(day - timedelta(days=1), today)):
        metrics = log.get("metrics") if isinstance(log.get("metrics"), dict) else {}
        recorded_kind = log.get("type", metrics.get("type"))
        if recorded_kind == kind or recorded_kind is None and _date(log["date"]).weekday() == weekday:
            prior.append(log)
    prior.sort(key=lambda x: _date(x["date"]))
    eligible = [x for x in prior if _number(x.get("rpe"), minimum=0, maximum=7) is not None
                and _number(x.get("duration"), 0, 0, 1440) > 0]
    latest_ok = prior and prior[-1] in eligible
    recovered = (readiness(logs, {}, day - timedelta(days=1))["color"] == "green"
                 if day < today else day > today + timedelta(days=6) or state["color"] == "green")
    return len(eligible) if latest_ok and recovered else 0


def generate_plan(profile, race, logs, checkin, today=None, stations=None):
    start = _date(race.get("plan_start"), date(2026, 10, 8))
    race_date = _date(race.get("date"), date(2026, 12, 2))
    if not start <= race_date <= start + timedelta(days=55):
        start = race_date - timedelta(days=55)
    simulation = _date(race.get("simulation_date"), date(2026, 11, 14))
    today = _date(today, date.today())
    state = readiness(logs, checkin, today)
    easy = _pace(profile)
    benchmark = _number(profile.get("benchmark_seconds"), minimum=600, maximum=14400)
    partner_benchmark = _number(profile.get("partner_benchmark_seconds"), minimum=600, maximum=14400)
    pace_notes = [f"Easy pace: {easy}."]
    if benchmark is not None:
        pace = round(benchmark / 10 + 15)
        pace_notes.append(f"Individual controlled starting pace: {pace // 60}:{pace % 60:02d}/km (measured 10 km benchmark + 15 sec/km), not a race prediction.")
        shared = round(max(benchmark, partner_benchmark or benchmark) / 10 + 15)
        pace_notes.append(f"Shared running starts no faster than {shared // 60}:{shared % 60:02d}/km; both partners stay together and slow further after stations if needed.")
    classes = profile.get("weekend_classes") or {}
    options = profile.get("optional_activities") or []
    if isinstance(options, str):
        options = [options]
    options = {str(x).lower() for x in options}
    loads = profile.get("station_loads") or {}
    station_specs = STATIONS if stations is None else stations
    references = []
    for station in station_specs:
        load = _number(station.get("load"), minimum=0)
        if load is not None:
            label = station.get("load_unit") or ("kg including sled" if station.get("includes_sled") else "kg")
            references.append(f"{station.get('name', station['id'])}: {load:g} {label}")
    reference_text = "; ".join(references) or "No loaded-station race specifications available"
    weakness = ", ".join(str(x) for x in profile.get("weaknesses", [])) or "repeatable transitions"
    plan = []
    for offset in range(56):
        day = start + timedelta(days=offset)
        week = offset // 7 + 1
        days_to_race = (race_date - day).days
        phase = "foundation" if week <= 2 else "specific"
        if abs((day - simulation).days) <= 3:
            phase = "simulation"
        if 0 <= days_to_race <= 10:
            phase = "taper"
        title, kind, intensity, duration = "Rest and mobility", "rest", "easy", 0
        main = ["Rest, or ten minutes of comfortable mobility."]
        objective = "Absorb training without compensating for missed sessions."
        why = f"Week {week}: {phase}; recovery makes the quality sessions useful."
        # Simulation substitutes for that week's Thursday quality, never adds a third hard session.
        simulation_week = (simulation - start).days // 7
        in_simulation_week = offset // 7 == simulation_week
        if day == race_date:
            title, kind, intensity, duration = race.get("name", "HYROX race"), "race", "hard", 65
            main = ["Run all eight 1 km legs together; station work may be shared.",
                    f"Configured race reference loads: {reference_text}. Verify current organiser rules and equipment.",
                    "Use only practised swaps, food and equipment; target time is a goal, not a prediction."]
            objective = "Execute the rehearsed doubles strategy safely."
        elif day == simulation:
            title, kind, intensity, duration = "Measured doubles simulation", "simulation", "hard", 80
            main = ["Rehearse eight 1 km runs together and all eight stations at controlled race-like effort.",
                    f"Configured race reference loads: {reference_text}. Scale down unless already practised safely.",
                    "If full distance is not established, scale station work and record the scaling; not a comparable full-race time.",
                    "Coordinate the Saturday external HYROX class with its instructor; unknown class structure is not assumed to be a complete simulation.",
                    "Record total, individual run/station/transition splits, swaps and RPE; do not invent missing splits."]
            objective = "Establish actual pacing, allocations and fuelling evidence."
        elif day in (simulation - timedelta(days=1), simulation + timedelta(days=1),
                     simulation + timedelta(days=2)):
            title, kind, duration = "Simulation recovery", "recovery", 20
            main = ["Optional easy walk and mobility; rest if tired. No intervals or loaded sleds."]
            if day.weekday() in (5, 6):
                title, kind = "External HYROX class — recovery only", "class"
                main.append("Keep the external class appointment for observation/mobility only; instructor structure is unknown. Do not join hard work after simulation.")
        elif day > race_date:
            title, kind, duration = "Post-race recovery", "recovery", 20
            main = ["Rest or walk comfortably; postpone strenuous training until recovered."]
        elif days_to_race in (1, 2):
            title, kind, duration = "Pre-race freshen up", "recovery", 15
            main = ["Optional gentle jog or walk; prepare equipment. No hard training."]
        elif day.weekday() == 0:
            if "bodyattack" in options or "body attack" in options:
                title, kind, intensity, duration = "Optional moderate BodyAttack", "class", "moderate", 40
                main = ["Optional Monday class, low-impact and moderate effort only. Skip it when weekend classes leave fatigue.",
                        "If the class becomes hard, log its real RPE and replace—not add to—the next hard session."]
            else:
                title, kind, duration = "Easy recovery after weekend HYROX", "recovery", 25
                main = [f"Optional conversational jog at {easy}, walk or mobility."]
            if phase == "taper":
                title, kind, intensity, duration = "Easy taper recovery", "recovery", "easy", 20
                main = ["Skip BodyAttack; optional gentle movement only."]
        elif day.weekday() == 1:
            title, kind, duration = "Tuesday recovery — drop spin", "recovery", 20
            main = ["Rest or easy walk and mobility. Drop Tuesday spin rather than stack another class.",
                    "Do not make up missed workouts; arrive fresh for Wednesday strength."]
        elif day.weekday() == 2:
            title, kind, intensity, duration = "Progressive novice strength — replaces BodyPump", "strength", "moderate", 45
            earned = _progression(logs, "strength", day, today, state)
            sets = 3 if week >= 5 and earned >= 4 else 2
            reps = 8 if sets == 3 or earned < 2 else 10
            if phase in ("simulation", "taper"):
                sets, reps, duration = 1 if phase == "taper" else 2, 6, 25
            main = [f"Core: {sets} × {reps} goblet squat or bodyweight squat, light Romanian deadlift (RDL)/hip hinge, and seated/dumbbell row; rest 60–90 seconds.",
                    f"Choose two accessories: {sets} × 6 each-side split squat, assisted pull-up/straight-arm pulldown, light dumbbell press, or {sets} × 20 m farmers carry.",
                    "Start with bodyweight/light loads, leave 3–4 comfortable repetitions in reserve; no 1RM test or percentages of an untested maximum.",
                    "Progress repetitions first; increase load by the smallest available increment only after two comfortable, technically clean sessions. Hold or reduce when fatigued.",
                    f"Progression gate: {earned} eligible completed prior strength sessions with RPE ≤7 and green recovery. No logged evidence means maintain the starting dose; weekly dates alone do not earn increases.",
                    "Dedicated strength replaces BodyPump; do not do both."]
            objective = "Build repeatable novice strength for sleds, pulling and load tolerance."
            if profile.get("back_pain_history"):
                main.append("Rob's reported back-pain history: keep hinges and carries pain-free, reduce range/load or use supported alternatives. Stop painful work and seek qualified assessment; no diagnosis.")
        elif day.weekday() == 3:
            title, kind, intensity, duration = "Thursday HYROX compromised running", "hyrox", "hard", 45 + min(week, 5) * 3
            earned = _progression(logs, "hyrox", day, today, state)
            duration = 45 + min(earned, 5) * 3
            rounds = min(2 + earned // 2, 2 if week <= 2 else 3 if week <= 4 else 4)
            run_metres = min(500 + earned * 100, 500 if week <= 2 else 750 if week <= 4 else 1000)
            ski = min(200 + earned * 50, 200 + (week - 1) * 75, 500)
            main = [f"{rounds} rounds: {run_metres} m controlled run together, {ski} m SkiErg, 10 m light sled push or pull; recover 2 minutes.",
                    *pace_notes,
                    "Light sled resistance on your actual surface; progress only a small increment after comfortable technique. No novice 1RM test or automatic jump to race load.",
                    f"Progression gate: {earned} eligible completed prior HYROX sessions at RPE ≤7 with green recovery. Optional extra rounds/metres require this evidence; no automatic week-index load increase.",
                    f"Technique focus: {weakness}. Keep both partners together on every run; never allocate running distance.",
                    f"Configured race references: {reference_text}. Verify rules, actual sled mass and surface; these are not novice training prescriptions."]
            if loads:
                main.append(f"Configured training loads (not independently verified): {loads}. Technique and surface govern progression.")
            objective = "Progress station-to-run tolerance while preserving measured, shared sustainable pacing."
            if in_simulation_week or phase == "taper":
                title, intensity, duration = "Thursday easy HYROX technique", "easy", 25
                main = [f"Easy running at {easy}; a few relaxed Ski strokes and unloaded sled rehearsals, no hard intervals.",
                        "Simulation replaces this week's quality; taper trims volume rather than cramming work."]
        elif day.weekday() == 4:
            if "tennis" in options and phase != "taper":
                title, kind, intensity, duration = "Optional moderate Friday tennis", "tennis", "moderate", 35
                main = ["Optional relaxed drills, not a hard match; skip if tired before weekend HYROX.",
                        "Competitive tennis counts as hard and replaces a planned hard session, never an addition."]
            else:
                title, kind, duration = "Friday recovery", "recovery", 20
                main = ["Gentle mobility or walk; keep energy for weekend classes."]
        elif day.weekday() in (5, 6):
            label = "saturday" if day.weekday() == 5 else "sunday"
            activity = str(classes.get(label) or "HYROX")
            title, kind, intensity, duration = f"External {activity} class — {label}", "class", "moderate" if day.weekday() == 5 else "hard", 50
            main = ["Mandatory external HYROX class slot; instructor structure is unknown, so no invented rounds or loads.",
                    "Saturday is moderate technique; Sunday is the second planned hard session alongside Thursday.",
                    "Ask the instructor to scale Saturday to moderate effort. If both classes are actually hard, record real RPE and reduce Thursday rather than adding hard work.",
                    "When running in doubles practice, both partners cover every run together."]
            objective = "Integrate real instructor-led classes without inventing their content or a third hard session."
            if phase == "taper":
                intensity, duration = "easy" if days_to_race <= 4 else "moderate", 25
                main.append("Taper attendance is technique/observation only, no exhausting full-race work.")
        workout = {"id": day.isoformat(), "date": day.isoformat(), "title": title, "type": kind,
                   "intensity": intensity, "duration": duration, "phase": phase,
                   "objective": objective, "why": why,
                   "warmup": "5–10 minutes easy movement and task-specific rehearsal" if duration else "Not required",
                   "main": main, "cooldown": "5 minutes easy movement; no painful stretching" if duration else "Not required",
                   "metrics": ["duration", "rpe", "notes"] + (["total_seconds", "runs", "stations", "transitions"]
                                                             if kind in ("simulation", "race") else []),
                   "fuelling": _fuel(profile, duration)}
        workout["external"] = day.weekday() in (5, 6) or (kind == "class" and day.weekday() == 0)
        plan.append(workout)
    # Enforce two hard sessions per anchored seven-day block, including external classes.
    for index in range(0, 56, 7):
        block = plan[index:index + 7]
        hard = [x for x in block if x["intensity"] == "hard"]
        if len(hard) > 2:
            keep = sorted(hard, key=lambda x: (x["type"] not in ("race", "simulation", "class"), x["date"]))[:2]
            for workout in hard:
                if workout not in keep:
                    workout.update(title="Easy run replacing quality", intensity="easy", duration=25,
                                   main=[f"Conversational run at {easy}; no extra intervals."])
                    workout["why"] += " External hard class replaces quality; maximum two planned hard sessions."
    # A simulation can straddle anchored weeks; cap every rolling seven-day window too.
    accepted = []
    hard = sorted((x for x in plan if x["intensity"] == "hard"),
                  key=lambda x: (x["type"] not in ("race", "simulation"), x["date"]))
    for workout in hard:
        dates = sorted(accepted + [_date(workout["date"])])
        overloaded = any(sum(0 <= (other - day).days <= 6 for other in dates) > 2
                         for day in dates)
        if overloaded:
            workout.update(title="Easy recovery replacing quality", intensity="easy", duration=25,
                           main=[f"Easy conversational movement at {easy}; no hard intervals or classes."])
            workout["why"] += " Protect simulation recovery and a maximum of two hard sessions in any seven days."
        else:
            accepted.append(_date(workout["date"]))
    # Short-lived check-ins reduce the next week's risk, not an entire week of rest.
    completed_dates = {str(x["date"])[:10] for x in _completed(logs, end=today)}
    for workout in plan:
        day = _date(workout["date"])
        if day.isoformat() in completed_dates:
            continue
        if today <= day <= today + timedelta(days=6) and state["color"] != "green" and workout["duration"]:
            immediate = day <= today + timedelta(days=2)
            event = workout["type"] in ("race", "simulation")
            if event and not (immediate and state["color"] == "red"):
                workout["adjustment"] = {"what": "Reassess participation; defer if pain or severe fatigue persists",
                                         "why": "; ".join(state["reasons"]),
                                         "effect": "No time projection or promise overrides symptoms."}
            elif immediate and state["color"] == "yellow":
                workout["duration"] = round(workout["duration"] * .8)
                workout["main"].append("Yellow readiness: complete approximately 80% of the listed work/time while keeping the planned controlled intensity; do not cram the full work into less time.")
                workout["adjustment"] = {"what": "Reduce volume about 20%; maintain planned intensity",
                                         "why": "; ".join(state["reasons"]),
                                         "effect": "Shorter controlled session; reassess tomorrow."}
            elif immediate:
                red = state["color"] == "red"
                external = workout.get("external")
                workout.update(title="Recovery adjustment", type="recovery", intensity="easy",
                               duration=0 if red else min(25, workout["duration"]),
                               main=["Rest; stop painful exercise and seek qualified assessment." if red
                                     else f"Short easy movement at conversational effort; no intervals or heavy stations."])
                if external:
                    workout["main"].append("External HYROX class slot remains reserved; observe only or notify the instructor rather than join hard work.")
                    if day.weekday() in (5, 6):
                        workout["type"] = "class"
                        workout["title"] = "External HYROX class — rest/observe only" if red else "External HYROX class — recovery only"
                if event:
                    workout["type"] = "race" if day == race_date else "simulation"
                    workout["title"] = "Event deferred — red readiness; rest"
                workout["adjustment"] = {"what": "Rest" if red else "Reduce to easy recovery",
                                         "why": "; ".join(state["reasons"]),
                                         "effect": "Lower immediate load; missed training is not made up."}
            else:
                optional = (workout["type"] == "tennis" or day.weekday() == 0 and workout["type"] == "class")
                if optional:
                    workout.update(title="Skip optional activity; reassess", type="rest", intensity="easy",
                                   duration=0, main=["Skip optional BodyAttack/tennis; reassess recovery before the next required session."])
                else:
                    workout["duration"] = round(workout["duration"] * .8)
                    if state["color"] in ("orange", "red") and workout["intensity"] == "hard":
                        workout["intensity"] = "moderate"
                    workout["main"].append("Provisional days 4–7 adjustment: reduce work/time by about 20%, then reassess with a fresh check-in. Do not assume today's fatigue lasts the whole week.")
                workout["adjustment"] = {"what": "Remove optional work" if optional else "Provisional volume reduction; reassess",
                                         "why": "; ".join(state["reasons"]),
                                         "effect": "Protect upcoming classes without prescribing seven days of rest."}
    return plan


def _simulations(simulations):
    valid = [s for s in simulations if isinstance(s, dict)
             and _date(s.get("date")) is not None
             and not s.get("scaled")
             and s.get("comparable") is not False
             and s.get("full_distance") is not False
             and _number(s.get("total_seconds"), minimum=1, maximum=604800) is not None]
    return sorted(valid, key=lambda s: _date(s["date"]))


def projection(race, simulations, logs, checkin):
    measured = _simulations(simulations)
    baseline = _number(race.get("baseline_seconds"), minimum=1, maximum=604800)
    seconds = measured[-1]["total_seconds"] if measured else baseline
    seconds = _number(seconds, minimum=1)
    rationale = ["The target is a goal, not a prediction."]
    if seconds is None:
        return {"seconds": None, "low": None, "high": None, "status": "unavailable",
                "goal_status": "unavailable",
                "evidence": {"type": "unavailable", "date": None, "anchor_seconds": None,
                             "log_adjustment_seconds": None, "comparisons": []},
                "rationale": rationale + ["No valid baseline or measured simulation total."]}
    rationale.append(f"Latest measured simulation ({measured[-1]['date']}) is the anchor."
                     if measured else "Declared race baseline is the anchor; no measured improvement assumed.")
    anchor = seconds
    comparisons = {}
    if measured:
        simulation = measured[-1]
        # Ordinary training splits are not race evidence: explicit comparability and
        # complete distances are required, with no inferred missing station work.
        for log in sorted(_completed(logs, _date(simulation["date"]) + timedelta(days=1), date.today()),
                          key=lambda x: _date(x["date"])):
            metrics = log.get("metrics") if isinstance(log.get("metrics"), dict) else {}
            values = dict(log, **metrics)
            if not (_affirmed(values.get("comparable_to_simulation")) or _affirmed(values.get("comparable"))):
                continue
            station_times = values.get("stations") or values.get("station_seconds") or {}
            if not isinstance(station_times, dict):
                station_times = {values.get("station"): station_times}
            old_stations = simulation.get("stations") or {}
            if isinstance(old_stations, dict):
                for station in STATIONS:
                    key = station["id"]
                    new = _number(station_times.get(key), minimum=1, maximum=604800)
                    old = _number(old_stations.get(key), minimum=1, maximum=604800)
                    distances = values.get("station_distances") or {}
                    distance = distances.get(key) if isinstance(distances, dict) else None
                    if values.get("station") == key:
                        distance = values.get("distance", distance)
                    full = _affirmed(values.get("full_distance")) or _number(distance) == station["distance"]
                    if new is not None and old is not None and full:
                        comparisons[key] = {"component": key, "date": log["date"], "previous_seconds": old,
                                            "recorded_seconds": new, "delta_seconds": max(-old * .1, min(old * .1, new - old))}
            old_runs, new_runs = simulation.get("runs"), values.get("runs")
            full_run = _affirmed(values.get("full_distance")) or _number(values.get("run_distance_km", values.get("distance_km"))) == 8
            if full_run and isinstance(old_runs, list) and len(old_runs) == 8:
                old_numbers = [_number(x, minimum=1, maximum=86400) for x in old_runs]
                new_numbers = ([_number(x, minimum=1, maximum=86400) for x in new_runs]
                               if isinstance(new_runs, list) and len(new_runs) == 8 else [])
                new = (sum(new_numbers) if new_numbers and all(x is not None for x in new_numbers)
                       else _number(values.get("run_seconds"), minimum=1, maximum=604800))
                if all(x is not None for x in old_numbers) and new is not None:
                    old = sum(old_numbers)
                    comparisons["runs"] = {"component": "runs", "date": log["date"], "previous_seconds": old,
                                           "recorded_seconds": new, "delta_seconds": max(-old * .1, min(old * .1, new - old))}
    delta = max(-anchor * .03, min(anchor * .03, sum(x["delta_seconds"] for x in comparisons.values())))
    seconds = anchor + delta
    if comparisons:
        rationale.append(f"Declared comparable full-distance training measurements adjust the anchor by {delta:+.1f} seconds. "
                         "Heuristic caps: 10% per measured component and 3% of total; different conditions/allocations invalidate comparisons.")
        rationale.extend(f"{x['component']} on {x['date']}: recorded {x['recorded_seconds']:g}s versus simulation {x['previous_seconds']:g}s."
                         for x in comparisons.values())
    state = readiness(logs, checkin, date.today())
    fraction = .06 if measured else .10
    if comparisons:
        fraction += .02
    high_fraction = fraction + {"red": .06, "orange": .04, "yellow": .02, "green": 0}[state["color"]]
    rationale.append("Uncertainty band is a planning heuristic, not a calibrated statistical confidence interval.")
    if state["color"] != "green":
        rationale.append(f"{state['color'].title()} readiness widens the slower bound; measured anchor is unchanged.")
    target = _number(race.get("target_seconds"), minimum=1, maximum=604800)
    goal_status = ("unavailable" if target is None else "on_track" if abs(seconds - target) <= target * .02
                   else "behind_target" if seconds > target else "ahead_target")
    evidence = {"type": "simulation" if measured else "baseline",
                "date": measured[-1]["date"] if measured else race.get("baseline_date"),
                "anchor_seconds": anchor, "log_adjustment_seconds": round(delta, 1),
                "comparisons": list(comparisons.values())}
    rationale.append("Goal status compares the estimate with a ±2% target tolerance; it is not a guarantee.")
    return {"seconds": round(seconds), "low": round(seconds * (1 - fraction)),
            "high": round(seconds * (1 + high_fraction)),
            "status": "measured" if measured else "baseline", "goal_status": goal_status,
            "evidence": evidence, "rationale": rationale}


def simulation_analysis(race, simulations):
    measured = _simulations(simulations)
    if not measured:
        return {"improvement": None, "gap": None, "percent": None,
                "split_improvements": {"runs": [], "stations": {}, "transitions": []},
                "opportunities": [], "rationale": "No valid measured simulation; no splits invented."}
    newest = measured[-1]
    previous = measured[-2] if len(measured) >= 2 else {}
    baseline = (_number(previous.get("total_seconds"), minimum=1)
                or _number(race.get("baseline_seconds"), minimum=1, maximum=604800))
    total = _number(newest["total_seconds"], minimum=1)
    target = _number(race.get("target_seconds"), minimum=1, maximum=604800)
    improvement = baseline - total if baseline is not None else None
    splits = {"runs": [], "stations": {}, "transitions": []}
    opportunities = []
    for key in ("runs", "transitions"):
        old, new = previous.get(key) or [], newest.get(key) or []
        if isinstance(old, list) and isinstance(new, list):
            for i, (a, b) in enumerate(zip(old, new)):
                a, b = _number(a, minimum=0), _number(b, minimum=0)
                if a is not None and b is not None:
                    splits[key].append({"index": i + 1, "seconds": round(a - b, 1)})
    old, new = previous.get("stations") or {}, newest.get("stations") or {}
    if isinstance(old, dict) and isinstance(new, dict):
        for station, value in new.items():
            a, b = _number(old.get(station), minimum=0), _number(value, minimum=0)
            if a is not None and b is not None:
                splits["stations"][station] = round(a - b, 1)
    if isinstance(new, dict):
        for station, value in sorted(new.items(), key=lambda item: _number(item[1], -1), reverse=True):
            seconds = _number(value, minimum=0)
            if seconds is not None:
                opportunities.append({"station": station, "seconds": seconds,
                                      "rationale": "Recorded station time to review, not guaranteed recoverable time."})
    return {"improvement": round(improvement, 1) if improvement is not None else None,
            "gap": round(total - target, 1) if target is not None else None,
            "percent": round(improvement / baseline * 100, 2) if improvement is not None else None,
            "split_improvements": splits, "opportunities": opportunities,
            "rationale": "Positive improvement means faster; positive gap means above target. Compare only equivalent full-distance simulations."}


def strategy(measurements, stations=None):
    result = []
    for station in STATIONS if stations is None else stations:
        key, name = station["id"], station["name"]
        evidence = measurements.get(key) or {}
        k = _number(evidence.get("kenza_seconds"), minimum=1, maximum=604800)
        r = _number(evidence.get("rob_seconds"), minimum=1, maximum=604800)
        row = {"station": key, "name": name, "kenza_share": None, "seconds": None,
               "confidence": "unavailable", "rationale": "Both athletes need comparable measured station times; no allocation guessed."}
        if k is not None and r is not None:
            kf = _number(evidence.get("kenza_fatigue"), 0, 0, 10)
            rf = _number(evidence.get("rob_fatigue"), 0, 0, 10)
            transition = _number(evidence.get("transition_seconds"), minimum=0, maximum=604800)
            preferred = _number(evidence.get("preferred_share"), minimum=0, maximum=1)
            # Discrete, reproducible cost using measured time and declared fatigue.
            candidates = [preferred] if preferred is not None else [x / 20 for x in range(21)]
            def cost(share):
                swap = transition if transition is not None and 0 < share < 1 else 0
                return k * share * (1 + kf / 20 * share) + r * (1 - share) * (1 + rf / 20 * (1 - share)) + swap
            share = min(candidates, key=lambda s: (cost(s), abs(s - .5)))
            seconds = k * share + r * (1 - share)
            if transition is not None and 0 < share < 1:
                seconds += transition
            row.update(kenza_share=share, seconds=round(seconds, 1), confidence="limited",
                       rationale="Linear estimate from comparable full-station measurements; fatigue is a declared heuristic, not a race guarantee. "
                                 + ("Preferred share honoured. " if preferred is not None else "Lowest fatigue-adjusted candidate selected. ")
                                 + ("Measured swap cost included when shared." if transition is not None
                                    else "Swap cost unknown and excluded; practise to validate."))
        result.append(row)
    return result


def race_scenario(run_pace_seconds, station_seconds, transition_seconds):
    """Pace is seconds per kilometre; station inputs are total shared work times."""
    pace = _number(run_pace_seconds, minimum=1, maximum=86400)
    def total(value):
        values = list(value.values()) if isinstance(value, dict) else value if isinstance(value, (list, tuple)) else [value]
        numbers = [_number(x, minimum=0) for x in values]
        return _number(sum(numbers), minimum=0, maximum=604800) if numbers and all(x is not None for x in numbers) else None
    stations, transitions = total(station_seconds), total(transition_seconds)
    if pace is None or stations is None or transitions is None:
        return {"seconds": None, "breakdown": None, "status": "unavailable",
                "rationale": "Finite nonnegative station/transition totals and positive seconds/km pace required."}
    runs = pace * 8
    return {"seconds": round(runs + stations + transitions, 1),
            "breakdown": {"runs": runs, "stations": stations, "transitions": transitions, "run_km": 8},
            "status": "scenario",
            "rationale": "What-if arithmetic, not a prediction. Both partners run all 8 km together; running is never divided."}


def weekly_summary(logs, plan, today=None):
    today = _date(today, date.today())
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    recorded = _completed(logs, start, today)
    sessions = [x for x in plan if start <= _date(x.get("date"), date.min) <= end]
    due = {x["date"] for x in sessions if _date(x["date"]) <= today and x.get("duration", 0) > 0}
    completed_dates = {str(x["date"])[:10] for x in recorded}
    planned_types = {x["date"]: x.get("type", "unknown") for x in sessions}
    by_type, kilometres, running_sessions = {}, 0, 0
    for log in recorded:
        metrics = log.get("metrics") if isinstance(log.get("metrics"), dict) else {}
        kind = str(log.get("type") or metrics.get("type") or planned_types.get(str(log["date"])[:10], "unknown"))
        by_type[kind] = by_type.get(kind, 0) + 1
        distance = _number(log.get("distance_km", metrics.get("distance_km",
                           metrics.get("run_distance_km"))), minimum=0, maximum=1000)
        if distance is None:
            metres = _number(metrics.get("run_distance_m"), minimum=0, maximum=1000000)
            if metres is not None:
                distance = metres / 1000
            elif metrics.get("unit") == "km" and not metrics.get("station"):
                distance = _number(metrics.get("distance"), minimum=0, maximum=1000)
        kilometres += distance or 0
        running_sessions += bool(distance and distance > 0 or kind == "run")
    duration = sum(_number(x.get("duration"), 0, 0, 1440) for x in recorded)
    load = sum(_number(x.get("duration"), 0, 0, 1440) * _number(x.get("rpe"), 0, 0, 10) for x in recorded)
    missed = {str(x.get("date"))[:10] for x in logs if isinstance(x, dict) and x.get("status") == "missed"
              and start <= _date(x.get("date"), date.min) <= today}
    return {"start": start.isoformat(), "end": end.isoformat(), "completed": len(recorded),
            "planned": sum(x.get("duration", 0) > 0 for x in sessions),
            "duration": round(duration, 1), "load": round(load, 1),
            "distance_km": round(kilometres, 2), "classes": by_type.get("class", 0) + by_type.get("external", 0),
            "strength_sessions": by_type.get("strength", 0), "running_sessions": running_sessions,
            "hyrox_sessions": sum(by_type.get(key, 0) for key in ("hyrox", "simulation", "race")),
            "sessions_by_type": by_type,
            "hard_sessions": sum(_number(x.get("rpe"), 0, 0, 10) >= 7 for x in recorded),
            "missed": len(missed - completed_dates),
            "remaining_due": len(due - completed_dates),
            "message": "Recorded completed sessions and exercised modified sessions contribute to load. Missed sessions are not made up."}


def coach_reply(question, profile, race, logs, checkin, simulations):
    text = str(question).lower()
    if any(word in text for word in ("insulin", "medication", "diagnos", "diabet", "chest pain")):
        answer = "I cannot diagnose conditions or advise on medication or insulin. Seek your qualified healthcare professional; stop exercise for concerning symptoms."
    elif any(word in text for word in ("fuel", "eat", "nutrition", "carb")):
        fuel = _fuel(profile, 75)
        answer = f"Before: {fuel['before']}. During: {fuel['during']}. After: {fuel['after']}. Practise tolerance; no medication advice."
    elif any(word in text for word in ("predict", "target", "time", "progress", "simulation")):
        estimate = projection(race, simulations, logs, checkin)
        if estimate["seconds"] is None:
            answer = "No valid baseline or measured simulation is available. Record a comparable simulation before estimating race time."
        else:
            answer = (f"Evidence anchor: {estimate['seconds']} seconds; planning range {estimate['low']}–{estimate['high']} seconds. "
                      + " ".join(estimate["rationale"]))
    elif any(word in text for word in ("split", "share", "partner", "allocation", "strategy")):
        answer = "Both partners run every 1 km leg together (8 km each). Allocate station work only from comparable measured times, fatigue and practised swap costs; missing evidence means no guessed shares."
    elif any(word in text for word in ("miss", "catch", "skip")):
        answer = "Do not make up missed sessions or stack hard days. Resume the next suitable planned session; reduce near-term load if your check-in indicates fatigue or pain."
    elif any(word in text for word in ("sled", "ski", "strength", "pump", "spin", "attack", "tennis")):
        answer = "Build SkiErg and sled technique gradually with light, repeatable work; no novice 1RM testing. Verify reference race loads, including sled mass. Wednesday progressive strength replaces Pump and Tuesday recovery replaces spin. Monday BodyAttack and Friday tennis are optional moderate work; Saturday HYROX is technique and Sunday HYROX is the second hard session alongside Thursday. Log actual instructor-led effort; do not add hard sessions."
    else:
        state = readiness(logs, checkin)
        answer = f"Readiness from available records: {state['color']} ({state['score']}/100). " + " ".join(state["reasons"]) + " Keep at most two planned hard sessions weekly and prioritise consistent easy work."
    return {"answer": answer, "source": "Recorded data and deterministic coaching rules; not medical advice."}
