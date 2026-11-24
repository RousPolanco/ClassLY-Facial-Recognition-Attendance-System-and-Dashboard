"""
ClassLY analytics service.

The live dashboard answers "what is happening right now?".
This module answers the other two decision stages required by
the project:

    Stage 2 - After class
              The professor analyses how a group behaves across
              the sessions of a course.

    Stage 3 - End of course
              The coordinator compares groups and courses inside
              a quarter.

Every figure is derived from the same primitives used by the
live dashboard (calculate_attendance_time), so the three stages
can never tell different stories about the same session.
"""

from datetime import timedelta
from statistics import mean, pstdev

from app.database.database import get_connection
from app.services.attendance import (
    calculate_attendance_time,
    to_local_time,
)
from app.services.dashboard import (
    get_active_students,
    get_session_duration_minutes,
    parse_utc_timestamp,
)


# ============================================================
# CONSTANTS
# ============================================================

PRESENT_THRESHOLD = 80.0
PARTIAL_THRESHOLD = 0.0

# Resolution of the occupancy curve, in seconds.
TIMELINE_STEP_SECONDS = 30

# Maximum number of points in an occupancy curve, so a three
# hour session does not return thousands of samples.
TIMELINE_MAX_POINTS = 240


# ============================================================
# SESSION QUERIES
# ============================================================

def get_sessions(
    course_name: str | None = None,
    quarter: int | None = None,
    group_name: str | None = None,
    only_started: bool = True,
) -> list[dict]:
    """
    Return the class sessions matching an academic scope,
    oldest first.
    """

    conditions = []
    parameters: list = []

    if course_name:
        conditions.append("course_name = ?")
        parameters.append(course_name)

    if quarter is not None:
        conditions.append("quarter = ?")
        parameters.append(int(quarter))

    if group_name:
        conditions.append("group_name = ?")
        parameters.append(str(group_name).upper())

    if only_started:
        conditions.append("session_started_at IS NOT NULL")

    where = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        f"""
        SELECT
            id,
            course_name,
            class_date,
            quarter,
            group_name,
            start_time,
            end_time,
            session_started_at,
            session_stopped_at
        FROM classes
        {where}
        ORDER BY
            class_date ASC,
            id ASC
        """,
        parameters,
    )

    sessions = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return sessions


def get_scopes() -> list[dict]:
    """
    Return every course + quarter + group combination that has
    at least one recorded session. Used to populate selectors.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            course_name,
            quarter,
            group_name,
            COUNT(*) AS sessions
        FROM classes
        WHERE session_started_at IS NOT NULL
        GROUP BY
            course_name,
            quarter,
            group_name
        ORDER BY
            quarter ASC,
            course_name ASC,
            group_name ASC
        """
    )

    scopes = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return scopes


def get_session_events(class_id: int) -> list[dict]:
    """
    Return the ENTRY / EXIT events of a session, oldest first.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            attendance_events.student_id,
            attendance_events.event_type,
            attendance_events.timestamp,
            students.full_name,
            students.student_code
        FROM attendance_events
        INNER JOIN students
            ON students.id = attendance_events.student_id
        WHERE attendance_events.class_id = ?
        ORDER BY attendance_events.timestamp ASC
        """,
        (class_id,),
    )

    events = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return events


# ============================================================
# ATTENDANCE MATRIX
# ============================================================

