// ============================================================
// CLASSLY DASHBOARD
// ============================================================

let currentClassId = null;
let availableClasses = [];
let sessionRunning = false;
let sessionStartTimestamp = null;
let sessionStopTimestamp = null;

let dashboardInterval = null;
let clockInterval = null;


// ============================================================
// COLORS
// ============================================================

const CHART_COLORS = {
    blue: "#8CC8E8",
    purple: "#A99BD7",
    blueDeep: "#5D91C2",
    purpleDeep: "#7765AE",
    text: "#30364D",
    muted: "#72788F",
    background: "#F0EFF5"
};


// ============================================================
// DOM HELPER
// ============================================================

function getElement(...ids) {

    for (const id of ids) {

        const element =
            document.getElementById(id);

        if (element) {
            return element;
        }
    }

    return null;
}


// ============================================================
// ACADEMIC CONTEXT
// ============================================================
//
// A ClassLY session is identified by:
//
//     subject + date + quarter + group
//
// quarter : 0 - 15   (cuatrimestre / semester)
// group   : A - Z
// ============================================================

const MIN_QUARTER = 0;
const MAX_QUARTER = 15;


function getQuarterInput() {

    return getElement(
        "class-quarter",
        "quarter-input"
    );
}


function getGroupInput() {

    return getElement(
        "class-group",
        "group-input"
    );
}


function populateAcademicSelectors() {

    const quarterInput =
        getQuarterInput();


    if (
        quarterInput &&
        quarterInput.options.length === 0
    ) {

        for (
            let quarter = MIN_QUARTER;
            quarter <= MAX_QUARTER;
            quarter += 1
        ) {

            const option =
                document.createElement("option");

            option.value = String(quarter);
            option.textContent = String(quarter);

            quarterInput.appendChild(option);
        }

        quarterInput.value = "0";
    }


    const groupInput =
        getGroupInput();


    if (
        groupInput &&
        groupInput.options.length === 0
    ) {

        for (
            let code = "A".charCodeAt(0);
            code <= "Z".charCodeAt(0);
            code += 1
        ) {

            const letter =
                String.fromCharCode(code);

            const option =
                document.createElement("option");

            option.value = letter;
            option.textContent = letter;

            groupInput.appendChild(option);
        }

        groupInput.value = "A";
    }
}


function getSelectedQuarter() {

    const quarterInput =
        getQuarterInput();


    if (!quarterInput) {
        return 0;
    }


    const quarter =
        Number(quarterInput.value);


    if (!Number.isFinite(quarter)) {
        return 0;
    }


    return Math.min(
        Math.max(
            Math.trunc(quarter),
            MIN_QUARTER
        ),
        MAX_QUARTER
    );
}


function getSelectedGroup() {

    const groupInput =
        getGroupInput();


    if (!groupInput) {
        return "A";
    }


    const group =
        String(groupInput.value || "")
            .trim()
            .toUpperCase();


    return group || "A";
}


function classQuarter(classItem) {

    const quarter =
        Number(classItem.quarter);


    return Number.isFinite(quarter)
        ? Math.trunc(quarter)
        : 0;
}


function classGroup(classItem) {

    return String(
        classItem.group_name || "A"
    )
    .trim()
    .toUpperCase();
}


// ============================================================
// NUMBER HELPER
// ============================================================

function numberValue(value) {

    const number =
        Number(value);

    if (!Number.isFinite(number)) {
        return 0;
    }

    return number;
}


// ============================================================
// HTML ESCAPE
// ============================================================

