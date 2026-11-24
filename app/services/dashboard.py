"""
ClassLY dashboard service.

This module is the SINGLE SOURCE OF TRUTH for every
attendance figure shown by ClassLY.

Both the web dashboard (/api/dashboard/summary) and the
Excel report (/api/reports/attendance/{class_id}) consume
get_dashboard_summary(), so the numbers can never diverge
between the two outputs.
"""

from datetime import datetime, timezone

from app.config import CLASSLY_TIMEZONE
from app.database.database import get_connection
from app.services.attendance import calculate_attendance_time


# ============================================================
# TIME HELPERS
# ============================================================

def parse_utc_timestamp(timestamp: str) -> datetime:
    """
    Parse an ISO timestamp and convert it to the
    configured ClassLY local timezone.
    """

    value = datetime.fromisoformat(timestamp)

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(CLASSLY_TIMEZONE)


def format_timestamp(timestamp: str | None) -> str | None:
    """
    Return a human readable local timestamp.

    The database stores UTC ISO strings such as

        2026-09-17T22:26:29.449913+00:00

    which are not meant to be displayed directly.
    """

    if not timestamp:
        return None

    try:
        return parse_utc_timestamp(
            timestamp
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    except (ValueError, TypeError):
        return timestamp


def format_duration(minutes: float) -> str:
    """
    Format a duration expressed in minutes as HH:MM:SS.
    """

    total_seconds = int(
        round(
            max(0.0, float(minutes)) * 60
        )
    )

    hours = total_seconds // 3600
    remaining = total_seconds % 3600

    return (
        f"{hours:02d}:"
        f"{remaining // 60:02d}:"
        f"{remaining % 60:02d}"
    )


# ============================================================
# CLASS
# ============================================================

def get_class_data(class_id: int) -> dict | None:

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
        return None

    return dict(row)


# ============================================================
# STUDENTS
# ============================================================

def get_active_students() -> list[dict]:

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            student_code,
            full_name
        FROM students
        WHERE active = 1
        ORDER BY full_name
        """
    )

    students = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return students


# ============================================================
# INTRUDERS
# ============================================================

def get_intruder_count(
    class_id: int,
    class_data: dict,
) -> int:

    session_started_at = class_data.get(
        "session_started_at"
    )

    session_stopped_at = class_data.get(
        "session_stopped_at"
    )

    # No actual session means no dashboard intruder data.
    if not session_started_at:
        return 0

    start = parse_utc_timestamp(
        session_started_at
    )

    if session_stopped_at:
        end = parse_utc_timestamp(
            session_stopped_at
        )
    else:
        end = datetime.now(
            timezone.utc
        ).astimezone(
            CLASSLY_TIMEZONE
        )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM intruder_events
        WHERE class_id = ?
          AND timestamp >= ?
          AND timestamp <= ?
        """,
        (
            class_id,
            start.astimezone(
                timezone.utc
            ).isoformat(),
            end.astimezone(
                timezone.utc
            ).isoformat(),
        ),
    )

    count = cursor.fetchone()[0]

    connection.close()

    return int(count)


# ============================================================
# ATTENDANCE EVENT COUNTS
# ============================================================

