from datetime import datetime, timedelta, timezone

from app.database.database import get_connection


class LiveAttendanceService:
    """
    Manage ENTRY / EXIT transitions for students detected
    by the live camera.

    A student cannot generate repeated events while remaining
    continuously visible.
    """

    def __init__(
        self,
        disappearance_seconds: float = 3.0,
    ):
        self.disappearance_seconds = (
            disappearance_seconds
        )

        # Current state:
        # student_id -> state information
        self.states = {}

    def _get_student_state(
        self,
        student_id: int,
    ) -> dict:

        if student_id not in self.states:

            self.states[student_id] = {
                "inside": False,
                "last_seen": None,
            }

        return self.states[student_id]

    def _record_event(
        self,
        student_id: int,
        class_id: int,
        event_type: str,
    ) -> int:

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

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

    def process_detection(
        self,
        student_id: int,
        class_id: int,
    ) -> str | None:

        state = self._get_student_state(
            student_id
        )

        now = datetime.now(timezone.utc)

        state["last_seen"] = now

        # Student is currently outside.
        # First detection = ENTRY.
        if not state["inside"]:

            self._record_event(
                student_id=student_id,
                class_id=class_id,
                event_type="ENTRY",
            )

            state["inside"] = True

            return "ENTRY"

        # Student is already inside.
        # Do not create another event.
        return None

    def process_missing_students(
        self,
        class_id: int,
    ) -> list[int]:

        now = datetime.now(timezone.utc)

        exited_students = []

        for student_id, state in self.states.items():

            if not state["inside"]:
                continue

            last_seen = state["last_seen"]

            if last_seen is None:
                continue

            elapsed = (
                now - last_seen
            ).total_seconds()

            if (
                elapsed
                >= self.disappearance_seconds
            ):

                self._record_event(
                    student_id=student_id,
                    class_id=class_id,
                    event_type="EXIT",
                )

                state["inside"] = False

                exited_students.append(
                    student_id
                )

        return exited_students

    def reset(self) -> None:

        self.states.clear()