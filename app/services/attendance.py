from datetime import datetime, timezone

from app.config import CLASSLY_TIMEZONE
from app.database.database import get_connection


# ============================================================
# TIME HELPERS
# ============================================================

def now_utc() -> datetime:
    """
    Return the current UTC datetime.
    """
    return datetime.now(timezone.utc)


def to_local_time(timestamp: str) -> datetime:
    """
    Convert an ISO timestamp to the configured
    ClassLY local timezone.
    """
    value = datetime.fromisoformat(timestamp)

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(CLASSLY_TIMEZONE)


def format_local_datetime(timestamp: str) -> str:
    """
    Convert an ISO timestamp to a human-readable
    local datetime using 24-hour format.
    """
    local_time = to_local_time(timestamp)

    return local_time.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ============================================================
# EMPTY ATTENDANCE RESULT
# ============================================================

def empty_attendance_result(
    student_id: int,
    class_id: int,
) -> dict:
    """
    Return a zeroed attendance result for a session
    that has not started yet.
    """

    return {
        "student_id": student_id,
        "class_id": class_id,
        "class_start": None,
        "class_end": None,
        "total_minutes": 0,
        "minutes_inside": 0,
        "minutes_outside": 0,
        "inside_percentage": 0,
        "attendance_status": "Absent",
        "entries": 0,
        "exits": 0,
    }


# ============================================================
# ATTENDANCE EVENTS
# ============================================================

def record_attendance_event(
    student_id: int,
    class_id: int,
    event_type: str,
) -> int:
    """
    Record an ENTRY or EXIT attendance event.

    Timestamps are stored in UTC.
    """

    event_type = event_type.upper()

    if event_type not in {
        "ENTRY",
        "EXIT",
    }:
        raise ValueError(
            "event_type must be ENTRY or EXIT"
        )

    timestamp = now_utc().isoformat()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO attendance_events (
            student_id,
            class_id,
            event_type,
            timestamp
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            student_id,
            class_id,
            event_type,
            timestamp,
        ),
    )

    event_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return event_id


def get_student_attendance_events(
    student_id: int,
    class_id: int,
) -> list[dict]:
    """
    Return all attendance events for a student
    in a specific class.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            student_id,
            class_id,
            event_type,
            timestamp
        FROM attendance_events
        WHERE student_id = ?
          AND class_id = ?
        ORDER BY timestamp ASC
        """,
        (
            student_id,
            class_id,
        ),
    )

    events = []

    for row in cursor.fetchall():

        event = dict(row)

        # Keep original UTC timestamp.
        event["timestamp_utc"] = event["timestamp"]

        # Add local timestamp for display.
        event["local_timestamp"] = format_local_datetime(
            event["timestamp"]
        )

        events.append(event)

    connection.close()

    return events


# ============================================================
# SESSION INTERVAL
# ============================================================

def get_effective_session_interval(
    class_data: dict,
) -> tuple[datetime, datetime] | None:
    """
    Return the actual ClassLY session interval.

    IMPORTANT:
    The scheduled class time is NOT used.

    Rules:

    1. If the class has not started:
       return None.

    2. If the class is running:
       session_started_at -> current UTC time.

    3. If the class has stopped:
       session_started_at -> session_stopped_at.
    """

    session_started_at = class_data.get(
        "session_started_at"
    )

    session_stopped_at = class_data.get(
        "session_stopped_at"
    )

    # --------------------------------------------------------
    # SESSION HAS NOT STARTED
    # --------------------------------------------------------

    if not session_started_at:
        return None

    # --------------------------------------------------------
    # SESSION START
    # --------------------------------------------------------

    start = to_local_time(
        session_started_at
    )

    # --------------------------------------------------------
    # SESSION END
    # --------------------------------------------------------

    if session_stopped_at:

        end = to_local_time(
            session_stopped_at
        )

    else:

        end = now_utc().astimezone(
            CLASSLY_TIMEZONE
        )

    # Prevent invalid intervals.
    if end < start:
        end = start

    return start, end


# ============================================================
# ATTENDANCE CALCULATION
# ============================================================