def get_attendance_event_counts(
    class_id: int,
) -> tuple[int, int]:

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            event_type,
            COUNT(*) AS total
        FROM attendance_events
        WHERE class_id = ?
        GROUP BY event_type
        """,
        (class_id,),
    )

    entries = 0
    exits = 0

    for row in cursor.fetchall():

        event_type = row["event_type"]
        total = int(row["total"])

        if event_type == "ENTRY":
            entries = total

        elif event_type == "EXIT":
            exits = total

    connection.close()

    return entries, exits


# ============================================================
# STUDENT ATTENDANCE
# ============================================================

def get_student_dashboard_data(
    student: dict,
    class_id: int,
    class_data: dict,
) -> dict:
    """
    Build the per-student row used by the dashboard table,
    the charts and the Excel report.

    NOTE:
    calculate_attendance_time() returns the keys

        minutes_inside
        minutes_outside

    and NOT inside_minutes / outside_minutes.
    Reading the wrong key silently produced zeroed times.
    """

    attendance = calculate_attendance_time(
        student_id=student["id"],
        class_id=class_id,
        class_start=class_data["start_time"],
        class_end=class_data["end_time"],
        class_date=class_data["class_date"],
        class_data=class_data,
    )

    return {
        "id": student["id"],
        "student_code": student["student_code"],
        "full_name": student["full_name"],

        # Only events that fall inside the real session
        # are counted, so the table, the charts and the
        # report always agree.
        "entries": attendance.get("entries", 0),
        "exits": attendance.get("exits", 0),

        "total_class_minutes": round(
            attendance.get("total_minutes", 0),
            2,
        ),

        "total_inside_minutes": round(
            attendance.get("minutes_inside", 0),
            2,
        ),

        "total_outside_minutes": round(
            attendance.get("minutes_outside", 0),
            2,
        ),

        "inside_percentage": round(
            attendance.get("inside_percentage", 0),
            1,
        ),

        "status": attendance.get(
            "attendance_status",
            "Absent",
        ),
    }


# ============================================================
# SESSION STATUS
# ============================================================

def get_session_status(
    class_data: dict,
) -> str:

    started = class_data.get(
        "session_started_at"
    )

    stopped = class_data.get(
        "session_stopped_at"
    )

    if not started:
        return "Not started"

    if started and not stopped:
        return "Running"

    return "Completed"


# ============================================================
# SESSION DURATION
# ============================================================

def get_session_duration_minutes(
    class_data: dict,
) -> float:

    started = class_data.get(
        "session_started_at"
    )

    if not started:
        return 0

    start = parse_utc_timestamp(
        started
    )

    stopped = class_data.get(
        "session_stopped_at"
    )

    if stopped:
        end = parse_utc_timestamp(
            stopped
        )
    else:
        end = datetime.now(
            timezone.utc
        ).astimezone(
            CLASSLY_TIMEZONE
        )

    seconds = max(
        0,
        (end - start).total_seconds(),
    )

    return round(
        seconds / 60,
        2,
    )


# ============================================================
# CLASS BLOCK
# ============================================================

def build_class_block(
    class_data: dict,
    session_status: str,
    duration_minutes: float,
) -> dict:
    """
    Build the class descriptor shared by the dashboard
    and the Excel report.

    Raw UTC timestamps are kept for the frontend clock,
    while *_display fields carry the local, readable value.
    """

    return {
        "id": class_data["id"],
        "course_name": class_data["course_name"],
        "class_date": class_data["class_date"],

        "quarter": class_data.get("quarter", 0),
        "group_name": class_data.get("group_name", "A"),

        "session_started_at": class_data.get(
            "session_started_at"
        ),
        "session_stopped_at": class_data.get(
            "session_stopped_at"
        ),

        # Aliases kept for frontend compatibility.
        "session_start": class_data.get(
            "session_started_at"
        ),
        "session_end": class_data.get(
            "session_stopped_at"
        ),

        # Local, human readable values.
        "session_start_display": format_timestamp(
            class_data.get("session_started_at")
        ),
        "session_end_display": format_timestamp(
            class_data.get("session_stopped_at")
        ),

        "session_status": session_status,

        "session_duration_minutes": duration_minutes,
        "session_duration_display": format_duration(
            duration_minutes
        ),
    }


# ============================================================
# DASHBOARD SUMMARY
# ============================================================

def get_dashboard_summary(
    class_id: int,
) -> dict:

    class_data = get_class_data(
        class_id
    )

    if not class_data:
        return {
            "error": "Class not found."
        }

    students = get_active_students()

    session_status = get_session_status(
        class_data
    )

    # --------------------------------------------------------
    # SESSION NOT STARTED
    # --------------------------------------------------------

    if not class_data.get("session_started_at"):

        student_data = [
            {
                "id": student["id"],
                "student_code": student["student_code"],
                "full_name": student["full_name"],
                "entries": 0,
                "exits": 0,
                "total_class_minutes": 0,
                "total_inside_minutes": 0,
                "total_outside_minutes": 0,
                "inside_percentage": 0,
                "status": "Not started",
            }
            for student in students
        ]

        return {
            "class": build_class_block(
                class_data=class_data,
                session_status="Not started",
                duration_minutes=0,
            ),
            "total_students": len(students),
            "present": 0,
            "partial": 0,
            "absent": 0,
            "intruders": 0,
            "total_entries": 0,
            "total_exits": 0,
            "attendance_percentage": 0,
            "students": student_data,
        }

    # --------------------------------------------------------
    # ACTIVE / COMPLETED SESSION
    # --------------------------------------------------------

    student_data = [
        get_student_dashboard_data(
            student=student,
            class_id=class_id,
            class_data=class_data,
        )
        for student in students
    ]

    present = sum(
        1
        for student in student_data
        if student["status"] == "Present"
    )

    partial = sum(
        1
        for student in student_data
        if student["status"] == "Partial"
    )

    absent = sum(
        1
        for student in student_data
        if student["status"] == "Absent"
    )

    total_students = len(student_data)

    if total_students > 0:
        attendance_percentage = (
            sum(
                student["inside_percentage"]
                for student in student_data
            )
            / total_students
        )
    else:
        attendance_percentage = 0

    # Totals are derived from the same per-student rows
    # shown in the table, so the cards can never contradict
    # the table or the report.
    total_entries = sum(
        student["entries"]
        for student in student_data
    )

    total_exits = sum(
        student["exits"]
        for student in student_data
    )

    intruders = get_intruder_count(
        class_id=class_id,
        class_data=class_data,
    )

    duration_minutes = get_session_duration_minutes(
        class_data
    )

    return {
        "class": build_class_block(
            class_data=class_data,
            session_status=session_status,
            duration_minutes=duration_minutes,
        ),
        "total_students": total_students,
        "present": present,
        "partial": partial,
        "absent": absent,
        "intruders": intruders,
        "total_entries": total_entries,
        "total_exits": total_exits,
        "attendance_percentage": round(
            attendance_percentage,
            1,
        ),
        "students": student_data,
    }
