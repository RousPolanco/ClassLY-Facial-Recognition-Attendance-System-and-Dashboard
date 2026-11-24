from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database.repositories import (
    create_student,
    get_student_by_id,
    get_students,
)


router = APIRouter(
    prefix="/api/students",
    tags=["Students"],
)


class StudentCreate(BaseModel):
    student_code: str
    full_name: str


@router.get("")
def list_students():

    return {
        "students": get_students()
    }


@router.get("/{student_id}")
def get_student(student_id: int):

    student = get_student_by_id(student_id)

    if student is None:
        raise HTTPException(
            status_code=404,
            detail="Student not found",
        )

    return student


@router.post("")
def add_student(student: StudentCreate):

    try:

        student_id = create_student(
            student_code=student.student_code,
            full_name=student.full_name,
        )

        return {
            "message": "Student created successfully",
            "student_id": student_id,
        }

    except Exception as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )