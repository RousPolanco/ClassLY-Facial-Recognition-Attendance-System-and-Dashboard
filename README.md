
![alt text](image-1.png)

**ClassLY** is an Intelligence for classroom attendance at UPY program created by students from Data Engineering 9°A. This program is about a face recognition and tracking replace the boolean attendance tick with a real measurement of how much of a class a student actually spent inside the room and take a control of it to turn that measurement into decisions at three different levels: the professor during class, the professor after class, and the coordinator at the end of the term. This helps the professor to pass assistence easily.

**Team Members:**
* Roselyn Guadalupe Polanco González
* Ingrid Jazmín Cstillo Ek
* Yeimy Getsemaní Pisté Moo
* Joel Alejandro Pérez Yupit

---
## 📂 Project Structure
```bash
ClassLY/
│
├── app/
│   │
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/                                 FastAPI routers — routing & validation only
│   │   ├── attendance.py                    Stage 1
│   │   ├── analytics.py                     Stage 2 and 3 + ML endpoints
│   │   ├── classes.py                       Class sessions (subject, date, quarter, group)
│   │   ├── dashboard.py                     
│   │   ├── intrudenrs.py
│   │   ├── reports.py                       Excel exports
│   │   ├── session.py                       start / stop / reset a session
│   │   └── students.py
│   │
│   ├── services/                            All business logic
│   │   ├── analytics.py                     Cross-session aggregation, occupancy timeline
│   │   ├── attendance.py                    Time inside the classroom, per student
│   │   ├── dashboard.py
│   │   ├── face_recognition.py
│   │   ├── face_registration.py
│   │   ├── intruder.py
│   │   ├── live_attendance.py
│   │   ├── ml.py                            K-Means + logistic regression, from scratch
│   │   └── reports.py
│   │
│   └── database/                            SQLite access, schema, idempotent migrations
│       ├── database.py
│       ├── models.py
│       └── repositories.py
│
├── frontend/                                Dashboard and Fronted design of the page
│   │
│   ├── templates/
│   │   ├── index.html                       Scenario 1
│   │   ├── analytics.html                   Scenario 2
│   │   └── coordinator.html                 Scenario 3
│   │
│   └── static/
│       ├── assets/                          Logo of the page
│       │   └── classly-logo.png 
│       │
│       ├── css/
│       │   └── styles.css                   All the specific design
│       │
│       └── js/
│           ├── dashboard.js                 Scenario 1
│           ├── analytics.js                 Scenario 2
│           ├── coordinator.js               Scenario 3
│           └── vendor/
│               └── plotly.min.js
│
├── scripts/
│   ├── live_camera.py
│   ├── register_students.py
│   ├── generate_embeddings.py
│   └── seed_demo_data.py
│
├── data/
│   ├── classly.db
│   ├── faces/
│   └── embeddings/
│
├── models/
│
├── reports/                                Where the excel report are saved
│
├── docs/                                   Documentation 
│   ├── ARCHITECTURE.md
│   ├── ML_MODELS.md
│   ├── REQUIREMENTS_TRACEABILITY.md
│   └── CHANGELOG_v5.md
│
├── requirements.txt                        Requirements necesaries to execute the program
├── run.py                                  Execute the program
├── .gitignore
└── README.md
```
---

## 📍 Three decision stages

| | Stage | Audience | Route | Answers |
|---|---|---|---|---|
| **1** | During class | Professor | `/` | What's happening in my classroom *right now*? |
| **2** | After class | Professor | `/analytics` | How is this group evolving, and who needs attention? |
| **3** | End of course | Coordinator | `/coordinator` | Which groups performed well this quarter, and where should we intervene? |

---

## 🧠 Machine learning

| Model | Type | Role |
|---|---|---|
| **InsightFace** `buffalo_l` | Pretrained CNN (512-d embeddings) | Recognizes students from the classroom camera |
| **K-Means** (k-means++, from scratch) | Unsupervised | Groups students into behavioural profiles — *consistent*, *disengaging*, *largely absent*… |
| **Logistic Regression** (batch GD + L2, from scratch) | Supervised | Predicts who is likely to miss the 80% threshold in the *next* session |

Full methodology, features, training protocol and evaluation
metrics: **[`docs/ML_MODELS.md`](docs/ML_MODELS.md)**.

---

## 🚀 Quickstart

Download the file ZIP in your computer, then open your prefer terminal and follow the next:
```bash
1. pip install -r requirements.txt
2. python run.py
3. Open the localhost page
```
Open **<http://localhost:8000>**.

---
## ⚠️ Try it without a camera (Data Synthetic for display)

The after-class and end-of-course views need a course history to
be meaningful. A synthetic one, matching a realistic teaching
scenario (Data Modeling for Information · Quarter 9 · Groups A/B),
ships with a one-line generator, just to VSIAUALIZATION AND DISPLAY PRUPOSES to not be empty when professor see how the data could be display when we use it in real scenarios:

```bash
python -m scripts.seed_demo_data          # generate
python -m scripts.seed_demo_data --clear  # remove it again
```

> **This data is clearly marked.** Every generated course is
> prefixed `[DEMO]`, and a yellow banner plus a `DEMO` tag appear
> automatically on `/analytics` and `/coordinator` whenever
> synthetic data is on screen — it can never be mistaken for a
> real recording. Once real sessions accumulate, run `--clear` and
> the same views repopulate from real data with no code changes.

### Registering students and running the camera

```bash
python scripts/register_students.py
python scripts/generate_embeddings.py
python scripts/live_camera.py
```
---

## 🔌 HTTP API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/dashboard/summary?class_id=` | Live figures for one session |
| `GET` | `/api/analytics/scopes` | Course/quarter/group combinations with data |
| `GET` | `/api/analytics/course` | Aggregated history of a scope |
| `GET` | `/api/analytics/timeline/{class_id}` | Minute-by-minute classroom occupancy |
| `GET` | `/api/analytics/clusters` | K-Means behavioural profiles |
| `GET` | `/api/analytics/risk` | Logistic regression risk predictions |
| `GET` | `/api/analytics/coordinator` | Cross-group overview |
| `GET` | `/api/reports/attendance/{class_id}` | Excel report |
| `POST` | `/api/classes` | Create a class session |
| `POST` | `/api/session/start` · `/stop` · `/reset` | Session control |

Interactive docs (Swagger UI) are auto-generated at **`/docs`**.

---

## 📚 Documentation

| Document | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Layers, data model, design decisions, known limitations |
| [`docs/ML_MODELS.md`](docs/ML_MODELS.md) | Features, training, evaluation protocol, ethical notes |
| [`docs/REQUIREMENTS_TRACEABILITY.md`](docs/REQUIREMENTS_TRACEABILITY.md) | Every project requirement → implementation → evidence |
| [`docs/CHANGELOG_v5.md`](docs/CHANGELOG_v5.md) | Version history: data-consistency fixes, academic context, stages 2/3, ML, UI bug fixes |

---

## ⚙️ Requirements

- Python 3.11+
- A webcam for live face recognition (not required to browse `/analytics` or `/coordinator` with demo data)
- See [`requirements.txt`](requirements.txt) for the full dependency list

---

