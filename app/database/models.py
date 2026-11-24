from dataclasses import dataclass


@dataclass
class Student:
    id: int | None
    student_code: str
    full_name: str
    active: bool = True


@dataclass
class ClassSession:
    id: int | None
    course_name: str
    class_date: str

    # Kept for compatibility with the existing database.
    start_time: str = "00:00"
    end_time: str = "00:00"

    # Actual session runtime.
    session_started_at: str | None = None
    session_stopped_at: str | None = None


@dataclass
class AttendanceEvent:
    id: int | None
    student_id: int
    class_id: int
    event_type: str
    timestamp: str


@dataclass
class IntruderEvent:
    id: int | None
    class_id: int
    timestamp: str
    snapshot_path: str | None = None