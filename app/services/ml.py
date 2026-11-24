"""
ClassLY machine learning services.

The project requires at least two ML models. ClassLY uses three,
two of which are implemented in this module:

    Model 1 - Face recognition and identity matching
              InsightFace (buffalo_l): a convolutional network
              produces a 512-dimensional embedding per face and
              identity is resolved by cosine similarity against
              the registered students.
              See app/services/face_recognition.py.

    Model 2 - K-Means clustering (unsupervised)
              Groups students into behavioural profiles from
              their attendance history, so the professor reasons
              about three or four profiles instead of thirty
              individuals.

    Model 3 - Logistic regression (supervised)
              Estimates the probability that a student will fail
              to reach the attendance threshold in the next
              session, using the sessions already recorded.

Models 2 and 3 are implemented from scratch in pure Python.
This is deliberate:

    - ClassLY already ships a heavy CV stack; adding scikit-learn
      for two small models is not justified.
    - The training loop is auditable, which matters for a system
      that flags students as "at risk".
    - The dataset is small (tens of students, tens of sessions),
      so the cost of a hand written optimiser is irrelevant.
"""

import math
import random

from app.services.analytics import (
    PRESENT_THRESHOLD,
    build_attendance_matrix,
    linear_trend,
)


# ============================================================
# NUMERIC HELPERS
# ============================================================

def mean_of(values: list[float]) -> float:

    if not values:
        return 0.0

    return sum(values) / len(values)


def stdev_of(values: list[float]) -> float:

    if len(values) < 2:
        return 0.0

    average = mean_of(values)

    variance = sum(
        (value - average) ** 2
        for value in values
    ) / len(values)

    return math.sqrt(variance)


def standardize(
    rows: list[list[float]],
) -> tuple[list[list[float]], list[float], list[float]]:
    """
    Z-score each column.

    K-Means uses Euclidean distance and logistic regression uses
    gradient descent; both behave badly when one feature ranges
    over 0-100 and another over 0-3.
    """

    if not rows:
        return [], [], []

    columns = len(rows[0])

    means = []
    deviations = []

    for column in range(columns):

        values = [row[column] for row in rows]

        column_mean = mean_of(values)
        column_stdev = stdev_of(values)

        # A constant feature carries no information; keeping the
        # deviation at 1 turns it into a harmless zero column.
        if column_stdev == 0:
            column_stdev = 1.0

        means.append(column_mean)
        deviations.append(column_stdev)

    scaled = [
        [
            (row[column] - means[column]) / deviations[column]
            for column in range(columns)
        ]
        for row in rows
    ]

    return scaled, means, deviations


def apply_scaler(
    row: list[float],
    means: list[float],
    deviations: list[float],
) -> list[float]:

    return [
        (value - means[index]) / deviations[index]
        for index, value in enumerate(row)
    ]


def euclidean(
    first: list[float],
    second: list[float],
) -> float:

    return math.sqrt(
        sum(
            (a - b) ** 2
            for a, b in zip(first, second)
        )
    )


# ============================================================
# MODEL 2 - K-MEANS
# ============================================================

class KMeans:
    """
    K-Means with k-means++ initialisation and Lloyd's algorithm.

    The seed is fixed so the dashboard does not reshuffle the
    profiles on every page refresh.
    """

    def __init__(
        self,
        clusters: int = 3,
        iterations: int = 100,
        tolerance: float = 1e-5,
        seed: int = 42,
    ) -> None:

        self.clusters = clusters
        self.iterations = iterations
        self.tolerance = tolerance
        self.seed = seed

        self.centroids: list[list[float]] = []
        self.labels: list[int] = []
        self.inertia: float = 0.0

    # --------------------------------------------------------

    def initialize_centroids(
        self,
        rows: list[list[float]],
    ) -> list[list[float]]:
        """
        k-means++ : the first centroid is random, and every other
        centroid is chosen with probability proportional to the
        squared distance to the closest existing centroid.
        """

        generator = random.Random(self.seed)

        centroids = [
            list(generator.choice(rows))
        ]

        while len(centroids) < self.clusters:

            distances = [
                min(
                    euclidean(row, centroid) ** 2
                    for centroid in centroids
                )
                for row in rows
            ]

            total = sum(distances)

            if total == 0:
                centroids.append(
                    list(generator.choice(rows))
                )
                continue

            threshold = generator.random() * total
            running = 0.0

            for index, distance in enumerate(distances):

                running += distance

                if running >= threshold:
                    centroids.append(list(rows[index]))
                    break

        return centroids

    # --------------------------------------------------------

    def fit(
        self,
        rows: list[list[float]],
    ) -> "KMeans":

        if not rows:
            return self

        # More clusters than points is meaningless.
        self.clusters = max(
            1,
            min(self.clusters, len(rows)),
        )

        self.centroids = self.initialize_centroids(rows)

        for _ in range(self.iterations):

            # Assignment step.
            labels = [
                min(
                    range(len(self.centroids)),
                    key=lambda index: euclidean(
                        row,
                        self.centroids[index],
                    ),
                )
                for row in rows
            ]

            # Update step.
            new_centroids = []

            for cluster in range(len(self.centroids)):

                members = [
                    row
                    for row, label in zip(rows, labels)
                    if label == cluster
                ]

                if not members:
                    # Keep the orphan centroid where it is rather
                    # than dropping a cluster.
                    new_centroids.append(
                        self.centroids[cluster]
                    )
                    continue

                new_centroids.append(
                    [
                        mean_of(
                            [
                                member[column]
                                for member in members
                            ]
                        )
                        for column in range(len(members[0]))
                    ]
                )

            shift = max(
                euclidean(old, new)
                for old, new in zip(
                    self.centroids,
                    new_centroids,
                )
            )

            self.centroids = new_centroids
            self.labels = labels

            if shift < self.tolerance:
                break

        self.inertia = sum(
            euclidean(row, self.centroids[label]) ** 2
            for row, label in zip(rows, self.labels)
        )

        return self


