from fastapi import APIRouter
from pydantic import BaseModel

from app.services.attendance import (
    calculate_attendance_time,
    get_student_attendance_events,
    record_attendance_event,
)


router = APIRouter(
    prefix="/api/attendance",
    tags=["Attendance"],
)


class AttendanceEventCreate(BaseModel):
    student_id: int
    class_id: int
    event_type: str


class AttendanceSummaryRequest(BaseModel):
    student_id: int
    class_id: int
    class_start: str
    class_end: str


# ============================================================
# ATTENDANCE EVENTS
# ============================================================

@router.post("/event")
def create_attendance_event(
    event: AttendanceEventCreate,
):
    event_id = record_attendance_event(
        student_id=event.student_id,
        class_id=event.class_id,
        event_type=event.event_type,
    )

    return {
        "message": "Attendance event recorded successfully",
        "event_id": event_id,
    }


@router.get(
    "/{student_id}/{class_id}/events"
)
def get_attendance_events(
    student_id: int,
    class_id: int,
):
    return {
        "events": get_student_attendance_events(
            student_id,
            class_id,
        )
    }


# ============================================================
# ATTENDANCE SUMMARY
# ============================================================

@router.post("/summary")
def get_attendance_summary(
    request: AttendanceSummaryRequest,
):
    return calculate_attendance_time(
        student_id=request.student_id,
        class_id=request.class_id,
        class_start=request.class_start,
        class_end=request.class_end,
    )