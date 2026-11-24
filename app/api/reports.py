from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.reports import (
    generate_attendance_report,
)


router = APIRouter(
    prefix="/api/reports",
    tags=["Reports"],
)


@router.get(
    "/attendance/{class_id}"
)
def download_attendance_report(
    class_id: int,
):

    try:

        file_path = generate_attendance_report(
            class_id
        )

        # Path().name works on every platform, unlike
        # splitting on a hard coded separator.
        return FileResponse(
            path=file_path,
            filename=Path(file_path).name,
            media_type=(
                "application/"
                "vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
        )

    except ValueError as error:

        raise HTTPException(
            status_code=404,
            detail=str(error),
        )