def silhouette_score(
    rows: list[list[float]],
    labels: list[int],
) -> float:
    """
    Mean silhouette coefficient, in [-1, 1].

    Reported in the UI so the clustering is not presented as an
    unquestionable truth.
    """

    if len(set(labels)) < 2:
        return 0.0

    scores = []

    for index, row in enumerate(rows):

        own_cluster = labels[index]

        same = [
            other
            for other_index, other in enumerate(rows)
            if labels[other_index] == own_cluster
            and other_index != index
        ]

        cohesion = (
            mean_of([euclidean(row, other) for other in same])
            if same
            else 0.0
        )

        separations = []

        for cluster in set(labels):

            if cluster == own_cluster:
                continue

            others = [
                other
                for other_index, other in enumerate(rows)
                if labels[other_index] == cluster
            ]

            if others:
                separations.append(
                    mean_of(
                        [
                            euclidean(row, other)
                            for other in others
                        ]
                    )
                )

        if not separations:
            continue

        separation = min(separations)

        divisor = max(cohesion, separation)

        if divisor == 0:
            continue

        scores.append(
            (separation - cohesion) / divisor
        )

    return round(mean_of(scores), 3)


# ============================================================
# MODEL 3 - LOGISTIC REGRESSION
# ============================================================

class LogisticRegression:
    """
    Binary logistic regression trained with batch gradient
    descent and L2 regularisation.
    """

    def __init__(
        self,
        learning_rate: float = 0.1,
        epochs: int = 800,
        regularization: float = 0.01,
    ) -> None:

        self.learning_rate = learning_rate
        self.epochs = epochs
        self.regularization = regularization

        self.weights: list[float] = []
        self.bias: float = 0.0

    # --------------------------------------------------------

    @staticmethod
    def sigmoid(value: float) -> float:

        # Clamped to avoid math.exp overflowing on large margins.
        if value < -35:
            return 1e-15

        if value > 35:
            return 1 - 1e-15

        return 1 / (1 + math.exp(-value))

    # --------------------------------------------------------

    def fit(
        self,
        rows: list[list[float]],
        targets: list[int],
    ) -> "LogisticRegression":

        if not rows:
            return self

        features = len(rows[0])
        samples = len(rows)

        self.weights = [0.0] * features
        self.bias = 0.0

        for _ in range(self.epochs):

            weight_gradients = [0.0] * features
            bias_gradient = 0.0

            for row, target in zip(rows, targets):

                prediction = self.predict_one(row)
                error = prediction - target

                for index in range(features):
                    weight_gradients[index] += error * row[index]

                bias_gradient += error

            for index in range(features):

                gradient = (
                    weight_gradients[index] / samples
                    + self.regularization * self.weights[index]
                )

                self.weights[index] -= (
                    self.learning_rate * gradient
                )

            self.bias -= (
                self.learning_rate * bias_gradient / samples
            )

        return self

    # --------------------------------------------------------

    def predict_one(self, row: list[float]) -> float:

        if not self.weights:
            return 0.0

        total = self.bias + sum(
            weight * value
            for weight, value in zip(self.weights, row)
        )

        return self.sigmoid(total)