function escapeHtml(value) {

    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


// ============================================================
// SHORT STUDENT NAME
//
// Examples:
//
// ROSELYN GUADALUPE POLANCO GONZALEZ
// -> ROSELYN POLANCO
//
// DALILA DE LOS ANGELES KU DZUL
// -> DALILA KU
//
// SARALET CHAN RAMOS
// -> SARALET CHAN
//
// FABIO MARTIN ENRIQUEZ
// -> FABIO ENRIQUEZ
//
// IVAN ESAU PALOMO GARCIA
// -> IVAN PALOMO
// ============================================================

function getShortStudentName(fullName) {

    if (!fullName) {
        return "Unknown";
    }

    const parts =
        String(fullName)
            .trim()
            .split(/\s+/)
            .filter(Boolean);

    if (parts.length === 0) {
        return "Unknown";
    }

    if (parts.length === 1) {
        return parts[0];
    }

    /*
     * Three-part names:
     *
     * First + middle + surname
     *
     * Example:
     * FABIO MARTIN ENRIQUEZ
     * -> FABIO ENRIQUEZ
     */
    if (parts.length === 3) {

        return `${parts[0]} ${parts[2]}`;
    }


    /*
     * Four or more parts:
     *
     * First name is parts[0].
     *
     * In the ClassLY roster, the first surname
     * is the second-to-last token.
     *
     * This correctly handles compound given names:
     *
     * DALILA DE LOS ANGELES KU DZUL
     * -> DALILA KU
     *
     * ROSELYN GUADALUPE POLANCO GONZALEZ
     * -> ROSELYN POLANCO
     */

    return `${parts[0]} ${parts[parts.length - 2]}`;
}


// ============================================================
// FORMAT DURATION
// ============================================================

function formatDurationFromSeconds(
    totalSeconds
) {

    const seconds =
        Math.max(
            0,
            Math.floor(
                numberValue(totalSeconds)
            )
        );


    const hours =
        Math.floor(
            seconds / 3600
        );


    const minutes =
        Math.floor(
            (seconds % 3600) / 60
        );


    const remainingSeconds =
        seconds % 60;


    return [
        String(hours).padStart(2, "0"),
        String(minutes).padStart(2, "0"),
        String(remainingSeconds).padStart(2, "0")
    ].join(":");
}


// ============================================================
// FORMAT MINUTES
// ============================================================

function formatMinutes(value) {

    const minutes =
        numberValue(value);

    return `${minutes.toFixed(1)} min`;
}


// ============================================================
// SESSION CLOCK
//
// This clock is independent from the dashboard's
// 5-second refresh.
//
// It updates every second.
// ============================================================

function calculateSessionSeconds() {

    if (!sessionStartTimestamp) {
        return 0;
    }


    const start =
        Number(sessionStartTimestamp);


    let end;


    if (sessionStopTimestamp) {

        end =
            Number(sessionStopTimestamp);

    } else {

        end =
            Date.now();
    }


    const seconds =
        Math.max(
            0,
            (end - start) / 1000
        );


    return seconds;
}


// ============================================================
// UPDATE CLOCK DISPLAY
// ============================================================

function updateClockDisplay() {

    const seconds =
        calculateSessionSeconds();

    const formatted =
        formatDurationFromSeconds(
            seconds
        );


    /*
     * Update the main live duration display.
     */

    const durationElements = [
        "session-duration",
        "class-duration",
        "duration",
        "session-timer",
        "class-timer"
    ];


    durationElements.forEach(
        id => {

            const element =
                document.getElementById(id);

            if (element) {

                element.textContent =
                    formatted;
            }
        }
    );


    /*
     * Update any element explicitly marked
     * as a session-duration element.
     */

    document
        .querySelectorAll(
            "[data-session-duration]"
        )
        .forEach(
            element => {

                element.textContent =
                    formatted;
            }
        );


    /*
     * IMPORTANT:
     *
     * Find the dashboard card whose label is
     * "Class Duration".
     *
     * This makes the card work even if its
     * internal ID is different from the live
     * duration element.
     */

    const statCards =
        document.querySelectorAll(
            ".stat-card"
        );


    statCards.forEach(
        card => {

            const small =
                card.querySelector(
                    "small"
                );


            if (!small) {
                return;
            }


            const label =
                small.textContent
                    .trim()
                    .toLowerCase();


            if (
                label ===
                "class duration"
            ) {

                const value =
                    card.querySelector(
                        "strong"
                    );


                if (value) {

                    value.textContent =
                        formatted;
                }
            }
        }
    );
}


// ============================================================
// START LIVE CLOCK
// ============================================================

function startLiveClock() {

    if (clockInterval) {

        clearInterval(
            clockInterval
        );
    }


    updateClockDisplay();


    clockInterval =
        setInterval(
            updateClockDisplay,
            1000
        );
}


// ============================================================
// STOP LIVE CLOCK
// ============================================================

function stopLiveClock() {

    if (clockInterval) {

        clearInterval(
            clockInterval
        );

        clockInterval = null;
    }


    updateClockDisplay();
}


// ============================================================
// LOAD CLASSES
// ============================================================

async function loadClasses() {

    const dateInput =
        getElement("class-date");


    const subjectInput =
        getElement(
            "subject-input",
            "class-subject",
            "subject"
        );


    const classInfo =
        getElement(
            "selected-class-info"
        );


    try {

        const response =
            await fetch(
                `/api/classes?_=${Date.now()}`,
                {
                    cache: "no-store"
                }
            );


        if (!response.ok) {

            throw new Error(
                "Could not load classes."
            );
        }


        const data =
            await response.json();


        if (Array.isArray(data)) {

            availableClasses =
                data;

        } else {

            availableClasses =
                data.classes || [];
        }


        /*
         * Default date = today.
         */

        if (
            dateInput &&
            !dateInput.value
        ) {

            dateInput.value =
                new Date()
                    .toISOString()
                    .split("T")[0];
        }


        /*
         * If subject and date are already
         * selected, restore that class.
         */

        if (
            subjectInput &&
            subjectInput.value &&
            dateInput &&
            dateInput.value
        ) {

            updateSelectedClass();

            return;
        }


        /*
         * Otherwise, try to find today's class.
         */

        if (
            dateInput &&
            availableClasses.length > 0
        ) {

            const today =
                new Date()
                    .toISOString()
                    .split("T")[0];


            const todayClass =
                availableClasses.find(
                    classItem =>
                        classItem.class_date ===
                        today
                );


            if (todayClass) {

                dateInput.value =
                    todayClass.class_date;


                if (subjectInput) {

                    subjectInput.value =
                        todayClass.course_name || "";
                }


                const quarterInput =
                    getQuarterInput();


                if (quarterInput) {

                    quarterInput.value =
                        String(
                            classQuarter(todayClass)
                        );
                }


                const groupInput =
                    getGroupInput();


                if (groupInput) {

                    groupInput.value =
                        classGroup(todayClass);
                }


                currentClassId =
                    Number(
                        todayClass.id
                    );


                updateSelectedClass();

                return;
            }
        }


        currentClassId = null;


        if (classInfo) {

            classInfo.innerHTML =
                "Select a subject and date.";
        }


    } catch (error) {

        console.error(
            "Class loading error:",
            error
        );


        availableClasses = [];

        currentClassId = null;


        if (classInfo) {

            classInfo.innerHTML =
                "Select a subject and date.";
        }
    }
}


// ============================================================
// FIND SELECTED CLASS
// ============================================================

function findSelectedClass() {

    const subjectInput =
        getElement(
            "subject-input",
            "class-subject",
            "subject"
        );


    const dateInput =
        getElement(
            "class-date"
        );


    if (
        !subjectInput ||
        !dateInput
    ) {

        return null;
    }


    const subject =
        subjectInput.value
            .trim()
            .toLowerCase();


    const date =
        dateInput.value;


    if (
        !subject ||
        !date
    ) {

        return null;
    }


    const quarter =
        getSelectedQuarter();


    const group =
        getSelectedGroup();


    return availableClasses.find(
        classItem => {

            const classSubject =
                String(
                    classItem.course_name || ""
                )
                .trim()
                .toLowerCase();


            return (
                classSubject === subject &&
                classItem.class_date === date &&
                classQuarter(classItem) === quarter &&
                classGroup(classItem) === group
            );
        }
    ) || null;
}


// ============================================================
// UPDATE SELECTED CLASS
// ============================================================

function updateSelectedClass() {

    const subjectInput =
        getElement(
            "subject-input",
            "class-subject",
            "subject"
        );


    const dateInput =
        getElement(
            "class-date"
        );


    const classInfo =
        getElement(
            "selected-class-info"
        );


    if (
        !subjectInput ||
        !dateInput
    ) {

        return;
    }


    const subject =
        subjectInput.value.trim();


    const date =
        dateInput.value;


    if (
        !subject ||
        !date
    ) {

        currentClassId = null;

        if (classInfo) {

            classInfo.innerHTML =
                "Select a subject and date.";
        }

        resetDashboardVisuals();

        updateExportLink();

        return;
    }


    const selectedClass =
        findSelectedClass();


    if (selectedClass) {

        currentClassId =
            Number(
                selectedClass.id
            );


        if (classInfo) {

            classInfo.innerHTML = `
                <strong>
                    ${escapeHtml(
                        selectedClass.course_name
                    )}
                </strong>

                <span>
                    ${escapeHtml(
                        selectedClass.class_date
                    )}
                </span>

                <span>
                    · Quarter ${escapeHtml(
                        String(
                            classQuarter(selectedClass)
                        )
                    )}
                </span>

                <span>
                    · Group ${escapeHtml(
                        classGroup(selectedClass)
                    )}
                </span>
            `;
        }


        updateExportLink();

        loadDashboard();

        return;
    }


    /*
     * The subject/date combination does not
     * exist yet.
     *
     * It will be created when Start Class
     * is pressed.
     */

    currentClassId = null;


    if (classInfo) {

        classInfo.innerHTML = `
            <strong>
                ${escapeHtml(subject)}
            </strong>

            <span>
                ${escapeHtml(date)}
                · Quarter ${escapeHtml(
                    String(getSelectedQuarter())
                )}
                · Group ${escapeHtml(
                    getSelectedGroup()
                )}
                · Ready to start
            </span>
        `;
    }


    resetDashboardVisuals();

    updateExportLink();
}


// ============================================================
// CREATE CLASS
// ============================================================

async function createClass(
    subject,
    classDate,
    quarter,
    groupName
) {

    const response =
        await fetch(
            "/api/classes",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    course_name: subject,
                    class_date: classDate,
                    quarter: quarter,
                    group_name: groupName,
                    start_time: "00:00",
                    end_time: "00:00"
                })
            }
        );


    const data =
        await response.json();


    if (!response.ok) {

        throw new Error(
            data.detail ||
            data.error ||
            "Could not create the class."
        );
    }


    const createdClass =
        data.class || data;


    // The ClassLY API returns the identifier as `class_id`.
    // Accept both formats so the frontend remains compatible
    // with the API response without changing the backend.
    const classId =
        createdClass.id ??
        createdClass.class_id;


    if (classId === undefined || classId === null) {

        throw new Error(
            "Could not determine the created class ID."
        );
    }


    return {
        ...createdClass,
        id: Number(classId),
        course_name: subject,
        class_date: classDate,
        quarter: quarter,
        group_name: groupName,
    };
}


