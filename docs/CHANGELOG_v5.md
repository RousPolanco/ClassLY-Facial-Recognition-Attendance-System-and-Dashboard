# ClassLY — v5 changes

## 1. Excel report no longer disagrees with the dashboard

**Problem.** The spreadsheet and the web page were two independent
implementations of the same calculation. `app/services/reports.py`
called `calculate_attendance_time()` directly, while the web page was
served by a *third* copy of the logic duplicated inside
`app/api/dashboard.py`. Any fix applied to one copy left the other
behind, which is exactly what happened with the "Outside (min)" column.

**Fix.** A single source of truth:

```
app/services/dashboard.py  ──►  get_dashboard_summary(class_id)
        │                                │
        ▼                                ▼
/api/dashboard/summary          app/services/reports.py
     (web dashboard)              (Excel export)
```

`app/api/dashboard.py` is now a thin router that re-exports the service
helpers. The Excel report reads the same rounded values the table shows,
so the two outputs cannot diverge.

## 2. Bug: zeroed inside/outside minutes

`calculate_attendance_time()` returns `minutes_inside` /
`minutes_outside`. `app/services/dashboard.py` was reading
`inside_minutes` / `outside_minutes`, so `dict.get(..., 0)` silently
returned `0` for every student. Fixed.

## 3. Session start and end in the report

The report used to print the raw UTC ISO string
(`2026-09-17T22:26:29.449913+00:00`) and the unused legacy
`start_time` / `end_time` columns (always `00:00`). It now prints:

- Session Status (Not started / Running / Completed)
- Session Start and Session End in local time (`America/Merida`)
- Session Duration as `HH:MM:SS` and in minutes
- The timezone used

Per-student event counts in the report are the session-filtered counts,
matching the dashboard.

## 4. New academic context: Quarter/Semester and Group

- `classes.quarter` — INTEGER, 0–15, default 0
- `classes.group_name` — TEXT, A–Z, default 'A'

Both are added by an idempotent `ALTER TABLE` migration in
`initialize_database()`, so existing databases keep working.

A class session is now identified by **subject + date + quarter + group**
in `findSelectedClass()`, validated in `POST /api/classes`, shown in the
dashboard header and written into the report (and its filename).

## 5. Dashboard layout

The standalone "Entries" and "Exits" stat cards were removed; the
"Entry & Exit Activity" card is the single place those totals are shown.

---

# ClassLY — v6 changes

## 6. Decision stage 2 — after class

New page `/analytics` and service `app/services/analytics.py`:

- Student × session attendance heatmap.
- Course trend against the 80% threshold.
- **Occupancy curve**: classroom headcount reconstructed minute by
  minute from the raw events, with a retention axis.
- **Presence bands**: every continuous stay of every student inside
  the classroom during a session.
- Per-student indicators: average, consistency, trend, sessions
  attended and missed.

## 7. Decision stage 3 — end of course

New page `/coordinator`:

- Group ranking against the threshold.
- Attendance evolution per group across the quarter.
- Attendance-vs-stability quadrant, bubble size = students below
  the threshold.
- Sortable ranking table with a quarter filter.

## 8. Machine learning

New service `app/services/ml.py`, implemented from scratch in pure
Python (no scikit-learn dependency added):

- **K-Means** (k-means++ init, Lloyd iterations) over five
  behavioural features, with silhouette score reported in the UI.
- **Logistic regression** (batch gradient descent, L2) predicting
  whether a student will miss the 80% threshold next session,
  trained on a chronological split and reporting accuracy,
  precision, recall, F1 and the confusion matrix.
- Both degrade explicitly: with too little history the API returns
  `trained: false` plus a reason, and the UI says the numbers are
  observations rather than predictions.

## 9. Supporting changes

- `scripts/seed_demo_data.py` generates a synthetic course history
  so the new views can be demonstrated before enough real sessions
  exist; `--clear` removes it. The generated scope matches the
  professor's real assignment (Data Modeling for Information,
  9th quarter, groups A and B) rather than a placeholder course, so
  the demo appears where the professor will actually look. Every
  generated course is still prefixed `[DEMO]`, and a visible banner
  plus a per-row tag mark it as synthetic in both `/analytics` and
  `/coordinator`, so it can never be mistaken for a real recording.
- The intruder router was defined but never registered in
  `app/main.py`; it is now mounted at `/api/intruders`.
- Navigation between the three stages added to every page.
- `README.md` written, plus `docs/ARCHITECTURE.md`,
  `docs/ML_MODELS.md` and `docs/REQUIREMENTS_TRACEABILITY.md`.

---

# ClassLY — v7 changes

## 10. Bug fix: "Start Class" stuck after finishing a session

**Symptom.** After finishing a class (Stop Class), typing the name
of a *different*, brand-new class and pressing Start Class did
nothing useful — the button stayed labeled "Class Completed" and
disabled. The only apparent way out was Reset Class Data, which
deleted the just-finished class's real attendance data as a side
effect of unblocking the button.

**Root cause.** This was a frontend-only bug — the backend already
handled multiple independent classes correctly (verified directly
against the API: start class A, stop class A, start class B all
succeed with no errors). `updateSessionButtons()` sets the Start
button's label and disabled state from the *last loaded* class's
status. It is only invoked from `updateSessionInformation()`,
which runs after `loadDashboard()` — and `loadDashboard()` is only
called when the typed subject/date/quarter/group matches an
*existing* class. When the combination does not exist yet (a new
class), `updateSelectedClass()` calls `resetDashboardVisuals()`
instead, which cleared every stat and chart but never touched the
Start button. The button was left showing the previous class's
"Completed" state indefinitely.

**Fix.** `resetDashboardVisuals()` now also calls
`updateSessionButtons("Not started")`, so selecting a new class
always re-enables the Start button regardless of what the
previously viewed class's status was. No backend or data-model
change was needed. `Reset Class Data` continues to work exactly as
before for its real purpose: clearing a specific class's recorded
events.
