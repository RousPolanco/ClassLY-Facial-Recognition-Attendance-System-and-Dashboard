import cv2
import time
import sys

from datetime import datetime

from app.config import DATA_DIR
from app.database.database import (
    initialize_database,
    get_connection,
)
from app.services.face_recognition import (
    FaceRecognitionService,
)
from app.services.live_attendance import (
    LiveAttendanceService,
)
from app.services.intruder import (
    record_intruder,
)


# Class ID is provided by the session that starts
# the live attendance process.
if len(sys.argv) < 2:
    print("ERROR: No class ID was provided.")
    sys.exit(1)

CLASS_ID = int(sys.argv[1])

RECOGNITION_THRESHOLD = 0.65

DISAPPEARANCE_SECONDS = 3.0

SNAPSHOT_DIR = DATA_DIR / "intruders"


def get_student_id(
    student_code: str,
) -> int | None:
    """
    Get the database ID of a student
    using their student code.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM students
        WHERE student_code = ?
        """,
        (student_code,),
    )

    row = cursor.fetchone()

    connection.close()

    if row:
        return row["id"]

    return None


def save_intruder_snapshot(
    frame,
) -> str:
    """
    Save a snapshot of an unknown person.
    """

    SNAPSHOT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    filename = (
        f"intruder_{timestamp}.jpg"
    )

    path = SNAPSHOT_DIR / filename

    cv2.imwrite(
        str(path),
        frame,
    )

    return str(path)


def main():

    # Make sure the database exists.
    initialize_database()

    # Initialize facial recognition.
    face_service = FaceRecognitionService(
        threshold=RECOGNITION_THRESHOLD
    )

    # Initialize live attendance state.
    attendance_service = LiveAttendanceService(
        disappearance_seconds=
        DISAPPEARANCE_SECONDS
    )

    # Open the default camera.
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():

        print(
            "ERROR: Could not open camera."
        )

        return

    print()
    print(
        "======================================"
    )
    print(
        "       ClassLY Live Attendance"
    )
    print(
        "======================================"
    )
    print(
        f"Registered students: "
        f"{face_service.get_registered_student_count()}"
    )
    print(
        "Camera started."
    )
    print(
        "Press Q to stop the class."
    )
    print()

    # Prevent recording the same unknown person
    # on every camera frame.
    last_intruder_time = 0.0

    try:

        while True:

            success, frame = camera.read()

            if not success:

                print(
                    "ERROR: Could not read "
                    "camera frame."
                )

                break

            # Recognize every face detected
            # in the current frame.
            results = (
                face_service.recognize_image(
                    frame
                )
            )

            for result in results:

                x1, y1, x2, y2 = map(
                    int,
                    result["bbox"],
                )

                # ==================================
                # KNOWN STUDENT
                # ==================================

                if result["is_known"]:

                    student_code = (
                        result["student_code"]
                    )

                    student_id = (
                        get_student_id(
                            student_code
                        )
                    )

                    if student_id is None:

                        continue

                    # Process the detection
                    # through the ENTRY / EXIT
                    # state machine.
                    event = (
                        attendance_service
                        .process_detection(
                            student_id=student_id,
                            class_id=CLASS_ID,
                        )
                    )

                    similarity = (
                        result["similarity"]
                    )

                    label = (
                        f"{student_code} "
                        f"{similarity:.2f}"
                    )

                    if event:

                        print(
                            f"[{event}] "
                            f"{student_code} "
                            f"similarity="
                            f"{similarity:.4f}"
                        )

                    # Draw known-person bounding box.
                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (96, 122, 116),
                        2,
                    )

                    cv2.putText(
                        frame,
                        label,
                        (
                            x1,
                            max(y1 - 10, 20),
                        ),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (96, 122, 116),
                        2,
                    )

                # ==================================
                # UNKNOWN PERSON
                # ==================================

                else:

                    current_time = time.time()

                    # Record at most one intruder
                    # event per second.
                    if (
                        current_time
                        - last_intruder_time
                        >= 1.0
                    ):

                        snapshot_path = (
                            save_intruder_snapshot(
                                frame
                            )
                        )

                        record_intruder(
                            class_id=CLASS_ID,
                            snapshot_path=
                            snapshot_path,
                        )

                        last_intruder_time = (
                            current_time
                        )

                        print(
                            "[INTRUDER] "
                            "Unknown person detected."
                        )

                    # Draw unknown-person box.
                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (123, 123, 255),
                        2,
                    )

                    cv2.putText(
                        frame,
                        "UNKNOWN PERSON",
                        (
                            x1,
                            max(y1 - 10, 20),
                        ),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (123, 123, 255),
                        2,
                    )

            # ======================================
            # CHECK FOR STUDENTS WHO DISAPPEARED
            # ======================================

            exited_students = (
                attendance_service
                .process_missing_students(
                    class_id=CLASS_ID
                )
            )

            for student_id in exited_students:

                print(
                    f"[EXIT] Student ID "
                    f"{student_id}"
                )

            # Show live camera.
            cv2.imshow(
                "ClassLY - Live Attendance",
                frame,
            )

            # Q = stop class.
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):

                break

    finally:

        # Always release camera resources,
        # even if an unexpected error occurs.
        camera.release()

        cv2.destroyAllWindows()

        print()
        print(
            "ClassLY attendance camera stopped."
        )
        print()


if __name__ == "__main__":
    main()