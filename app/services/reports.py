"""
ClassLY Excel report generation.

The report is built from get_dashboard_summary(), which is
the same function that feeds the web dashboard. This removes
any possibility of the spreadsheet and the screen showing
different numbers: there is one calculation, consumed twice.
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from app.config import CLASSLY_TIMEZONE_NAME, REPORTS_DIR
from app.database.database import get_connection
from app.services.attendance import format_local_datetime
from app.services.dashboard import get_dashboard_summary


# ============================================================
# STYLES
# ============================================================

HEADER_FILL = PatternFill(
    fill_type="solid",
    fgColor="F15350",
)

HEADER_FONT = Font(
    bold=True,
    color="FFFFFF",
)

TITLE_FONT = Font(
    bold=True,
    size=14,
)

SUBHEADER_FONT = Font(
    bold=True,
)

LABEL_FONT = Font(
    bold=True,
)

MINUTES_FORMAT = "0.00"
PERCENTAGE_FORMAT = "0.0"


# ============================================================
# EVENT QUERIES
# ============================================================

def fetch_attendance_events(class_id: int) -> list[dict]:

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            attendance_events.id,
            attendance_events.student_id,
            attendance_events.event_type,
            attendance_events.timestamp,
            students.student_code,
            students.full_name
        FROM attendance_events
        INNER JOIN students
            ON students.id = attendance_events.student_id
        WHERE attendance_events.class_id = ?
        ORDER BY attendance_events.timestamp ASC
        """,
        (class_id,),
    )

    events = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return events