// ============================================================
// EXPORT LINK
// ============================================================

function updateExportLink() {

    const exportButton =
        getElement(
            "export-button"
        );


    if (!exportButton) {
        return;
    }


    if (!currentClassId) {

        exportButton.href =
            "#";

        return;
    }


    exportButton.href =
        `/api/reports/attendance/${currentClassId}`;
}


// ============================================================
// LOAD DASHBOARD
// ============================================================

async function loadDashboard() {

    if (!currentClassId) {
        return;
    }


    try {

        const response =
            await fetch(
                `/api/dashboard/summary?class_id=${currentClassId}&_=${Date.now()}`,
                {
                    cache: "no-store"
                }
            );


        if (!response.ok) {

            throw new Error(
                "Could not load dashboard data."
            );
        }


        const data =
            await response.json();


        if (data.error) {

            throw new Error(
                data.error
            );
        }


        updateDashboard(
            data
        );


    } catch (error) {

        console.error(
            "Dashboard error:",
            error
        );
    }
}


// ============================================================
// UPDATE DASHBOARD
// ============================================================

function updateDashboard(data) {

    const students =
        Array.isArray(
            data.students
        )
            ? data.students
            : [];


    setText(
        "total-students",
        data.total_students ??
        students.length
    );


    setText(
        "present-students",
        data.present ?? 0
    );


    setText(
        "partial-students",
        data.partial ?? 0
    );


    setText(
        "absent-students",
        data.absent ?? 0
    );


    setText(
        "intruders",
        data.intruders ?? 0
    );

    const totalEntries =
    students.reduce(
        (total, student) =>
            total +
            numberValue(student.entries),
        0
    );


    const totalExits =
        students.reduce(
            (total, student) =>
                total +
                numberValue(student.exits),
            0
        );


    setText(
        "total-entries-summary",
        totalEntries
    );


    setText(
        "total-exits-summary",
        totalExits
    );


    const attendance =
        numberValue(
            data.attendance_percentage
        );


    setText(
        "attendance-percentage",
        `${attendance.toFixed(1)}%`
    );


    const progress =
        getElement(
            "attendance-progress"
        );


    if (progress) {

        progress.style.width =
            `${Math.min(
                Math.max(
                    attendance,
                    0
                ),
                100
            )}%`;
    }


    updateSessionInformation(
        data
    );


    updateAttendanceChart(
        students
    );


    updateEntryExitChart(
        students
    );


    updateTimeChart(
        students
    );


    updateStudentTable(
        students
    );


    updateLiveOccupancy();
}


