import subprocess
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from app.database.database import get_connection


router = APIRouter(
    prefix="/api/session",
    tags=["Session"],
)


# ============================================================
# GLOBAL CAMERA PROCESS
# ============================================================

camera_process = None


# ============================================================
# REQUEST MODEL
# ============================================================

class SessionRequest(BaseModel):
    class_id: int


# ============================================================
# TIME
# ============================================================

def now_utc_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# START CLASS
# ============================================================

@router.post("/start")
def start_class(
    payload: SessionRequest | None = Body(
        default=None
    ),
    class_id: int | None = Query(
        default=None
    ),
):

    global camera_process

    # --------------------------------------------------------
    # Resolve class ID.
    #
    # Accept both:
    #
    # JSON:
    # {
    #     "class_id": 4
    # }
    #
    # and:
    #
    # /api/session/start?class_id=4
    # --------------------------------------------------------

    resolved_class_id = None

    if payload is not None:
        resolved_class_id = payload.class_id

    elif class_id is not None:
        resolved_class_id = class_id

    if resolved_class_id is None:
        raise HTTPException(
            status_code=400,
            detail="class_id is required.",
        )

    # --------------------------------------------------------
    # Prevent multiple camera sessions.
    # --------------------------------------------------------

    if (
        camera_process is not None
        and camera_process.poll() is None
    ):
        raise HTTPException(
            status_code=409,
            detail="Another class session is already running.",
        )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            course_name,
            class_date,
            session_started_at,
            session_stopped_at
        FROM classes
        WHERE id = ?
        """,
        (resolved_class_id,),
    )

    class_row = cursor.fetchone()

    if not class_row:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Class not found.",
        )

    class_data = dict(
        class_row
    )

    # --------------------------------------------------------
    # Do not restart a completed class.
    # --------------------------------------------------------

    if class_data.get(
        "session_started_at"
    ) and class_data.get(
        "session_stopped_at"
    ):

        connection.close()

        raise HTTPException(
            status_code=409,
            detail=(
                "This class has already been completed. "
                "Use Reset Class Data before starting it again."
            ),
        )

    # --------------------------------------------------------
    # Start timestamp.
    # --------------------------------------------------------

    started_at = (
        class_data.get(
            "session_started_at"
        )
        or now_utc_iso()
    )

    cursor.execute(
        """
        UPDATE classes
        SET
            session_started_at = ?,
            session_stopped_at = NULL
        WHERE id = ?
        """,
        (
            started_at,
            resolved_class_id,
        ),
    )

    connection.commit()
    connection.close()

    # --------------------------------------------------------
    # Launch camera.
    # --------------------------------------------------------

    try:

        camera_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "scripts.live_camera",
                str(resolved_class_id),
            ]
        )

    except Exception as error:

        # Roll back session start if camera cannot launch.
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE classes
            SET session_started_at = NULL
            WHERE id = ?
            """,
            (
                resolved_class_id,
            ),
        )

        connection.commit()
        connection.close()

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not start the camera process: "
                f"{error}"
            ),
        )

    return {
        "status": "running",
        "message": "Class started successfully.",
        "class_id": resolved_class_id,
        "session_started_at": started_at,
    }


# ============================================================
# STOP CLASS
# ============================================================

@router.post("/stop")
def stop_class():

    global camera_process

    if (
        camera_process is None
        or camera_process.poll() is not None
    ):
        raise HTTPException(
            status_code=409,
            detail="No class session is currently running.",
        )

    # --------------------------------------------------------
    # Stop camera.
    # --------------------------------------------------------

    try:

        camera_process.terminate()

        try:
            camera_process.wait(
                timeout=5
            )
        except subprocess.TimeoutExpired:
            camera_process.kill()
            camera_process.wait()

    finally:
        camera_process = None

    # --------------------------------------------------------
    # Find active class.
    # --------------------------------------------------------

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            session_started_at
        FROM classes
        WHERE session_started_at IS NOT NULL
          AND session_stopped_at IS NULL
        ORDER BY session_started_at DESC
        LIMIT 1
        """
    )

    row = cursor.fetchone()

    if not row:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Active class session not found.",
        )

    class_id = row["id"]

    stopped_at = now_utc_iso()

    cursor.execute(
        """
        UPDATE classes
        SET session_stopped_at = ?
        WHERE id = ?
        """,
        (
            stopped_at,
            class_id,
        ),
    )

    connection.commit()
    connection.close()

    return {
        "status": "stopped",
        "message": "Class stopped successfully.",
        "class_id": class_id,
        "session_stopped_at": stopped_at,
    }


# ============================================================
# SESSION STATUS
# ============================================================

@router.get("/status")
def session_status():

    global camera_process

    running = (
        camera_process is not None
        and camera_process.poll() is None
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            course_name,
            class_date,
            session_started_at,
            session_stopped_at
        FROM classes
        WHERE session_started_at IS NOT NULL
          AND session_stopped_at IS NULL
        ORDER BY session_started_at DESC
        LIMIT 1
        """
    )

    row = cursor.fetchone()

    connection.close()

    if not row:
        return {
            "running": False,
            "class_id": None,
            "session_started_at": None,
            "session_stopped_at": None,
        }

    return {
        "running": running,
        "class_id": row["id"],
        "course_name": row[
            "course_name"
        ],
        "class_date": row[
            "class_date"
        ],
        "session_started_at": row[
            "session_started_at"
        ],
        "session_stopped_at": row[
            "session_stopped_at"
        ],
    }


# ============================================================
# RESET CLASS DATA
# ============================================================

@router.post("/reset")
def reset_class(
    payload: SessionRequest | None = Body(
        default=None
    ),
    class_id: int | None = Query(
        default=None
    ),
):

    global camera_process

    # --------------------------------------------------------
    # Resolve class ID.
    # --------------------------------------------------------

    resolved_class_id = None

    if payload is not None:
        resolved_class_id = payload.class_id

    elif class_id is not None:
        resolved_class_id = class_id

    if resolved_class_id is None:
        raise HTTPException(
            status_code=400,
            detail="class_id is required.",
        )

    # --------------------------------------------------------
    # Do not reset while camera is running.
    # --------------------------------------------------------

    if (
        camera_process is not None
        and camera_process.poll() is None
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Stop the class before resetting its data."
            ),
        )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM classes
        WHERE id = ?
        """,
        (
            resolved_class_id,
        ),
    )

    if not cursor.fetchone():
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Class not found.",
        )

    # --------------------------------------------------------
    # Delete attendance events.
    # --------------------------------------------------------

    cursor.execute(
        """
        DELETE FROM attendance_events
        WHERE class_id = ?
        """,
        (
            resolved_class_id,
        ),
    )

    # --------------------------------------------------------
    # Delete intruder events.
    # --------------------------------------------------------

    cursor.execute(
        """
        DELETE FROM intruder_events
        WHERE class_id = ?
        """,
        (
            resolved_class_id,
        ),
    )

    # --------------------------------------------------------
    # Reset session timestamps.
    # --------------------------------------------------------

    cursor.execute(
        """
        UPDATE classes
        SET
            session_started_at = NULL,
            session_stopped_at = NULL
        WHERE id = ?
        """,
        (
            resolved_class_id,
        ),
    )

    connection.commit()
    connection.close()

    return {
        "status": "reset",
        "message": "Class data reset successfully.",
        "class_id": resolved_class_id,
    }