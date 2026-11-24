"""
ClassLY analytics API.

Stage 2 (after class)     -> /api/analytics/course
                             /api/analytics/timeline/{class_id}
Stage 3 (end of course)   -> /api/analytics/coordinator

Machine learning          -> /api/analytics/clusters
                             /api/analytics/risk
"""

from fastapi import APIRouter, HTTPException

from app.services.analytics import (
    get_coordinator_overview,
    get_course_analytics,
    get_scopes,
    get_session_timeline,
)
from app.services.ml import (
    get_attendance_clusters,
    get_risk_predictions,
)


router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"],
)


# ============================================================
# SCOPES
# ============================================================

@router.get("/scopes")
def list_scopes():
    """
    Course + quarter + group combinations that have data.
    """

    return {
        "scopes": get_scopes()
    }


# ============================================================
# STAGE 2 - AFTER CLASS
# ============================================================

@router.get("/course")
def course_analytics(
    course_name: str | None = None,
    quarter: int | None = None,
    group_name: str | None = None,
):

    return get_course_analytics(
        course_name=course_name,
        quarter=quarter,
        group_name=group_name,
    )


@router.get("/timeline/{class_id}")
def session_timeline(class_id: int):

    timeline = get_session_timeline(class_id)

    if timeline.get("error"):
        raise HTTPException(
            status_code=404,
            detail=timeline["error"],
        )

    return timeline


# ============================================================
# STAGE 3 - END OF COURSE
# ============================================================

@router.get("/coordinator")
def coordinator_overview(
    quarter: int | None = None,
):

    return get_coordinator_overview(
        quarter=quarter
    )


# ============================================================
# MACHINE LEARNING
# ============================================================

@router.get("/clusters")
def attendance_clusters(
    course_name: str | None = None,
    quarter: int | None = None,
    group_name: str | None = None,
    k: int = 3,
):

    if k < 2 or k > 6:
        raise HTTPException(
            status_code=400,
            detail="k must be between 2 and 6.",
        )

    return get_attendance_clusters(
        course_name=course_name,
        quarter=quarter,
        group_name=group_name,
        clusters=k,
    )


@router.get("/risk")
def risk_predictions(
    course_name: str | None = None,
    quarter: int | None = None,
    group_name: str | None = None,
):

    return get_risk_predictions(
        course_name=course_name,
        quarter=quarter,
        group_name=group_name,
    )