// ============================================================
// LIVE OCCUPANCY
// ============================================================
//
// Stage 1 reuses the analytics timeline endpoint so the live view
// and the after-class view are drawn from the same reconstruction
// of the session.
// ============================================================

async function updateLiveOccupancy() {

    const container =
        getElement("live-occupancy-chart");


    if (
        !container ||
        !currentClassId ||
        typeof Plotly === "undefined"
    ) {
        return;
    }


    try {

        const response =
            await fetch(
                `/api/analytics/timeline/${currentClassId}` +
                `?_=${Date.now()}`,
                { cache: "no-store" }
            );


        if (!response.ok) {
            return;
        }


        const timeline =
            await response.json();


        const points =
            timeline.points || [];


        if (points.length === 0) {

            container.innerHTML =
                "<div class=\"empty-state\">" +
                "No entries recorded yet in this session." +
                "</div>";

            return;
        }


        Plotly.react(
            container,
            [
                {
                    type: "scatter",
                    mode: "lines",
                    x: points.map(
                        point => point.minute
                    ),
                    y: points.map(
                        point => point.inside
                    ),
                    line: {
                        color: CHART_COLORS.blueDeep,
                        width: 3,
                        shape: "hv"
                    },
                    fill: "tozeroy",
                    fillcolor: "rgba(140,200,232,.24)",
                    customdata: points.map(
                        point => point.clock
                    ),
                    hovertemplate:
                        "Minute %{x}<br>%{customdata}<br>" +
                        "Inside: %{y}<extra></extra>"
                }
            ],
            {
                paper_bgcolor: "rgba(0,0,0,0)",
                plot_bgcolor: "rgba(0,0,0,0)",
                font: {
                    family:
                        "Georgia, 'Times New Roman', serif",
                    size: 12,
                    color: CHART_COLORS.text
                },
                margin: {
                    l: 55,
                    r: 24,
                    t: 18,
                    b: 52
                },
                height: 300,
                xaxis: {
                    title: {
                        text: "Minutes since session start"
                    },
                    gridcolor: "#E7E5F0"
                },
                yaxis: {
                    title: {
                        text: "Students inside"
                    },
                    rangemode: "tozero",
                    gridcolor: "#E7E5F0"
                }
            },
            {
                displayModeBar: false,
                responsive: true
            }
        );


    } catch (error) {

        console.error(
            "Live occupancy error:",
            error
        );
    }
}


// ============================================================
// TEXT HELPER
// ============================================================
//
// Updates ALL elements that use the same ID.
//
// ClassLY has the entry/exit totals displayed in
// more than one place:
//   - Summary statistic card
//   - Entry & Exit Activity card
//
// Using getElementById() only updates the first one.
// querySelectorAll() keeps every display synchronized.
// ============================================================

function setText(
    elementId,
    value
) {

    const elements =
        document.querySelectorAll(
            `#${elementId}`
        );


    if (
        !elements ||
        elements.length === 0
    ) {
        return;
    }


    elements.forEach(
        element => {

            element.textContent =
                value;
        }
    );
}


// ============================================================
// SESSION INFORMATION
// ============================================================

