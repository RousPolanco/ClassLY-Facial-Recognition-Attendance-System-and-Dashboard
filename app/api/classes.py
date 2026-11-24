from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.database.repositories import (
    create_class,
    get_class_by_id,
    get_classes,
)


router = APIRouter(
    prefix="/api/classes",
    tags=["Classes"],
)


# ============================================================
# ACADEMIC CONTEXT
# ============================================================
#
# ClassLY identifies a class session by:
#
#     subject + date + quarter + group
#
# quarter    : 0 - 15   (cuatrimestre / semester)
# group_name : A - Z
# ============================================================

MIN_QUARTER = 0
MAX_QUARTER = 15

VALID_GROUPS = {
    chr(code)
    for code in range(ord("A"), ord("Z") + 1)
}


# ============================================================
# REQUEST MODEL
# ============================================================

class ClassCreate(BaseModel):
    course_name: str
    class_date: str

    quarter: int = Field(
        default=0,
        ge=MIN_QUARTER,
        le=MAX_QUARTER,
    )

    group_name: str = "A"


# ============================================================
# VALIDATION HELPERS
# ============================================================

def validate_quarter(quarter: int) -> int:

    if (
        quarter < MIN_QUARTER
        or quarter > MAX_QUARTER
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Quarter/Semester must be a value "
                f"between {MIN_QUARTER} and {MAX_QUARTER}."
            ),
        )

    return int(quarter)


def validate_group(group_name: str) -> str:

    normalized = str(
        group_name or ""
    ).strip().upper()

    if normalized not in VALID_GROUPS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Group must be a single letter "
                "between A and Z."
            ),
        )

    return normalized


# ============================================================
# LIST CLASSES
# ============================================================

@router.get("")
def list_classes():
    return {
        "classes": get_classes()
    }


# ============================================================
# GET CLASS
# ============================================================

@router.get("/{class_id}")
def get_class(class_id: int):

    class_session = get_class_by_id(
        class_id
    )

    if class_session is None:
        raise HTTPException(
            status_code=404,
            detail="Class not found.",
        )

    return class_session


# ============================================================
# CREATE CLASS
# ============================================================

@router.post("")
def add_class(
    class_data: ClassCreate,
):

    course_name = class_data.course_name.strip()
    class_date = class_data.class_date.strip()

    if not course_name:
        raise HTTPException(
            status_code=400,
            detail="Subject is required.",
        )

    if not class_date:
        raise HTTPException(
            status_code=400,
            detail="Class date is required.",
        )

    quarter = validate_quarter(
        class_data.quarter
    )

    group_name = validate_group(
        class_data.group_name
    )

    class_id = create_class(
        course_name=course_name,
        class_date=class_date,
        quarter=quarter,
        group_name=group_name,
    )

    return {
        "message": "Class created successfully.",
        "class_id": class_id,
        "course_name": course_name,
        "class_date": class_date,
        "quarter": quarter,
        "group_name": group_name,
    }
