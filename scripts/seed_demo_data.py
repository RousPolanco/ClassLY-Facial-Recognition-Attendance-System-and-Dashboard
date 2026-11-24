"""
ClassLY demo data generator.

The analytics and machine learning views need a course history to
be meaningful. A freshly installed ClassLY has one or two real
sessions, which is not enough to demonstrate the after-class and
end-of-course stages.

This script writes SYNTHETIC sessions and attendance events so the
three decision stages can be demonstrated end to end.

    python -m scripts.seed_demo_data            # create demo data
    python -m scripts.seed_demo_data --clear    # remove it again

Every generated course name is prefixed with DEMO_PREFIX, so the
demo data can always be identified and deleted without touching
real recordings.
"""

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent),
)

from app.database.database import (  # noqa: E402
    get_connection,
    initialize_database,
)


DEMO_PREFIX = "[DEMO] "

SESSION_MINUTES = 90

SESSIONS_PER_COURSE = 12


# Behavioural archetypes. The generator samples students from
# these profiles so K-Means has real structure to find instead of
# uniform noise.
PROFILES = {
    "consistent": {
        "base": 0.94,
        "noise": 0.04,
        "drift": 0.0,
        "exits": (0, 1),
    },
    "irregular": {
        "base": 0.72,
        "noise": 0.22,
        "drift": 0.0,
        "exits": (1, 3),
    },
    "disengaging": {
        "base": 0.90,
        "noise": 0.07,
        "drift": -0.055,
        "exits": (1, 2),
    },
    "absent": {
        "base": 0.18,
        "noise": 0.15,
        "drift": -0.01,
        "exits": (0, 1),
    },
}


# (course, quarter, group, bias, profile_offset)
#
# bias shifts the whole group up or down, and profile_offset
# rotates which archetype each student gets, so the two groups
# are genuinely different and comparable in the coordinator view.
#
# These match the professor's real teaching assignment: Data
# Modeling for Information, 9th quarter, groups A and B (Data
# Engineering). ClassLY's Group field is a single letter (A-Z),
# so "Data Engineering" is the program the letter belongs to, not
# part of the stored value. Keeping course + quarter aligned to
# the real course means the professor opens /analytics and
# /coordinator and sees his own course and quarter in the
# selector, not a placeholder subject he never taught.
COURSES = [
    ("Data Modeling for Information", 9, "A", 0.05, 0),
    ("Data Modeling for Information", 9, "B", -0.12, 2),
]


# ============================================================
# CLEAN UP
# ============================================================

def clear_demo_data() -> int:

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM classes
        WHERE course_name LIKE ?
        """,
        (f"{DEMO_PREFIX}%",),
    )

    class_ids = [
        row["id"]
        for row in cursor.fetchall()
    ]

    for class_id in class_ids:

        cursor.execute(
            "DELETE FROM attendance_events WHERE class_id = ?",
            (class_id,),
        )

        cursor.execute(
            "DELETE FROM intruder_events WHERE class_id = ?",
            (class_id,),
        )

        cursor.execute(
            "DELETE FROM classes WHERE id = ?",
            (class_id,),
        )

    connection.commit()
    connection.close()

    return len(class_ids)


# ============================================================
# STUDENTS
# ============================================================

def get_students() -> list[dict]:

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, student_code, full_name
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


# ============================================================
# GENERATION
# ============================================================

def generate(seed: int = 7) -> dict:

    generator = random.Random(seed)

    students = get_students()

    if not students:
        raise SystemExit(
            "No active students found. Register students before "
            "generating demo data."
        )

    profile_names = list(PROFILES)

    # A stable profile per student, so the same person behaves
    # coherently across every demo course.
    student_profiles = {
        student["id"]: index % len(profile_names)
        for index, student in enumerate(students)
    }

    connection = get_connection()
    cursor = connection.cursor()

    created_classes = 0
    created_events = 0

    for (
        course_name,
        quarter,
        group_name,
        bias,
        profile_offset,
    ) in COURSES:

        first_day = datetime(
            2026,
            2,
            2,
            9,
            0,
            tzinfo=timezone.utc,
        )

        for session_index in range(SESSIONS_PER_COURSE):

            session_start = first_day + timedelta(
                days=7 * session_index
            )

            session_end = session_start + timedelta(
                minutes=SESSION_MINUTES
            )

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
                VALUES (?, ?, ?, ?, '00:00', '00:00', ?, ?)
                """,
                (
                    f"{DEMO_PREFIX}{course_name}",
                    session_start.strftime("%Y-%m-%d"),
                    quarter,
                    group_name,
                    session_start.isoformat(),
                    session_end.isoformat(),
                ),
            )

            class_id = cursor.lastrowid
            created_classes += 1

            for student in students:

                profile_name = profile_names[
                    (
                        student_profiles[student["id"]]
                        + profile_offset
                    )
                    % len(profile_names)
                ]

                profile = PROFILES[profile_name]

                # Target share of the session spent inside.
                share = (
                    profile["base"]
                    + bias
                    + profile["drift"] * session_index
                    + generator.gauss(0, profile["noise"])
                )

                share = max(0.0, min(0.99, share))

                if share < 0.05:
                    # Student never showed up.
                    continue

                inside_minutes = share * SESSION_MINUTES

                # Split the time inside into 1..n visits.
                visits = generator.randint(
                    1,
                    max(1, profile["exits"][1]),
                )

                chunk = inside_minutes / visits

                cursor_minute = generator.uniform(0, 6)

                for _ in range(visits):

                    if cursor_minute >= SESSION_MINUTES:
                        break

                    entry_minute = cursor_minute

                    exit_minute = min(
                        SESSION_MINUTES,
                        entry_minute + chunk,
                    )

                    for event_type, minute in (
                        ("ENTRY", entry_minute),
                        ("EXIT", exit_minute),
                    ):

                        timestamp = (
                            session_start
                            + timedelta(minutes=minute)
                        ).isoformat()

                        cursor.execute(
                            """
                            INSERT INTO attendance_events (
                                student_id,
                                class_id,
                                event_type,
                                timestamp
                            )
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                student["id"],
                                class_id,
                                event_type,
                                timestamp,
                            ),
                        )

                        created_events += 1

                    # Gap before the student comes back.
                    cursor_minute = exit_minute + generator.uniform(
                        2,
                        10,
                    )

            # Occasional unknown face.
            if generator.random() < 0.18:

                cursor.execute(
                    """
                    INSERT INTO intruder_events (
                        class_id,
                        timestamp,
                        snapshot_path
                    )
                    VALUES (?, ?, NULL)
                    """,
                    (
                        class_id,
                        (
                            session_start
                            + timedelta(
                                minutes=generator.uniform(
                                    5,
                                    SESSION_MINUTES - 5,
                                )
                            )
                        ).isoformat(),
                    ),
                )

    connection.commit()
    connection.close()

    return {
        "classes": created_classes,
        "events": created_events,
        "students": len(students),
    }


# ============================================================
# ENTRY POINT
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description="Generate ClassLY demo data."
    )

    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete previously generated demo data and exit.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed (default: 7).",
    )

    arguments = parser.parse_args()

    initialize_database()

    removed = clear_demo_data()

    if arguments.clear:
        print(f"Removed {removed} demo sessions.")
        return

    result = generate(seed=arguments.seed)

    print(
        f"Created {result['classes']} demo sessions and "
        f"{result['events']} attendance events for "
        f"{result['students']} students."
    )


if __name__ == "__main__":
    main()