function updateSessionInformation(
    data
) {

    const classData =
        data.class || {};


    const status =
        classData.session_status ||
        "Not started";


    sessionRunning =
        status === "Running";


    sessionStartTimestamp =
        classData.session_started_at
            ? Date.parse(
                classData.session_started_at
            )
            : null;


    sessionStopTimestamp =
        classData.session_stopped_at
            ? Date.parse(
                classData.session_stopped_at
            )
            : null;


    /*
     * Start the local one-second clock while
     * the session is running.
     */

    if (
        sessionRunning &&
        sessionStartTimestamp
    ) {

        startLiveClock();

    } else {

        stopLiveClock();
    }


    /*
     * Started / ended labels.
     */

    const started =
        getElement(
            "session-started",
            "session-start"
        );


    const ended =
        getElement(
            "session-ended",
            "session-end"
        );


    if (started) {

        started.textContent =
            formatSessionTimestamp(
                classData.session_started_at
            );
    }


    if (ended) {

        ended.textContent =
            classData.session_stopped_at
                ? formatSessionTimestamp(
                    classData.session_stopped_at
                )
                : "—";
    }


    /*
     * Update duration immediately.
     */

    updateClockDisplay();


    /*
     * If the session is completed,
     * use the final backend duration as a fallback
     * only when timestamps are unavailable.
     */

    if (
        status === "Completed" &&
        !sessionStartTimestamp
    ) {

        const duration =
            formatDurationFromSeconds(
                numberValue(
                    classData.session_duration_minutes
                ) * 60
            );


        setDurationElements(
            duration
        );
    }


    updateSessionButtons(
        status
    );
}


// ============================================================
// SET ALL DURATION ELEMENTS
// ============================================================

function setDurationElements(
    formatted
) {

    const ids = [
        "session-duration",
        "class-duration",
        "duration",
        "session-timer",
        "class-timer"
    ];


    ids.forEach(
        id => {

            const element =
                document.getElementById(
                    id
                );


            if (element) {

                element.textContent =
                    formatted;
            }
        }
    );


    document
        .querySelectorAll(
            "[data-session-duration]"
        )
        .forEach(
            element => {

                element.textContent =
                    formatted;
            }
        );
}


// ============================================================
// FORMAT SESSION TIMESTAMP
// ============================================================

function formatSessionTimestamp(
    timestamp
) {

    if (!timestamp) {
        return "—";
    }


    const date =
        new Date(timestamp);


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return "—";
    }


    return date.toLocaleString(
        "en-US",
        {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false
        }
    );
}


// ============================================================
// SESSION BUTTONS
// ============================================================

function updateSessionButtons(
    status
) {

    const startButton =
        getElement(
            "start-class-button"
        );


    const stopButton =
        getElement(
            "stop-class-button"
        );


    if (startButton) {

        if (status === "Running") {

            startButton.textContent =
                "Class Running";

            startButton.disabled =
                true;

            startButton.classList.add(
                "running-button"
            );

        } else if (
            status === "Completed"
        ) {

            startButton.textContent =
                "Class Completed";

            startButton.disabled =
                true;

            startButton.classList.remove(
                "running-button"
            );

        } else {

            startButton.textContent =
                "Start Class";

            startButton.disabled =
                false;

            startButton.classList.remove(
                "running-button"
            );
        }
    }


    if (stopButton) {

        stopButton.disabled =
            status !== "Running";
    }
}


// ============================================================
// RESET DASHBOARD
// ============================================================

function resetDashboardVisuals() {

    setText(
        "total-students",
        0
    );

    setText(
        "present-students",
        0
    );

    setText(
        "partial-students",
        0
    );

    setText(
        "absent-students",
        0
    );

    setText(
        "intruders",
        0
    );

    setText(
        "total-entries-summary",
        0
    );

    setText(
        "total-exits-summary",
        0
    );

    setText(
        "attendance-percentage",
        "0.0%"
    );


    const progress =
        getElement(
            "attendance-progress"
        );


    if (progress) {

        progress.style.width =
            "0%";
    }


    sessionRunning = false;

    sessionStartTimestamp = null;

    sessionStopTimestamp = null;


    stopLiveClock();


    setDurationElements(
        "00:00:00"
    );


    updateAttendanceChart([]);

    updateEntryExitChart([]);

    updateTimeChart([]);

    updateStudentTable([]);


    /*
     * BUG FIX (v7):
     *
     * Without this call, the Start Class button stayed stuck on
     * "Class Completed" / disabled after finishing a class, even
     * once the user had typed the name of a brand new class that
     * had never been started.
     *
     * updateSessionButtons() only used to run from
     * updateSessionInformation(), which is fed by loadDashboard().
     * loadDashboard() is only called when the selected subject
     * already matches an existing class. For a class that does
     * not exist yet, updateSelectedClass() calls
     * resetDashboardVisuals() instead and never touched the
     * button — so the button kept showing the previous class's
     * state, and Reset Class Data looked like the only way out
     * (at the cost of deleting that previous class's real data).
     */

    updateSessionButtons(
        "Not started"
    );
}


// ============================================================
// PASTEL CHART PALETTE
// One visual color per student, all inside the blue/purple
// pastel family requested for the new interface.
// ============================================================

const STUDENT_CHART_PALETTE = [
    "#8CC8E8",
    "#A99BD7",
    "#9DBFE0",
    "#B9A9DE",
    "#76B5D5",
    "#C5B9E8",
    "#91C9D7",
    "#9E8CCB",
    "#A8CBEA",
    "#B7A4D8",
    "#78A9CE",
    "#C9BEE2"
];

