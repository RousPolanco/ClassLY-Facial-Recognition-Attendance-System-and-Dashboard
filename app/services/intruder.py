from datetime import datetime, timezone

from app.database.database import get_connection


def record_intruder(
    class_id: int,
    snapshot_path: str | None = None,
) -> int:
    """
    Record an unknown person detected during a class.
    """

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO intruder_events (
            class_id,
            timestamp,
            snapshot_path
        )
        VALUES (?, ?, ?)
        """,
        (
            class_id,
            timestamp,
            snapshot_path,
        ),
    )

    intruder_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return intruder_id