def fetch_intruder_events(class_id: int) -> list[dict]:

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            timestamp,
            snapshot_path
        FROM intruder_events
        WHERE class_id = ?
        ORDER BY timestamp ASC
        """,
        (class_id,),
    )

    events = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return events


def safe_local_timestamp(timestamp: str) -> str:

    try:
        return format_local_datetime(timestamp)

    except (ValueError, TypeError):
        return timestamp


# ============================================================
# SHEET HELPERS
# ============================================================

def write_label(
    sheet: Worksheet,
    row: int,
    label: str,
    value,
) -> None:

    label_cell = sheet.cell(
        row=row,
        column=1,
        value=label,
    )

    label_cell.font = LABEL_FONT

    sheet.cell(
        row=row,
        column=2,
        value=value,
    )


def write_table_header(
    sheet: Worksheet,
    row: int,
    headers: list[str],
) -> None:

    for column_index, header in enumerate(
        headers,
        start=1,
    ):

        cell = sheet.cell(
            row=row,
            column=column_index,
            value=header,
        )

        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(
            horizontal="center"
        )


def apply_widths(
    sheet: Worksheet,
    widths: dict,
) -> None:

    for column, width in widths.items():
        sheet.column_dimensions[column].width = width


# ============================================================
# REPORT GENERATION
# ============================================================

def generate_attendance_report(
    class_id: int,
) -> str:
    """
    Generate the Excel attendance report for a class.

    Every figure comes from get_dashboard_summary(), so the
    spreadsheet mirrors the dashboard exactly.
    """

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary = get_dashboard_summary(class_id)

    if summary.get("error"):
        raise ValueError("Class not found.")

    class_block = summary["class"]
    students = summary["students"]

    attendance_events = fetch_attendance_events(class_id)
    intruder_events = fetch_intruder_events(class_id)

    # ========================================================
    # WORKBOOK
    # ========================================================

    workbook = Workbook()

    attendance_sheet = workbook.active
    attendance_sheet.title = "Attendance"

    operations_sheet = workbook.create_sheet("Operations")

    # ========================================================
    # ATTENDANCE SHEET - TITLE
    # ========================================================

    attendance_sheet["A1"] = "ClassLY Attendance Report"
    attendance_sheet["A1"].font = TITLE_FONT
    attendance_sheet.merge_cells("A1:H1")

    # --------------------------------------------------------
    # CLASS INFORMATION
    # --------------------------------------------------------

    session_status = class_block["session_status"]

    if class_block["session_start_display"]:
        session_start = class_block["session_start_display"]
    else:
        session_start = "Not started"

    if class_block["session_end_display"]:
        session_end = class_block["session_end_display"]

    elif session_status == "Running":
        session_end = "Session still running"

    else:
        session_end = "Not started"

    write_label(
        attendance_sheet,
        3,
        "Course",
        class_block["course_name"],
    )

    write_label(
        attendance_sheet,
        4,
        "Quarter / Semester",
        class_block["quarter"],
    )

    write_label(
        attendance_sheet,
        5,
        "Group",
        class_block["group_name"],
    )

    write_label(
        attendance_sheet,
        6,
        "Class Date",
        class_block["class_date"],
    )

    write_label(
        attendance_sheet,
        7,
        "Session Status",
        session_status,
    )

    write_label(
        attendance_sheet,
        8,
        "Session Start",
        session_start,
    )

    write_label(
        attendance_sheet,
        9,
        "Session End",
        session_end,
    )

    write_label(
        attendance_sheet,
        10,
        "Session Duration (HH:MM:SS)",
        class_block["session_duration_display"],
    )

    write_label(
        attendance_sheet,
        11,
        "Session Duration (min)",
        class_block["session_duration_minutes"],
    )

    attendance_sheet["B11"].number_format = MINUTES_FORMAT

    write_label(
        attendance_sheet,
        12,
        "Timezone",
        CLASSLY_TIMEZONE_NAME,
    )

    # --------------------------------------------------------
    # GROUP SUMMARY
    # --------------------------------------------------------

    attendance_sheet["A14"] = "Group Summary"
    attendance_sheet["A14"].font = SUBHEADER_FONT

    write_label(
        attendance_sheet,
        15,
        "Students",
        summary["total_students"],
    )

    write_label(
        attendance_sheet,
        16,
        "Present",
        summary["present"],
    )

    write_label(
        attendance_sheet,
        17,
        "Partial",
        summary["partial"],
    )

    write_label(
        attendance_sheet,
        18,
        "Absent",
        summary["absent"],
    )

    write_label(
        attendance_sheet,
        19,
        "Intruders",
        summary["intruders"],
    )

    write_label(
        attendance_sheet,
        20,
        "Total Entries",
        summary["total_entries"],
    )

    write_label(
        attendance_sheet,
        21,
        "Total Exits",
        summary["total_exits"],
    )

    write_label(
        attendance_sheet,
        22,
        "Average Attendance (%)",
        summary["attendance_percentage"],
    )

    attendance_sheet["B22"].number_format = PERCENTAGE_FORMAT

    attendance_sheet["A24"] = "Attendance is calculated using:"
    attendance_sheet["A24"].font = SUBHEADER_FONT

    attendance_sheet["B24"] = (
        "The actual ClassLY session interval "
        "(session start to session end)."
    )

    # --------------------------------------------------------
    # STUDENT TABLE
    # --------------------------------------------------------

    headers = [
        "Student",
        "Code",
        "Entries",
        "Exits",
        "Inside (min)",
        "Outside (min)",
        "Attendance (%)",
        "Status",
    ]

    header_row = 26

    write_table_header(
        attendance_sheet,
        header_row,
        headers,
    )

    current_row = header_row + 1

    for student in students:

        values = [
            student["full_name"],
            student["student_code"],
            student["entries"],
            student["exits"],
            student["total_inside_minutes"],
            student["total_outside_minutes"],
            student["inside_percentage"],
            student["status"],
        ]

        for column_index, value in enumerate(
            values,
            start=1,
        ):

            cell = attendance_sheet.cell(
                row=current_row,
                column=column_index,
                value=value,
            )

            cell.alignment = Alignment(
                vertical="center"
            )

            if column_index in (5, 6):
                cell.number_format = MINUTES_FORMAT

            elif column_index == 7:
                cell.number_format = PERCENTAGE_FORMAT

        current_row += 1

    # ========================================================
    # OPERATIONS SHEET
    # ========================================================

    operations_sheet["A1"] = "ClassLY Operations Log"
    operations_sheet["A1"].font = TITLE_FONT
    operations_sheet.merge_cells("A1:E1")

    write_table_header(
        operations_sheet,
        3,
        [
            "Timestamp",
            "Student Code",
            "Student",
            "Event",
            "Type",
        ],
    )

    operations_row = 4

    for event in attendance_events:

        values = [
            safe_local_timestamp(event["timestamp"]),
            event["student_code"],
            event["full_name"],
            event["event_type"],
            "Attendance",
        ]

        for column_index, value in enumerate(
            values,
            start=1,
        ):

            operations_sheet.cell(
                row=operations_row,
                column=column_index,
                value=value,
            )

        operations_row += 1

    for event in intruder_events:

        values = [
            safe_local_timestamp(event["timestamp"]),
            "",
            "Unknown person",
            "INTRUDER",
            "Security",
        ]

        for column_index, value in enumerate(
            values,
            start=1,
        ):

            operations_sheet.cell(
                row=operations_row,
                column=column_index,
                value=value,
            )

        operations_row += 1

    # ========================================================
    # LAYOUT
    # ========================================================

    apply_widths(
        attendance_sheet,
        {
            "A": 38,
            "B": 30,
            "C": 12,
            "D": 12,
            "E": 16,
            "F": 17,
            "G": 18,
            "H": 16,
        },
    )

    apply_widths(
        operations_sheet,
        {
            "A": 24,
            "B": 18,
            "C": 38,
            "D": 16,
            "E": 16,
        },
    )

    attendance_sheet.freeze_panes = (
        f"A{header_row + 1}"
    )

    operations_sheet.freeze_panes = "A4"

    if students:
        attendance_sheet.auto_filter.ref = (
            f"A{header_row}:H{header_row + len(students)}"
        )

    total_operations = (
        len(attendance_events)
        + len(intruder_events)
    )

    if total_operations > 0:
        operations_sheet.auto_filter.ref = (
            f"A3:E{3 + total_operations}"
        )

    # ========================================================
    # OUTPUT FILE
    # ========================================================

    filename = (
        "classly_attendance_"
        f"{class_block['course_name']}_"
        f"Q{class_block['quarter']}"
        f"{class_block['group_name']}_"
        f"{class_block['class_date']}.xlsx"
    )

    filename = "".join(
        character
        if character.isalnum()
        or character in {"_", "-", "."}
        else "_"
        for character in filename
    )

    file_path = Path(REPORTS_DIR) / filename

    workbook.save(file_path)

    return str(file_path)
