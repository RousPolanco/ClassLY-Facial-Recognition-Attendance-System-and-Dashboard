from app.database.database import get_connection


# ============================================================
# STUDENTS
# ============================================================

def create_student(
    student_code: str,
    full_name: str,
) -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO students (
            student_code,
            full_name
        )
        VALUES (?, ?)
        """,
        (
            student_code,
            full_name,
        ),
    )

    student_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return student_id


def get_student_by_code(
    student_code: str,
) -> dict | None:

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            student_code,
            full_name,
            active,
            created_at
        FROM students
        WHERE student_code = ?
        """,
        (student_code,),
    )

    row = cursor.fetchone()

    connection.close()

    return dict(row) if row else None


def get_or_create_student(
    student_code: str,
    full_name: str,
) -> dict:

    existing_student = get_student_by_code(
        student_code
    )

    if existing_student:
        return existing_student

    student_id = create_student(
        student_code=student_code,
        full_name=full_name,
    )

    return get_student_by_id(student_id)


def get_students() -> list[dict]:

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            student_code,
            full_name,
            active,
            created_at
        FROM students
        WHERE active = 1
        ORDER BY full_name
        """
    )

    students = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return students


def get_student_by_id(
    student_id: int,
) -> dict | None:

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            student_code,
            full_name,
            active,
            created_at
        FROM students
        WHERE id = ?
        """,
        (student_id,),
    )

    row = cursor.fetchone()

    connection.close()

    return dict(row) if row else None


# ============================================================
# CLASSES
# ============================================================

def create_class(
    course_name: str,
    class_date: str,
    quarter: int = 0,
    group_name: str = "A",
) -> int:

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO classes (
            course_name,
            class_date,
            quarter,
            group_name,
            start_time,
            end_time,
            session_started_at,
            session_stopped_at
        )
        VALUES (?, ?, ?, ?, '00:00', '00:00', NULL, NULL)
        """,
        (
            course_name,
            class_date,
            int(quarter),
            str(group_name).upper(),
        ),
    )

    class_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return class_id


def get_classes() -> list[dict]:

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            course_name,
            class_date,
            quarter,
            group_name,
            start_time,
            end_time,
            session_started_at,
            session_stopped_at,
            created_at
        FROM classes
        ORDER BY
            class_date DESC,
            id DESC
        """
    )

    classes = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return classes


def get_class_by_id(
    class_id: int,
) -> dict | None:

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            course_name,
            class_date,
            quarter,
            group_name,
            start_time,
            end_time,
            session_started_at,
            session_stopped_at,
            created_at
        FROM classes
        WHERE id = ?
        """,
        (class_id,),
    )

    row = cursor.fetchone()

    connection.close()

    return dict(row) if row else None


# ============================================================
# CLASS SESSION
# ============================================================

def start_class_session(
    class_id: int,
    started_at: str,
) -> dict | None:

    connection = get_connection()
    cursor = connection.cursor()

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
            class_id,
        ),
    )

    connection.commit()

    cursor.execute(
        """
        SELECT
            id,
            course_name,
            class_date,
            quarter,
            group_name,
            start_time,
            end_time,
            session_started_at,
            session_stopped_at,
            created_at
        FROM classes
        WHERE id = ?
        """,
        (class_id,),
    )

    row = cursor.fetchone()

    connection.close()

    return dict(row) if row else None


def stop_class_session(
    class_id: int,
    stopped_at: str,
) -> dict | None:

    connection = get_connection()
    cursor = connection.cursor()

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

    cursor.execute(
        """
        SELECT
            id,
            course_name,
            class_date,
            quarter,
            group_name,
            start_time,
            end_time,
            session_started_at,
            session_stopped_at,
            created_at
        FROM classes
        WHERE id = ?
        """,
        (class_id,),
    )

    row = cursor.fetchone()

    connection.close()

    return dict(row) if row else None


def get_class_session(
    class_id: int,
) -> dict | None:

    return get_class_by_id(class_id)


# ============================================================
# RESET CLASS DATA
# ============================================================

def reset_class_data(
    class_id: int,
) -> dict | None:

    connection = get_connection()
    cursor = connection.cursor()

    # Delete attendance events.
    cursor.execute(
        """
        DELETE FROM attendance_events
        WHERE class_id = ?
        """,
        (class_id,),
    )

    # Delete intruder events.
    cursor.execute(
        """
        DELETE FROM intruder_events
        WHERE class_id = ?
        """,
        (class_id,),
    )

    # Reset actual session timestamps.
    cursor.execute(
        """
        UPDATE classes
        SET
            session_started_at = NULL,
            session_stopped_at = NULL
        WHERE id = ?
        """,
        (class_id,),
    )

    connection.commit()

    cursor.execute(
        """
        SELECT
            id,
            course_name,
            class_date,
            quarter,
            group_name,
            start_time,
            end_time,
            session_started_at,
            session_stopped_at,
            created_at
        FROM classes
        WHERE id = ?
        """,
        (class_id,),
    )

    row = cursor.fetchone()

    connection.close()

    return dict(row) if row else None