def evaluate_classifier(
    model: LogisticRegression,
    rows: list[list[float]],
    targets: list[int],
    threshold: float = 0.5,
) -> dict:
    """
    Accuracy, precision, recall and F1 on a held out split.
    """

    if not rows:
        return {
            "samples": 0,
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1": None,
        }

    true_positive = 0
    false_positive = 0
    true_negative = 0
    false_negative = 0

    for row, target in zip(rows, targets):

        predicted = 1 if model.predict_one(row) >= threshold else 0

        if predicted == 1 and target == 1:
            true_positive += 1

        elif predicted == 1 and target == 0:
            false_positive += 1

        elif predicted == 0 and target == 0:
            true_negative += 1

        else:
            false_negative += 1

    total = len(rows)

    accuracy = (true_positive + true_negative) / total

    precision = (
        true_positive / (true_positive + false_positive)
        if (true_positive + false_positive)
        else 0.0
    )

    recall = (
        true_positive / (true_positive + false_negative)
        if (true_positive + false_negative)
        else 0.0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    return {
        "samples": total,
        "accuracy": round(accuracy, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "confusion_matrix": {
            "true_positive": true_positive,
            "false_positive": false_positive,
            "true_negative": true_negative,
            "false_negative": false_negative,
        },
    }


# ============================================================
# FEATURE ENGINEERING
# ============================================================

CLUSTER_FEATURE_NAMES = [
    "average_attendance",
    "consistency",
    "trend",
    "average_exits",
    "absence_rate",
]

RISK_FEATURE_NAMES = [
    "average_attendance",
    "last_attendance",
    "trend",
    "absence_rate",
    "average_exits",
]


def build_student_features(
    percentages: list[float],
    exits: list[int],
) -> dict:
    """
    Turn a raw attendance history into the indicators both models
    consume.
    """

    if not percentages:
        return {
            "average_attendance": 0.0,
            "consistency": 0.0,
            "trend": 0.0,
            "average_exits": 0.0,
            "absence_rate": 1.0,
            "last_attendance": 0.0,
        }

    absences = sum(
        1
        for value in percentages
        if value <= 0
    )

    return {
        "average_attendance": mean_of(percentages),
        "consistency": max(
            0.0,
            100.0 - stdev_of(percentages),
        ),
        "trend": linear_trend(percentages),
        "average_exits": mean_of(
            [float(value) for value in exits]
        ),
        "absence_rate": absences / len(percentages),
        "last_attendance": percentages[-1],
    }


# ============================================================
# CLUSTER INTERPRETATION
# ============================================================

def describe_cluster(
    average_attendance: float,
    consistency: float,
    trend: float,
) -> dict:
    """
    Translate a centroid into language a professor can act on.

    The label is derived from the centroid itself, not hard coded
    per cluster index, because cluster numbering is arbitrary.
    """

    if average_attendance >= PRESENT_THRESHOLD and consistency >= 75:
        return {
            "label": "Consistently present",
            "description": (
                "Attends nearly the whole session and behaves the "
                "same way every class. No action needed."
            ),
            "color": "#6FBF9B",
        }

    if average_attendance >= PRESENT_THRESHOLD:
        return {
            "label": "Present but irregular",
            "description": (
                "Good overall attendance with unstable sessions. "
                "Worth checking what happens on the bad days."
            ),
            "color": "#8CC8E8",
        }

    if trend < -3:
        return {
            "label": "Disengaging",
            "description": (
                "Attendance is falling session after session. "
                "This is the group to contact first."
            ),
            "color": "#E8A15B",
        }

    if average_attendance <= 20:
        return {
            "label": "Largely absent",
            "description": (
                "Rarely inside the classroom. Requires escalation "
                "to the coordinator."
            ),
            "color": "#E2766F",
        }

    return {
        "label": "Partial attendance",
        "description": (
            "Enters the classroom but leaves for long stretches "
            "of the session."
        ),
        "color": "#A99BD7",
    }


# ============================================================
# PUBLIC API - CLUSTERING
# ============================================================

def get_attendance_clusters(
    course_name: str | None = None,
    quarter: int | None = None,
    group_name: str | None = None,
    clusters: int = 3,
) -> dict:
    """
    Run K-Means over the attendance history of a scope and return
    the behavioural profiles found.
    """

    data = build_attendance_matrix(
        course_name=course_name,
        quarter=quarter,
        group_name=group_name,
    )

    sessions = data["sessions"]
    students = data["students"]

    if len(sessions) < 2 or len(students) < clusters:
        return {
            "trained": False,
            "reason": (
                "At least 2 recorded sessions and "
                f"{clusters} students are needed to build "
                "behavioural profiles."
            ),
            "sessions": len(sessions),
            "students": len(students),
            "clusters": [],
            "assignments": [],
        }

    feature_rows = []
    feature_dicts = []

    for index, student in enumerate(students):

        features = build_student_features(
            percentages=data["matrix"][index],
            exits=data["exits"][index],
        )

        feature_dicts.append(features)

        feature_rows.append(
            [
                features[name]
                for name in CLUSTER_FEATURE_NAMES
            ]
        )

    scaled, means, deviations = standardize(feature_rows)

    model = KMeans(clusters=clusters).fit(scaled)

    score = silhouette_score(scaled, model.labels)

    # --------------------------------------------------------
    # CLUSTER DESCRIPTIONS
    # --------------------------------------------------------

    cluster_info = []

    for cluster in range(len(model.centroids)):

        members = [
            index
            for index, label in enumerate(model.labels)
            if label == cluster
        ]

        if not members:
            continue

        average_attendance = mean_of(
            [
                feature_dicts[index]["average_attendance"]
                for index in members
            ]
        )

        consistency = mean_of(
            [
                feature_dicts[index]["consistency"]
                for index in members
            ]
        )

        trend = mean_of(
            [
                feature_dicts[index]["trend"]
                for index in members
            ]
        )

        description = describe_cluster(
            average_attendance=average_attendance,
            consistency=consistency,
            trend=trend,
        )

        cluster_info.append(
            {
                "cluster": cluster,
                "size": len(members),
                "average_attendance": round(average_attendance, 1),
                "average_consistency": round(consistency, 1),
                "average_trend": round(trend, 2),
                **description,
            }
        )

    # Two centroids can land on the same qualitative description.
    # Appending the average keeps every profile distinguishable in
    # the legend without inventing a new taxonomy.
    label_counts: dict[str, int] = {}

    for cluster in cluster_info:
        label_counts[cluster["label"]] = (
            label_counts.get(cluster["label"], 0) + 1
        )

    for cluster in cluster_info:

        if label_counts[cluster["label"]] > 1:
            cluster["label"] = (
                f"{cluster['label']} · "
                f"{cluster['average_attendance']:.0f}%"
            )

    # --------------------------------------------------------
    # STUDENT ASSIGNMENTS
    # --------------------------------------------------------

    assignments = []

    for index, student in enumerate(students):

        assignments.append(
            {
                **student,
                "cluster": model.labels[index],
                "average_attendance": round(
                    feature_dicts[index]["average_attendance"],
                    1,
                ),
                "consistency": round(
                    feature_dicts[index]["consistency"],
                    1,
                ),
                "trend": round(
                    feature_dicts[index]["trend"],
                    2,
                ),
                "average_exits": round(
                    feature_dicts[index]["average_exits"],
                    2,
                ),
            }
        )

    return {
        "trained": True,
        "algorithm": "K-Means (k-means++, Lloyd)",
        "features": CLUSTER_FEATURE_NAMES,
        "k": len(cluster_info),
        "silhouette": score,
        "inertia": round(model.inertia, 3),
        "sessions": len(sessions),
        "students": len(students),
        "scaler": {
            "means": [round(value, 3) for value in means],
            "deviations": [
                round(value, 3)
                for value in deviations
            ],
        },
        "clusters": cluster_info,
        "assignments": assignments,
    }


# ============================================================
# PUBLIC API - RISK PREDICTION
# ============================================================

def build_risk_dataset(
    data: dict,
) -> tuple[list[list[float]], list[int], list[int]]:
    """
    Build the supervised dataset.

    For every student and every session index i >= 2, the features
    are computed from sessions [0 .. i-1] and the label is whether
    the student failed to reach the attendance threshold at
    session i.

    Labels therefore come from observed data, never from a rule
    invented for the demo. The session index of each sample is
    returned so the split can be chronological.
    """

    rows = []
    targets = []
    session_indexes = []

    sessions = data["sessions"]

    for student_index in range(len(data["students"])):

        history = data["matrix"][student_index]
        exits = data["exits"][student_index]

        for session_index in range(2, len(sessions)):

            features = build_student_features(
                percentages=history[:session_index],
                exits=exits[:session_index],
            )

            rows.append(
                [
                    features[name]
                    for name in RISK_FEATURE_NAMES
                ]
            )

            targets.append(
                1
                if history[session_index] < PRESENT_THRESHOLD
                else 0
            )

            session_indexes.append(session_index)

    return rows, targets, session_indexes


def risk_level(probability: float) -> str:

    if probability >= 0.7:
        return "High"

    if probability >= 0.4:
        return "Medium"

    return "Low"


def get_risk_predictions(
    course_name: str | None = None,
    quarter: int | None = None,
    group_name: str | None = None,
) -> dict:
    """
    Predict, for every student, the probability of missing the
    attendance threshold in the next session of the course.
    """

    data = build_attendance_matrix(
        course_name=course_name,
        quarter=quarter,
        group_name=group_name,
    )

    sessions = data["sessions"]
    students = data["students"]

    rows, targets, session_indexes = build_risk_dataset(data)

    # --------------------------------------------------------
    # NOT ENOUGH HISTORY
    # --------------------------------------------------------
    # Rather than pretending to predict, ClassLY falls back to the
    # observed average and says so explicitly.

    if (
        len(sessions) < 4
        or len(set(targets)) < 2
        or len(rows) < 8
    ):

        fallback = []

        for index, student in enumerate(students):

            features = build_student_features(
                percentages=data["matrix"][index],
                exits=data["exits"][index],
            )

            probability = max(
                0.0,
                min(
                    1.0,
                    1 - features["average_attendance"] / 100,
                ),
            )

            fallback.append(
                {
                    **student,
                    "probability": round(probability, 3),
                    "risk": risk_level(probability),
                    "average_attendance": round(
                        features["average_attendance"],
                        1,
                    ),
                    "trend": round(features["trend"], 2),
                }
            )

        return {
            "trained": False,
            "reason": (
                "At least 4 recorded sessions with mixed outcomes "
                "are needed to train the risk model. The values "
                "below are the observed absence rate, not a "
                "prediction."
            ),
            "sessions": len(sessions),
            "metrics": None,
            "predictions": sorted(
                fallback,
                key=lambda item: item["probability"],
                reverse=True,
            ),
        }

    # --------------------------------------------------------
    # CHRONOLOGICAL SPLIT
    # --------------------------------------------------------
    # The newest session is the test set. A random split would let
    # the model train on the future, which inflates the metrics.

    last_session = max(session_indexes)

    train_rows = [
        row
        for row, index in zip(rows, session_indexes)
        if index < last_session
    ]

    train_targets = [
        target
        for target, index in zip(targets, session_indexes)
        if index < last_session
    ]

    test_rows = [
        row
        for row, index in zip(rows, session_indexes)
        if index == last_session
    ]

    test_targets = [
        target
        for target, index in zip(targets, session_indexes)
        if index == last_session
    ]

    if not train_rows or len(set(train_targets)) < 2:
        train_rows, train_targets = rows, targets
        test_rows, test_targets = [], []

    scaled_train, means, deviations = standardize(train_rows)

    model = LogisticRegression().fit(
        scaled_train,
        train_targets,
    )

    scaled_test = [
        apply_scaler(row, means, deviations)
        for row in test_rows
    ]

    metrics = evaluate_classifier(
        model=model,
        rows=scaled_test,
        targets=test_targets,
    )

    training_metrics = evaluate_classifier(
        model=model,
        rows=scaled_train,
        targets=train_targets,
    )

    # --------------------------------------------------------
    # PREDICT THE NEXT SESSION
    # --------------------------------------------------------

    predictions = []

    for index, student in enumerate(students):

        features = build_student_features(
            percentages=data["matrix"][index],
            exits=data["exits"][index],
        )

        row = apply_scaler(
            [
                features[name]
                for name in RISK_FEATURE_NAMES
            ],
            means,
            deviations,
        )

        probability = model.predict_one(row)

        predictions.append(
            {
                **student,
                "probability": round(probability, 3),
                "risk": risk_level(probability),
                "average_attendance": round(
                    features["average_attendance"],
                    1,
                ),
                "last_attendance": round(
                    features["last_attendance"],
                    1,
                ),
                "trend": round(features["trend"], 2),
            }
        )

    return {
        "trained": True,
        "algorithm": (
            "Logistic regression "
            "(batch gradient descent, L2)"
        ),
        "features": RISK_FEATURE_NAMES,
        "target": (
            "Student stays below "
            f"{PRESENT_THRESHOLD:.0f}% of the next session"
        ),
        "sessions": len(sessions),
        "training_samples": len(train_rows),
        "weights": {
            name: round(weight, 4)
            for name, weight in zip(
                RISK_FEATURE_NAMES,
                model.weights,
            )
        },
        "bias": round(model.bias, 4),
        "metrics": metrics,
        "training_metrics": training_metrics,
        "predictions": sorted(
            predictions,
            key=lambda item: item["probability"],
            reverse=True,
        ),
    }
