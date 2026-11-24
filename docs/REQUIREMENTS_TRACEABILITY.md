# ClassLY — Requirements traceability

Each requirement from the UA1 project brief, mapped to its
implementation and to the evidence a reviewer can check.

| # | Requirement | Implementation | Evidence |
|---|---|---|---|
| R1 | Visual aid for teachers to track attendance | Three Plotly dashboards over a FastAPI backend | `/`, `/analytics`, `/coordinator` |
| R2 | Move from boolean attendance to real time in the classroom | ENTRY/EXIT events; attendance = measured time inside ÷ session duration | `app/services/attendance.py`; Inside/Outside columns; occupancy curve |
| R3 | Use face recognition and tracking to extract student information | InsightFace `buffalo_l` embeddings + cosine matching; unknown faces logged as intruders | `app/services/face_recognition.py`, `live_attendance.py`, `scripts/live_camera.py` |
| R4 | Decision stage 1 — during class (professor, extraordinary situations) | Live dashboard: present/partial/absent counts, intruder alerts, running clock, live per-student table, auto-refresh every 5 s | `/`, `/api/dashboard/summary` |
| R5 | Decision stage 2 — after class (professor, student performance over the course) | Attendance heatmap, course trend vs threshold, occupancy curve, presence bands, per-student indicators, behavioural profiles, risk ranking | `/analytics`, `/api/analytics/course`, `/api/analytics/timeline/{id}` |
| R6 | Decision stage 3 — end of course (coordinator, overall group performance) | Group ranking, per-group evolution, attendance-vs-stability quadrant, ranking table, quarter filter | `/coordinator`, `/api/analytics/coordinator` |
| R7 | At least 2 ML models | Three: InsightFace recognition, K-Means profiles, logistic regression risk | `docs/ML_MODELS.md`, `app/services/ml.py` |
| R8 | Innovative visualizations | Occupancy curve with retention axis; per-student presence bands; student × session heatmap; cluster scatter sized by trend; group quadrant sized by students at risk | `/analytics`, `/coordinator` |
| R9 | Software engineering good practices | Layered architecture, single source of truth for every figure, idempotent migrations, thin routers, documented ML evaluation protocol, demo data generator, versioned changelog | `docs/ARCHITECTURE.md`, `docs/CHANGELOG_v5.md`, `docs/ML_MODELS.md` |
| R10 | Documentation | README, architecture, ML models, traceability, changelog; FastAPI auto-generated API docs | `README.md`, `docs/`, `/docs` |

## Reproducing the evidence

```bash
pip install -r requirements.txt
python -m scripts.seed_demo_data     # synthetic course history
python run.py
```

- `/` → stage 1 (start a class to see it live)
- `/analytics` → stage 2, select a `[DEMO]` scope
- `/coordinator` → stage 3, filter by quarter
- `/docs` → generated API reference

## Requirements deliberately not implemented

| Item | Reason |
|---|---|
| Per-course student enrollment | The existing schema keeps one global student list; splitting it would require re-registering every face. Documented as a limitation in `docs/ARCHITECTURE.md`. |
| Authentication and roles | The brief is about visualization; professor and coordinator views are separate routes, not protected roles. |
| Excel export of the course and coordinator views | The Excel report covers the per-session case, which is the one the professor files. |
