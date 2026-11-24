# ClassLY — Architecture

## 1. Layers

```
Camera ──► live_attendance ──► SQLite ──► services ──► API ──► Frontend
           (face recognition)             (logic)     (HTTP)   (Plotly)
```

| Layer | Directory | Rule |
|---|---|---|
| Presentation | `frontend/` | No business logic; renders whatever the API returns |
| API | `app/api/` | Routing, validation, HTTP status codes only |
| Services | `app/services/` | All business logic and ML |
| Data | `app/database/` | SQL, schema, migrations |

The one rule that matters: **a number is computed in exactly one
place.** `app/api/dashboard.py` used to duplicate the whole
dashboard service, which is how the Excel report and the web page
started disagreeing. The router is now a thin wrapper over
`app/services/dashboard.py`.

```
app/services/attendance.py      calculate_attendance_time()
            │
            ▼
app/services/dashboard.py       get_dashboard_summary()   ← single source of truth
            │                            │
            ▼                            ▼
/api/dashboard/summary          app/services/reports.py (Excel)
            │
            ▼
app/services/analytics.py       cross-session aggregation
            │
            ▼
app/services/ml.py              K-Means + logistic regression
```

## 2. Data model

```
students            id, student_code, full_name, active
classes             id, course_name, class_date, quarter, group_name,
                    session_started_at, session_stopped_at
attendance_events   id, student_id, class_id, event_type(ENTRY|EXIT), timestamp
intruder_events     id, class_id, timestamp, snapshot_path
```

Design decisions:

- **Events, not states.** The database stores raw ENTRY/EXIT
  events. Every percentage is derived at read time. A bug in the
  attendance formula is therefore fixable retroactively; a bug in a
  stored percentage is not.
- **UTC everywhere in storage, local time only for display.**
  Timestamps are stored as UTC ISO strings and converted through
  `CLASSLY_TIMEZONE` (`America/Merida`) at the boundary.
- **The real session defines attendance, not the timetable.**
  Attendance is measured between `session_started_at` and
  `session_stopped_at`. The legacy `start_time` / `end_time`
  columns are kept only for database compatibility.
- **A session is identified by subject + date + quarter + group.**
  This is what lets the coordinator compare group A against group B
  of the same course.
- **Migrations are idempotent.** `initialize_database()` inspects
  `PRAGMA table_info` and issues `ALTER TABLE` only for missing
  columns, so an existing `classly.db` keeps working.

## 3. Attendance calculation

For a student in a session:

1. Take the session interval `[start, end]`.
2. Discard events outside that interval.
3. Pair each ENTRY with the next EXIT; an ENTRY left open is
   closed at `end`.
4. `inside = Σ(exit − entry)`, capped at the session duration.
5. `percentage = inside / duration × 100`.
6. Status: `≥ 80% → Present`, `> 0% → Partial`, else `Absent`.

A student who never entered has `outside = 0`, not
`outside = duration`: they were not "outside the classroom", they
were not in the session at all. Conflating the two inflates the
outside-time chart with people who never showed up.

## 4. Frontend

Three pages, one stylesheet, one vendored Plotly build, no build
step and no framework. Each page owns a single JS file and talks
only to its own endpoints.

Charts used per stage:

| Stage | Visuals |
|---|---|
| 1 · During class | Stat cards, live clock, attendance bars, entry/exit bars, inside vs outside |
| 2 · After class | Student × session heatmap, course trend, **occupancy curve**, **presence bands**, cluster scatter, risk table |
| 3 · End of course | Group ranking, per-group evolution, **attendance vs stability quadrant** |

The bolded ones are the visualizations that only exist because
attendance is measured continuously rather than as a boolean.

## 5. Known limitations

- Attendance events depend on face detection quality; a missed
  detection is indistinguishable from a real exit.
- `students` is global rather than per-course, so every active
  student appears in every scope.
- The occupancy curve is sampled at 30 s (adaptive up to 240
  points), so very short visits can be missed in the curve. They
  are still counted exactly in the percentages and in the bands.
- The ML models are trained on tens of samples. They are decision
  *aids*, and the UI says so.