def build_attendance_matrix(
    course_name: str | None = None,
    quarter: int | None = None,
    group_name: str | None = None,
) -> dict:
    """
    Build the student x session attendance matrix that feeds the
    after-class heatmap, the trend lines and the ML features.

    matrix[student_index][session_index] = % of the session the
    student spent inside the classroom.
    """

    sessions = get_sessions(
        course_name=course_name,
        quarter=quarter,
        group_name=group_name,
    )

    students = get_active_students()

    matrix: list[list[float]] = []
    statuses: list[list[str]] = []
    entries_matrix: list[list[int]] = []
    exits_matrix: list[list[int]] = []

    for student in students:

        percentages = []
        student_statuses = []
        student_entries = []
        student_exits = []

        for session in sessions:

            attendance = calculate_attendance_time(
                student_id=student["id"],
                class_id=session["id"],
                class_start=session["start_time"],
                class_end=session["end_time"],
                class_date=session["class_date"],
                class_data=session,
            )

            percentages.append(
                round(
                    attendance.get("inside_percentage", 0),
                    1,
                )
            )

            student_statuses.append(
                attendance.get("attendance_status", "Absent")
            )

            student_entries.append(
                attendance.get("entries", 0)
            )

            student_exits.append(
                attendance.get("exits", 0)
            )

        matrix.append(percentages)
        statuses.append(student_statuses)
        entries_matrix.append(student_entries)
        exits_matrix.append(student_exits)

    return {
        "sessions": [
            {
                "id": session["id"],
                "label": session["class_date"],
                "course_name": session["course_name"],
                "quarter": session["quarter"],
                "group_name": session["group_name"],
                "duration_minutes":
                    get_session_duration_minutes(session),
            }
            for session in sessions
        ],
        "students": [
            {
                "id": student["id"],
                "student_code": student["student_code"],
                "full_name": student["full_name"],
            }
            for student in students
        ],
        "matrix": matrix,
        "statuses": statuses,
        "entries": entries_matrix,
        "exits": exits_matrix,
    }


# ============================================================
# TREND HELPERS
# ============================================================

def linear_trend(values: list[float]) -> float:
    """
    Least squares slope of a series, expressed in percentage
    points gained or lost per session.

    A negative slope means the student is disengaging.
    """

    size = len(values)

    if size < 2:
        return 0.0

    x_mean = (size - 1) / 2
    y_mean = mean(values)

    numerator = sum(
        (index - x_mean) * (value - y_mean)
        for index, value in enumerate(values)
    )

    denominator = sum(
        (index - x_mean) ** 2
        for index in range(size)
    )

    if denominator == 0:
        return 0.0

    return numerator / denominator


def summarize_student(
    percentages: list[float],
    entries: list[int],
    exits: list[int],
) -> dict:
    """
    Condense a student's history into the indicators shown in the
    after-class table and consumed by the ML models.
    """

    if not percentages:
        return {
            "average_attendance": 0.0,
            "consistency": 0.0,
            "trend": 0.0,
            "sessions_attended": 0,
            "sessions_missed": 0,
            "average_exits": 0.0,
            "last_attendance": 0.0,
        }

    attended = sum(
        1
        for value in percentages
        if value >= PRESENT_THRESHOLD
    )

    missed = sum(
        1
        for value in percentages
        if value <= PARTIAL_THRESHOLD
    )

    # Consistency: 100 means the student behaves the same way in
    # every session, regardless of whether that behaviour is good.
    deviation = (
        pstdev(percentages)
        if len(percentages) > 1
        else 0.0
    )

    consistency = max(
        0.0,
        100.0 - deviation,
    )

    return {
        "average_attendance": round(mean(percentages), 1),
        "consistency": round(consistency, 1),
        "trend": round(linear_trend(percentages), 2),
        "sessions_attended": attended,
        "sessions_missed": missed,
        "average_exits": round(mean(exits), 2) if exits else 0.0,
        "last_attendance": percentages[-1],
    }


# ============================================================
# STAGE 2 - AFTER CLASS
# ============================================================

def get_course_analytics(
    course_name: str | None = None,
    quarter: int | None = None,
    group_name: str | None = None,
) -> dict:
    """
    Everything the professor needs to analyse a course after the
    class has ended.
    """

    data = build_attendance_matrix(
        course_name=course_name,
        quarter=quarter,
        group_name=group_name,
    )

    sessions = data["sessions"]
    students = data["students"]
    matrix = data["matrix"]

    # --------------------------------------------------------
    # PER STUDENT SUMMARY
    # --------------------------------------------------------

    student_summaries = []

    for index, student in enumerate(students):

        summary = summarize_student(
            percentages=matrix[index],
            entries=data["entries"][index],
            exits=data["exits"][index],
        )

        student_summaries.append(
            {
                **student,
                **summary,
                "history": matrix[index],
            }
        )

    # --------------------------------------------------------
    # PER SESSION SUMMARY
    # --------------------------------------------------------

    session_summaries = []

    for session_index, session in enumerate(sessions):

        column = [
            matrix[student_index][session_index]
            for student_index in range(len(students))
        ]

        session_summaries.append(
            {
                **session,
                "average_attendance": (
                    round(mean(column), 1)
                    if column
                    else 0.0
                ),
                "present": sum(
                    1
                    for value in column
                    if value >= PRESENT_THRESHOLD
                ),
                "partial": sum(
                    1
                    for value in column
                    if 0 < value < PRESENT_THRESHOLD
                ),
                "absent": sum(
                    1
                    for value in column
                    if value <= 0
                ),
            }
        )

    # --------------------------------------------------------
    # COURSE SUMMARY
    # --------------------------------------------------------

    all_values = [
        value
        for row in matrix
        for value in row
    ]

    course_average = (
        round(mean(all_values), 1)
        if all_values
        else 0.0
    )

    at_risk = [
        student
        for student in student_summaries
        if student["average_attendance"] < PRESENT_THRESHOLD
    ]

    return {
        "scope": {
            "course_name": course_name,
            "quarter": quarter,
            "group_name": group_name,
            "total_sessions": len(sessions),
            "total_students": len(students),
        },
        "course_average_attendance": course_average,
        "students_below_threshold": len(at_risk),
        "sessions": session_summaries,
        "students": student_summaries,
        "heatmap": {
            "x": [
                session["label"]
                for session in sessions
            ],
            "y": [
                student["full_name"]
                for student in students
            ],
            "z": matrix,
        },
    }