function hexToRgba(hex, alpha) {
    const value = hex.replace("#", "");
    const bigint = parseInt(value, 16);
    const r = (bigint >> 16) & 255;
    const g = (bigint >> 8) & 255;
    const b = bigint & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function studentChartColor(index) {
    return STUDENT_CHART_PALETTE[
        index % STUDENT_CHART_PALETTE.length
    ];
}

function makeChartTooltip(element, text) {
    element.title = text;
    element.setAttribute("aria-label", text);
}

// ============================================================
// CHART 1
// ATTENDANCE PERCENTAGE BY STUDENT
// ============================================================

function updateAttendanceChart(students) {

    const container = document.getElementById("attendance-chart");

    if (!container) return;

    container.innerHTML = "";

    if (!Array.isArray(students) || students.length === 0) {
        container.innerHTML = `
            <div class="chart-empty-state">
                No attendance data available.
            </div>
        `;
        return;
    }

    const sortedStudents = [...students].sort(
        (a, b) => numberValue(b.inside_percentage) - numberValue(a.inside_percentage)
    );

    const wrapper = document.createElement("div");
    wrapper.className = "pastel-chart-scroll";

    const chart = document.createElement("div");
    chart.className = "pastel-column-chart attendance-column-chart";
    chart.style.minWidth = `${Math.max(820, sortedStudents.length * 82)}px`;

    sortedStudents.forEach((student, index) => {

        const percentage = Math.min(
            Math.max(numberValue(student.inside_percentage), 0),
            100
        );

        const color = studentChartColor(index);
        const shortName = getShortStudentName(student.full_name);

        const column = document.createElement("div");
        column.className = "pastel-column";

        const value = document.createElement("div");
        value.className = "pastel-value";
        value.textContent = `${percentage.toFixed(1)}%`;

        const track = document.createElement("div");
        track.className = "pastel-track";

        const bar = document.createElement("div");
        bar.className = "pastel-bar";
        bar.style.height = `${percentage}%`;
        bar.style.background = `linear-gradient(180deg, ${color}, ${hexToRgba(color, .78)})`;

        const hover = document.createElement("div");
        hover.className = "chart-hover-card";
        hover.innerHTML = `
            <strong>${escapeHtml(shortName)}</strong>
            <span>Attendance: ${percentage.toFixed(1)}%</span>
        `;

        const name = document.createElement("div");
        name.className = "pastel-name";
        name.textContent = shortName;
        name.title = student.full_name || "";

        makeChartTooltip(
            column,
            `${shortName} — Attendance: ${percentage.toFixed(1)}%`
        );

        column.addEventListener("mouseenter", () => {
            column.classList.add("is-hovered");
        });
        column.addEventListener("mouseleave", () => {
            column.classList.remove("is-hovered");
        });

        track.appendChild(bar);
        column.appendChild(value);
        column.appendChild(track);
        column.appendChild(hover);
        column.appendChild(name);
        chart.appendChild(column);
    });

    wrapper.appendChild(chart);
    container.appendChild(wrapper);
}

// ============================================================
// CHART 2
// ENTRY & EXIT EVENTS BY STUDENT
// ============================================================

function updateEntryExitChart(students) {

    const container = document.getElementById("entry-exit-chart");

    if (!container) return;

    container.innerHTML = "";

    if (!Array.isArray(students) || students.length === 0) {
        container.innerHTML = `
            <div class="chart-empty-state">
                No event data available.
            </div>
        `;
        return;
    }

    const sortedStudents = [...students].sort((a, b) => {
        const totalA = numberValue(a.entries) + numberValue(a.exits);
        const totalB = numberValue(b.entries) + numberValue(b.exits);
        return totalB - totalA;
    });

    const maximum = Math.max(
        ...sortedStudents.map(student => Math.max(
            numberValue(student.entries),
            numberValue(student.exits)
        )),
        1
    );

    const wrapper = document.createElement("div");
    wrapper.className = "pastel-chart-scroll";

    const chart = document.createElement("div");
    chart.className = "pastel-column-chart events-column-chart";
    chart.style.minWidth = `${Math.max(820, sortedStudents.length * 86)}px`;

    sortedStudents.forEach((student, index) => {

        const entries = numberValue(student.entries);
        const exits = numberValue(student.exits);
        const color = studentChartColor(index);
        const shortName = getShortStudentName(student.full_name);

        const group = document.createElement("div");
        group.className = "pastel-column event-column";

        const values = document.createElement("div");
        values.className = "event-values";
        values.innerHTML = `
            <span style="color:${color}">${entries}</span>
            <span class="event-separator">/</span>
            <span style="color:${hexToRgba(color, .72)}">${exits}</span>
        `;

        const barArea = document.createElement("div");
        barArea.className = "event-bar-area";

        const entryTrack = document.createElement("div");
        entryTrack.className = "pastel-track event-track";

        const entryBar = document.createElement("div");
        entryBar.className = "pastel-bar";
        entryBar.style.height = `${(entries / maximum) * 100}%`;
        entryBar.style.background = color;

        const exitTrack = document.createElement("div");
        exitTrack.className = "pastel-track event-track";

        const exitBar = document.createElement("div");
        exitBar.className = "pastel-bar";
        exitBar.style.height = `${(exits / maximum) * 100}%`;
        exitBar.style.background = hexToRgba(color, .48);

        const hover = document.createElement("div");
        hover.className = "chart-hover-card event-hover";
        hover.innerHTML = `
            <strong>${escapeHtml(shortName)}</strong>
            <span>Entries: ${entries}</span>
            <span>Exits: ${exits}</span>
        `;

        const name = document.createElement("div");
        name.className = "pastel-name";
        name.textContent = shortName;
        name.title = student.full_name || "";

        makeChartTooltip(
            group,
            `${shortName} — Entries: ${entries} | Exits: ${exits}`
        );

        group.addEventListener("mouseenter", () => {
            group.classList.add("is-hovered");
        });
        group.addEventListener("mouseleave", () => {
            group.classList.remove("is-hovered");
        });

        entryTrack.appendChild(entryBar);
        exitTrack.appendChild(exitBar);
        barArea.appendChild(entryTrack);
        barArea.appendChild(exitTrack);

        group.appendChild(values);
        group.appendChild(barArea);
        group.appendChild(hover);
        group.appendChild(name);
        chart.appendChild(group);
    });

    wrapper.appendChild(chart);
    container.appendChild(wrapper);
}

// ============================================================
// CHART 3
// INSIDE VS OUTSIDE TIME
//
// Keeps the same stacked horizontal concept, but uses the
// backend's actual total_inside_minutes / total_outside_minutes
// values directly. No artificial fallback is applied here.
// ============================================================

function updateTimeChart(students) {

    const container = document.getElementById("time-chart");

    if (!container) return;

    container.innerHTML = "";

    if (!Array.isArray(students) || students.length === 0) {
        container.innerHTML = `
            <div class="chart-empty-state">
                No time data available.
            </div>
        `;
        return;
    }

    const processedStudents = students.map(student => {

        const inside = Math.max(
            0,
            numberValue(
                student.total_inside_minutes ??
                student.minutes_inside ??
                student.inside_minutes ??
                0
            )
        );

        const outside = Math.max(
            0,
            numberValue(
                student.total_outside_minutes ??
                student.minutes_outside ??
                student.outside_minutes ??
                0
            )
        );

        const total = Math.max(0, inside + outside);

        return {
            student,
            inside,
            outside,
            total
        };
    });

    processedStudents.sort((a, b) => b.inside - a.inside);

    const wrapper = document.createElement("div");
    wrapper.className = "time-chart-wrapper";

    processedStudents.forEach((item, index) => {

        const student = item.student;
        const inside = item.inside;
        const outside = item.outside;
        const total = item.total;

        const insidePercentage = total > 0 ? (inside / total) * 100 : 0;
        const outsidePercentage = total > 0 ? (outside / total) * 100 : 0;

        const row = document.createElement("div");
        row.className = "time-row";

        const label = document.createElement("div");
        label.className = "time-name";
        label.textContent = getShortStudentName(student.full_name);
        label.title = student.full_name || "";

        const track = document.createElement("div");
        track.className = "time-track";

        const insideBar = document.createElement("div");
        insideBar.className = "time-inside";
        insideBar.style.width = `${insidePercentage}%`;

        const outsideBar = document.createElement("div");
        outsideBar.className = "time-outside";
        outsideBar.style.width = `${outsidePercentage}%`;

        const tooltip = document.createElement("div");
        tooltip.className = "time-tooltip";
        tooltip.innerHTML = `
            <strong>${escapeHtml(getShortStudentName(student.full_name))}</strong>
            <span>Inside: ${inside.toFixed(1)} min</span>
            <span>Outside: ${outside.toFixed(1)} min</span>
            <span>Total: ${total.toFixed(1)} min</span>
        `;

        makeChartTooltip(
            track,
            `${getShortStudentName(student.full_name)} — Inside: ${inside.toFixed(1)} min | Outside: ${outside.toFixed(1)} min`
        );

        track.addEventListener("mouseenter", () => {
            row.classList.add("is-hovered");
        });
        track.addEventListener("mouseleave", () => {
            row.classList.remove("is-hovered");
        });

        track.appendChild(insideBar);
        track.appendChild(outsideBar);
        track.appendChild(tooltip);

        row.appendChild(label);
        row.appendChild(track);
        wrapper.appendChild(row);
    });

    container.appendChild(wrapper);
}


// ============================================================
// STUDENT TABLE
//
// FULL NAMES ARE PRESERVED HERE.
// ============================================================

function updateStudentTable(
    students
) {

    const tableBody =
        getElement(
            "student-table-body"
        );


    if (!tableBody) {
        return;
    }


    tableBody.innerHTML = "";


    if (
        !students ||
        students.length === 0
    ) {

        tableBody.innerHTML = `
            <tr>
                <td colspan="8">
                    No session data available.
                </td>
            </tr>
        `;

        return;
    }


    students.forEach(
        student => {

            const row =
                document.createElement(
                    "tr"
                );


            const status =
                String(
                    student.status ||
                    "Absent"
                );

            const outsideMinutes =
                status.toLowerCase() === "absent"
                    ? 0
                    : numberValue(student.total_outside_minutes);


            row.innerHTML = `
                <td>
                    ${escapeHtml(
                        student.full_name
                    )}
                </td>

                <td>
                    ${escapeHtml(
                        student.student_code
                    )}
                </td>

                <td>
                    ${numberValue(
                        student.entries
                    )}
                </td>

                <td>
                    ${numberValue(
                        student.exits
                    )}
                </td>

                <td>
                    ${numberValue(
                        student.total_inside_minutes
                    ).toFixed(1)}
                    min
                </td>

                <td>
                    ${outsideMinutes.toFixed(1)}
                    min
                </td>

                <td>
                    ${numberValue(
                        student.inside_percentage
                    ).toFixed(1)}%
                </td>

                <td class="
                    status-${status.toLowerCase()}
                ">
                    ${escapeHtml(
                        status
                    )}
                </td>
            `;


            tableBody.appendChild(
                row
            );
        }
    );
}


// ============================================================
// START CLASS
// ============================================================

async function startClass() {

    const subjectInput =
        getElement(
            "subject-input",
            "class-subject",
            "subject"
        );


    const dateInput =
        getElement(
            "class-date"
        );


    const button =
        getElement(
            "start-class-button"
        );


    if (!subjectInput) {

        alert(
            "Please enter a subject."
        );

        return;
    }


    const subject =
        subjectInput.value.trim();


    const classDate =
        dateInput
            ? dateInput.value
            : "";


    if (!subject) {

        alert(
            "Please enter a subject."
        );

        subjectInput.focus();

        return;
    }


    if (!classDate) {

        alert(
            "Please select a class date."
        );

        if (dateInput) {
            dateInput.focus();
        }

        return;
    }


    if (button) {
        button.disabled = true;
    }


    try {

        let selectedClass =
            findSelectedClass();


        /*
         * Create class if necessary.
         */

        if (!selectedClass) {

            selectedClass =
                await createClass(
                    subject,
                    classDate,
                    getSelectedQuarter(),
                    getSelectedGroup()
                );


            availableClasses.push(
                selectedClass
            );
        }


        currentClassId =
            Number(
                selectedClass.id
            );


        updateExportLink();


        /*
         * Start actual camera/session.
         */

        const response =
            await fetch(
                "/api/session/start",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        class_id:
                            currentClassId
                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                data.error ||
                "Could not start the class."
            );
        }


        console.log(
            "Class started:",
            data
        );


        await loadDashboard();


    } catch (error) {

        console.error(
            "Could not start class:",
            error
        );


        alert(
            error.message ||
            "Could not start the class."
        );


        if (button) {
            button.disabled = false;
        }
    }
}


