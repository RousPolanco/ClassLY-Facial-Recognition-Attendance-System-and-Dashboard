from fastapi import APIRouter

from app.database.database import get_connection


router = APIRouter(
    prefix="/api/intruders",
    tags=["Intruders"],
)


@router.get("/{class_id}")
def get_intruders(
    class_id: int,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            class_id,
            timestamp,
            snapshot_path
        FROM intruder_events
        WHERE class_id = ?
        ORDER BY timestamp DESC
        """,
        (class_id,),
    )

    intruders = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return {
        "intruders": intruders,
        "total": len(intruders),
    }