# ============================================================
# OCCUPANCY TIMELINE
# ============================================================

def get_session_timeline(class_id: int) -> dict:
    """
    Reconstruct minute by minute how many students were inside
    the classroom, plus the presence bands of each student.

    This is the visualization that makes the boolean attendance
    paradigm obsolete: instead of a single tick, the professor
    sees when the room emptied.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            course_name,
            class_date,
            quarter,
            group_name,
            start_time,
            end_time,
            session_started_at,
            session_stopped_at
        FROM classes
        WHERE id = ?
        """,
        (class_id,),
    )

    row = cursor.fetchone()

    connection.close()

    if not row:
        return {"error": "Class not found."}

    session = dict(row)

    if not session["session_started_at"]:
        return {
            "class_id": class_id,
            "points": [],
            "bands": [],
            "dropoff": [],
            "message": "The session has not been started.",
        }

    start = parse_utc_timestamp(
        session["session_started_at"]
    )

    if session["session_stopped_at"]:
        end = parse_utc_timestamp(
            session["session_stopped_at"]
        )
    else:
        from datetime import datetime, timezone

        from app.config import CLASSLY_TIMEZONE

        end = datetime.now(
            timezone.utc
        ).astimezone(CLASSLY_TIMEZONE)

    total_seconds = max(
        1.0,
        (end - start).total_seconds(),
    )

    events = get_session_events(class_id)

    # --------------------------------------------------------
    # PRESENCE BANDS
    # --------------------------------------------------------
    # For every student, the intervals during which they were
    # inside the classroom.

    open_entry: dict[int, object] = {}
    bands: dict[int, dict] = {}

    for event in events:

        moment = to_local_time(event["timestamp"])

        if moment < start or moment > end:
            continue

        student_id = event["student_id"]

        record = bands.setdefault(
            student_id,
            {
                "student_id": student_id,
                "full_name": event["full_name"],
                "student_code": event["student_code"],
                "intervals": [],
            },
        )

        if event["event_type"] == "ENTRY":

            if student_id not in open_entry:
                open_entry[student_id] = moment

        elif event["event_type"] == "EXIT":

            entry_moment = open_entry.pop(student_id, None)

            if entry_moment is not None:
                record["intervals"].append(
                    (entry_moment, moment)
                )

    # Close the intervals of students still inside.
    for student_id, entry_moment in open_entry.items():

        bands.setdefault(
            student_id,
            {
                "student_id": student_id,
                "full_name": "",
                "student_code": "",
                "intervals": [],
            },
        )["intervals"].append(
            (entry_moment, end)
        )

    # --------------------------------------------------------
    # OCCUPANCY CURVE
    # --------------------------------------------------------

    step = max(
        TIMELINE_STEP_SECONDS,
        int(total_seconds // TIMELINE_MAX_POINTS) + 1,
    )

    points = []

    elapsed = 0.0

    while elapsed <= total_seconds:

        moment = start + timedelta(seconds=elapsed)

        inside = sum(
            1
            for record in bands.values()
            for interval_start, interval_end in record["intervals"]
            if interval_start <= moment <= interval_end
        )

        points.append(
            {
                "minute": round(elapsed / 60, 2),
                "clock": moment.strftime("%H:%M:%S"),
                "inside": inside,
            }
        )

        elapsed += step

    # --------------------------------------------------------
    # DROP-OFF CURVE
    # --------------------------------------------------------
    # Share of the class still inside as the session advances,
    # normalised by the peak occupancy.

    peak = max(
        [point["inside"] for point in points],
        default=0,
    )

    dropoff = [
        {
            "minute": point["minute"],
            "retention": (
                round(point["inside"] / peak * 100, 1)
                if peak
                else 0.0
            ),
        }
        for point in points
    ]

    # --------------------------------------------------------
    # SERIALIZE BANDS
    # --------------------------------------------------------

    serialized_bands = []

    for record in sorted(
        bands.values(),
        key=lambda item: item["full_name"],
    ):

        serialized_bands.append(
            {
                "student_id": record["student_id"],
                "full_name": record["full_name"],
                "student_code": record["student_code"],
                "intervals": [
                    {
                        "start_minute": round(
                            (interval_start - start).total_seconds() / 60,
                            2,
                        ),
                        "end_minute": round(
                            (interval_end - start).total_seconds() / 60,
                            2,
                        ),
                        "start_clock": interval_start.strftime("%H:%M:%S"),
                        "end_clock": interval_end.strftime("%H:%M:%S"),
                    }
                    for interval_start, interval_end in record["intervals"]
                ],
            }
        )

    return {
        "class_id": class_id,
        "course_name": session["course_name"],
        "class_date": session["class_date"],
        "quarter": session["quarter"],
        "group_name": session["group_name"],
        "duration_minutes": round(total_seconds / 60, 2),
        "peak_occupancy": peak,
        "points": points,
        "dropoff": dropoff,
        "bands": serialized_bands,
    }


# ============================================================
# STAGE 3 - END OF COURSE
# ============================================================

def get_coordinator_overview(
    quarter: int | None = None,
) -> dict:
    """
    Cross-group view for the coordinator.

    Each scope (course + quarter + group) is summarised with the
    same indicators, so groups can be ranked and compared.
    """

    scopes = get_scopes()

    if quarter is not None:
        scopes = [
            scope
            for scope in scopes
            if int(scope["quarter"]) == int(quarter)
        ]

    overview = []

    for scope in scopes:

        analytics = get_course_analytics(
            course_name=scope["course_name"],
            quarter=int(scope["quarter"]),
            group_name=scope["group_name"],
        )

        students = analytics["students"]

        averages = [
            student["average_attendance"]
            for student in students
        ]

        consistencies = [
            student["consistency"]
            for student in students
        ]

        trends = [
            student["trend"]
            for student in students
        ]

        overview.append(
            {
                "course_name": scope["course_name"],
                "quarter": int(scope["quarter"]),
                "group_name": scope["group_name"],
                "label": (
                    f"{scope['course_name']} · "
                    f"Q{scope['quarter']} · "
                    f"{scope['group_name']}"
                ),
                "sessions": analytics["scope"]["total_sessions"],
                "students": analytics["scope"]["total_students"],
                "average_attendance":
                    analytics["course_average_attendance"],
                "students_below_threshold":
                    analytics["students_below_threshold"],
                "average_consistency": (
                    round(mean(consistencies), 1)
                    if consistencies
                    else 0.0
                ),
                "average_trend": (
                    round(mean(trends), 2)
                    if trends
                    else 0.0
                ),
                "session_averages": [
                    session["average_attendance"]
                    for session in analytics["sessions"]
                ],
                "session_labels": [
                    session["label"]
                    for session in analytics["sessions"]
                ],
            }
        )

    averages = [
        item["average_attendance"]
        for item in overview
    ]

    return {
        "quarter": quarter,
        "quarters": sorted(
            {
                int(scope["quarter"])
                for scope in get_scopes()
            }
        ),
        "total_groups": len(overview),
        "institution_average": (
            round(mean(averages), 1)
            if averages
            else 0.0
        ),
        "best_group": (
            max(
                overview,
                key=lambda item: item["average_attendance"],
            )["label"]
            if overview
            else None
        ),
        "worst_group": (
            min(
                overview,
                key=lambda item: item["average_attendance"],
            )["label"]
            if overview
            else None
        ),
        "groups": overview,
    }