// ============================================================
// STOP CLASS
// ============================================================

async function stopClass() {

    const button =
        getElement(
            "stop-class-button"
        );


    if (button) {
        button.disabled = true;
    }


    try {

        const response =
            await fetch(
                "/api/session/stop",
                {
                    method: "POST"
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                data.error ||
                "Could not stop the class."
            );
        }


        console.log(
            "Class stopped:",
            data
        );


        await loadDashboard();


    } catch (error) {

        console.error(
            "Could not stop class:",
            error
        );


        alert(
            error.message ||
            "Could not stop the class."
        );


        if (button) {
            button.disabled = false;
        }
    }
}


// ============================================================
// RESET CLASS DATA
// ============================================================

async function resetClassData() {

    if (!currentClassId) {

        alert(
            "Please select a class first."
        );

        return;
    }


    const confirmed =
        window.confirm(
            "Reset this class data?\n\n" +
            "Attendance events and intruder events " +
            "will be deleted, and the session will be " +
            "reset. The subject, date, students, photos, " +
            "and face embeddings will be preserved."
        );


    if (!confirmed) {
        return;
    }


    try {

        const response =
            await fetch(
                "/api/session/reset",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        class_id:
                            currentClassId
                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                data.error ||
                "Could not reset class data."
            );
        }


        console.log(
            "Class data reset:",
            data
        );


        resetDashboardVisuals();


        await loadDashboard();


    } catch (error) {

        console.error(
            "Could not reset class data:",
            error
        );


        alert(
            error.message ||
            "Could not reset class data."
        );
    }
}


