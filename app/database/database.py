import sqlite3

from app.config import DATABASE_PATH, ensure_directories


def get_connection() -> sqlite3.Connection:
    """
    Create and return a connection to the ClassLY SQLite database.
    """
    ensure_directories()

    connection = sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    # Enable foreign key constraints.
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database() -> None:
    """
    Initialize the ClassLY SQLite database.

    The class subject and date identify a class session.
    The actual attendance period is defined exclusively by:

        session_started_at
        session_stopped_at

    The legacy start_time/end_time fields are preserved for
    compatibility with the existing database.
    """

    connection = get_connection()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_code TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            class_date TEXT NOT NULL,

            -- Academic context of the session.
            -- quarter: 0 - 15 (cuatrimestre / semester)
            -- group_name: A - Z
            quarter INTEGER NOT NULL DEFAULT 0,
            group_name TEXT NOT NULL DEFAULT 'A',

            -- Legacy fields kept for database compatibility.
            -- ClassLY no longer uses them to calculate attendance.
            start_time TEXT NOT NULL DEFAULT '00:00',
            end_time TEXT NOT NULL DEFAULT '00:00',

            -- Actual session runtime.
            session_started_at TEXT,
            session_stopped_at TEXT,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attendance_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            event_type TEXT NOT NULL
                CHECK (event_type IN ('ENTRY', 'EXIT')),
            timestamp TEXT NOT NULL,

            FOREIGN KEY (student_id)
                REFERENCES students(id)
                ON DELETE CASCADE,

            FOREIGN KEY (class_id)
                REFERENCES classes(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS intruder_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            snapshot_path TEXT,

            FOREIGN KEY (class_id)
                REFERENCES classes(id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_attendance_student
            ON attendance_events(student_id);

        CREATE INDEX IF NOT EXISTS idx_attendance_class
            ON attendance_events(class_id);

        CREATE INDEX IF NOT EXISTS idx_attendance_timestamp
            ON attendance_events(timestamp);

        CREATE INDEX IF NOT EXISTS idx_intruder_class
            ON intruder_events(class_id);
        """
    )

    # ------------------------------------------------------------
    # DATABASE MIGRATION
    # ------------------------------------------------------------

    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(classes)")

    existing_columns = {
        row["name"]
        for row in cursor.fetchall()
    }

    if "session_started_at" not in existing_columns:
        connection.execute(
            """
            ALTER TABLE classes
            ADD COLUMN session_started_at TEXT
            """
        )

    if "session_stopped_at" not in existing_columns:
        connection.execute(
            """
            ALTER TABLE classes
            ADD COLUMN session_stopped_at TEXT
            """
        )

    if "quarter" not in existing_columns:
        connection.execute(
            """
            ALTER TABLE classes
            ADD COLUMN quarter INTEGER NOT NULL DEFAULT 0
            """
        )

    if "group_name" not in existing_columns:
        connection.execute(
            """
            ALTER TABLE classes
            ADD COLUMN group_name TEXT NOT NULL DEFAULT 'A'
            """
        )

    connection.commit()
    connection.close()