def calculate_attendance_time(
    student_id: int,
    class_id: int,
    class_start: str | None = None,
    class_end: str | None = None,
    class_date: str | None = None,
    class_data: dict | None = None,
) -> dict:
    """
    Calculate attendance based exclusively on the
    actual ClassLY session.

    Scheduled class times are intentionally ignored.

    Attendance is calculated between:

        session_started_at
        and
        session_stopped_at

    If the session is still running, the current time
    is used as the temporary session end.
    """

    # --------------------------------------------------------
    # BUILD CLASS DATA
    # --------------------------------------------------------

    if class_data is None:

        class_data = {
            "session_started_at": None,
            "session_stopped_at": None,
        }

    # --------------------------------------------------------
    # GET ACTUAL SESSION INTERVAL
    # --------------------------------------------------------

    session_interval = (
        get_effective_session_interval(
            class_data
        )
    )

    # --------------------------------------------------------
    # SESSION NOT STARTED
    # --------------------------------------------------------

    if session_interval is None:

        return empty_attendance_result(
            student_id=student_id,
            class_id=class_id,
        )

    start, end = session_interval

    # --------------------------------------------------------
    # GET EVENTS
    # --------------------------------------------------------

    events = get_student_attendance_events(
        student_id,
        class_id,
    )

    # --------------------------------------------------------
    # PROCESS EVENTS
    # --------------------------------------------------------

    inside_seconds = 0.0

    current_entry = None

    valid_events = []

    for event in events:

        timestamp = to_local_time(
            event["timestamp_utc"]
        )

        # Ignore events before the real session.
        if timestamp < start:
            continue

        # Ignore events after the real session.
        if timestamp > end:
            continue

        valid_events.append(event)

        # ----------------------------------------------------
        # ENTRY
        # ----------------------------------------------------

        if event["event_type"] == "ENTRY":

            if current_entry is None:

                current_entry = timestamp

        # ----------------------------------------------------
        # EXIT
        # ----------------------------------------------------

        elif event["event_type"] == "EXIT":

            if current_entry is not None:

                interval = (
                    timestamp - current_entry
                ).total_seconds()

                if interval > 0:

                    inside_seconds += interval

                current_entry = None

    # --------------------------------------------------------
    # CLOSE OPEN ENTRY
    # --------------------------------------------------------

    if current_entry is not None:

        interval = (
            end - current_entry
        ).total_seconds()

        if interval > 0:

            inside_seconds += interval

    # --------------------------------------------------------
    # TOTAL SESSION TIME
    # --------------------------------------------------------

    total_seconds = max(
        0,
        (
            end - start
        ).total_seconds(),
    )

    # Never allow inside time to exceed
    # the total session duration.

    inside_seconds = min(
        inside_seconds,
        total_seconds,
    )

    # --------------------------------------------------------
    # OUTSIDE TIME
    # --------------------------------------------------------
    # An absent student was never inside the classroom, but that
    # does NOT mean they spent the whole session "outside".
    # Outside time is meaningful only once the student has an
    # actual attendance event during the session.

    has_attendance = any(
        event["event_type"] in {"ENTRY", "EXIT"}
        for event in valid_events
    )

    # A student with no time inside is absent. They did not
    # participate in the session, so their outside time must be
    # zero rather than the full class duration.
    if inside_seconds <= 0:
        outside_seconds = 0.0
    elif has_attendance:
        outside_seconds = max(
            0,
            total_seconds - inside_seconds,
        )
    else:
        outside_seconds = 0.0

    # --------------------------------------------------------
    # MINUTES
    # --------------------------------------------------------

    total_minutes = (
        total_seconds / 60
    )

    inside_minutes = (
        inside_seconds / 60
    )

    outside_minutes = (
        outside_seconds / 60
    )

    # --------------------------------------------------------
    # ATTENDANCE PERCENTAGE
    # --------------------------------------------------------

    if total_seconds > 0:

        inside_percentage = (
            inside_seconds
            / total_seconds
        ) * 100

    else:

        inside_percentage = 0

    # --------------------------------------------------------
    # ATTENDANCE STATUS
    # --------------------------------------------------------

    if inside_percentage >= 80:

        attendance_status = "Present"

    elif inside_percentage > 0:

        attendance_status = "Partial"

    else:

        attendance_status = "Absent"

    # --------------------------------------------------------
    # EVENT COUNTS
    # --------------------------------------------------------

    entries = sum(
        1
        for event in valid_events
        if event["event_type"] == "ENTRY"
    )

    exits = sum(
        1
        for event in valid_events
        if event["event_type"] == "EXIT"
    )

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {
        "student_id": student_id,
        "class_id": class_id,

        "class_start":
            start.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "class_end":
            end.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "total_minutes":
            round(
                total_minutes,
                2,
            ),

        "minutes_inside":
            round(
                inside_minutes,
                2,
            ),

        "minutes_outside":
            round(
                outside_minutes,
                2,
            ),

        "inside_percentage":
            round(
                inside_percentage,
                2,
            ),

        "attendance_status":
            attendance_status,

        "entries":
            entries,

        "exits":
            exits,
    }