// ============================================================
// INITIALIZE
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        populateAcademicSelectors();


        const dateInput =
            getElement(
                "class-date"
            );


        const subjectInput =
            getElement(
                "subject-input",
                "class-subject",
                "subject"
            );


        /*
         * Quarter / Group change.
         */

        [
            getQuarterInput(),
            getGroupInput()
        ].forEach(
            selector => {

                if (!selector) {
                    return;
                }


                selector.addEventListener(
                    "change",
                    () => {

                        if (!sessionRunning) {
                            updateSelectedClass();
                        }
                    }
                );
            }
        );


        /*
         * Date change.
         */

        if (dateInput) {

            dateInput.addEventListener(
                "change",
                () => {

                    if (!sessionRunning) {
                        updateSelectedClass();
                    }
                }
            );
        }


        /*
         * Subject change.
         */

        if (subjectInput) {

            subjectInput.addEventListener(
                "input",
                () => {

                    if (!sessionRunning) {
                        updateSelectedClass();
                    }
                }
            );


            subjectInput.addEventListener(
                "change",
                () => {

                    if (!sessionRunning) {
                        updateSelectedClass();
                    }
                }
            );
        }


        /*
         * Load classes.
         */

        await loadClasses();


        /*
         * Dashboard refresh.
         */

        dashboardInterval =
            setInterval(
                () => {

                    if (currentClassId) {
                        loadDashboard();
                    }

                },
                5000
            );


        /*
         * Clock refresh.
         *
         * This is intentionally independent
         * from the dashboard refresh.
         */

        startLiveClock();
    }
);