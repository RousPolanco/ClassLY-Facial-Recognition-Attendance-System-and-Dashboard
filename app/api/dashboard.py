"""
ClassLY dashboard API.

This router is intentionally thin.

All attendance logic lives in app/services/dashboard.py so
the dashboard and the Excel report share exactly the same
numbers. The helpers are re-exported to keep backwards
compatibility with modules that imported them from here.
"""

from fastapi import APIRouter

from app.services.dashboard import (  # noqa: F401
    build_class_block,
    format_duration,
    format_timestamp,
    get_active_students,
    get_attendance_event_counts,
    get_class_data,
    get_dashboard_summary,
    get_intruder_count,
    get_session_duration_minutes,
    get_session_status,
    get_student_dashboard_data,
    parse_utc_timestamp,
)


# ============================================================
# API ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


# ============================================================
# DASHBOARD API ENDPOINT
# ============================================================

@router.get("/summary")
async def dashboard_summary(class_id: int):
    return get_dashboard_summary(class_id)
