# ClassLY — Machine learning models

The project requires at least two ML models. ClassLY uses three.
This document states what each one consumes, how it is trained,
how it is evaluated and where it should not be trusted.

---

## Model 1 — Face recognition and identity matching

| | |
|---|---|
| Algorithm | InsightFace `buffalo_l` (RetinaFace detector + ArcFace embedder) |
| Type | Supervised, pretrained CNN used as a feature extractor |
| Input | Video frame from the classroom camera |
| Output | 512-dimensional embedding per detected face |
| Decision rule | Cosine similarity against registered students; below the threshold the face is an intruder |
| Threshold | `0.65`, configurable in `FaceRecognitionService` |
| Code | `app/services/face_recognition.py`, `app/services/live_attendance.py` |

Enrollment (`scripts/register_students.py`,
`scripts/generate_embeddings.py`) stores one averaged embedding per
student. Recognition is therefore a nearest-neighbour problem in
embedding space, not a classifier that must be retrained when a
student joins the course.

**Known limitations.** Sensitive to illumination and to faces
turned away from the camera. A missed detection produces a false
EXIT, which inflates the number of transitions. The occupancy
curve in stage 2 makes these artefacts visible instead of hiding
them inside a single percentage.

---

## Model 2 — K-Means: behavioural profiles

| | |
|---|---|
| Algorithm | K-Means, k-means++ initialisation, Lloyd's iterations |
| Type | Unsupervised |
| Unit of analysis | One student within one course/quarter/group |
| Default k | 3 (selectable 2–5 in the UI) |
| Code | `app/services/ml.py`, class `KMeans` |

### Features

| Feature | Definition |
|---|---|
| `average_attendance` | Mean % of the session spent inside, across sessions |
| `consistency` | `100 − stdev(percentages)`, floored at 0 |
| `trend` | Least-squares slope, in percentage points per session |
| `average_exits` | Mean number of exits per session |
| `absence_rate` | Fraction of sessions with 0% presence |

All features are z-scored before clustering. Without scaling,
`average_attendance` (0–100) would dominate `average_exits` (0–3)
and the clustering would degenerate into a one-dimensional split.

### Evaluation

The mean **silhouette coefficient** is computed over the same
scaled data and displayed in the UI next to the chart. Values near
1 mean well separated profiles; values near 0 mean the profiles
overlap and should not be over-interpreted. Inertia is also
returned by the API.

Seed is fixed at 42 so the profiles do not reshuffle between page
refreshes — a professor must be able to return to the same view.

### Interpretation

Cluster indices are arbitrary, so labels are derived from the
centroid statistics, not from the index: *Consistently present*,
*Present but irregular*, *Disengaging*, *Partial attendance*,
*Largely absent*. When two centroids yield the same label, the
average attendance is appended so the profiles remain
distinguishable.

---

## Model 3 — Logistic regression: attendance risk

| | |
|---|---|
| Algorithm | Binary logistic regression, batch gradient descent, L2 regularisation |
| Type | Supervised |
| Target | The student stays **below 80%** of the *next* session |
| Hyperparameters | learning rate 0.1, 800 epochs, λ = 0.01 |
| Code | `app/services/ml.py`, class `LogisticRegression` |

### Dataset construction

For every student and every session index *i ≥ 2*:

- **Features** are computed from sessions `[0 … i−1]` only:
  `average_attendance`, `last_attendance`, `trend`,
  `absence_rate`, `average_exits`.
- **Label** is the observed outcome at session *i*:
  `1` if the student was below 80%, `0` otherwise.

Labels come from recorded data. Nothing is hand-labelled and no
rule is baked into the target.

### Train/test split

The split is **chronological**: the most recent session index is
the test set, everything before it is training data. A random
split would let the model see the future of the same student and
would inflate every metric.

### Reported metrics

Accuracy, precision, recall, F1 and the confusion matrix, on the
held-out session, are returned by `/api/analytics/risk` and shown
under the risk table. Training metrics are returned too, so the
gap between them exposes overfitting.

On the reference demo dataset (12 students × 12 sessions):
accuracy ≈ 0.92–1.00, recall ≈ 1.00 on the held-out session.
The dataset is small; these numbers describe the demo, not a
guarantee about a real cohort.

### Degradation instead of pretending

With fewer than 4 sessions, fewer than 8 samples, or a single
class present in the labels, the model is **not** trained. The API
returns `trained: false`, a human readable reason, and the observed
absence rate instead of a prediction. The UI states plainly that
those numbers are not a prediction.

---

## Ethical notes

- The risk model flags **attendance risk**, not academic failure or
  intent. It is an input to a conversation with a student, not a
  verdict.
- Predictions are shown together with the raw history, so a
  professor can always see the evidence behind a flag.
- The models are auditable: the trained weights, the bias and the
  scaler parameters are returned by the API.
- Face embeddings are stored locally in `data/embeddings`, never
  uploaded anywhere.
