// ============================================================
// CLASSLY — STAGE 3 : END OF COURSE
// ============================================================
//
// Cross-group assessment for the coordinator.
//
// Data source: /api/analytics/coordinator
// ============================================================

const PALETTE = {
    blue: "#8CC8E8",
    blueDeep: "#5D91C2",
    purple: "#A99BD7",
    purpleDeep: "#7765AE",
    mint: "#9FD5CA",
    amber: "#E8C77A",
    coral: "#E2766F",
    text: "#20253A",
    border: "#E7E5F0"
};


const GROUP_COLORS = [
    "#8CC8E8",
    "#A99BD7",
    "#9FD5CA",
    "#E8C77A",
    "#E2766F",
    "#CBBCE8",
    "#76B5D5",
    "#E4B9D5"
];


const PLOT_FONT = {
    family: "Georgia, 'Times New Roman', serif",
    size: 12,
    color: PALETTE.text
};


const PLOT_CONFIG = {
    displayModeBar: false,
    responsive: true
};


let currentQuarter = null;


// ============================================================
// HELPERS
// ============================================================

function element(id) {
    return document.getElementById(id);
}


function escapeHtml(value) {

    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}


function setText(id, value) {

    const node = element(id);

    if (node) {
        node.textContent = value;
    }
}


function baseLayout(extra) {

    return Object.assign(
        {
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: PLOT_FONT,
            margin: { l: 60, r: 24, t: 24, b: 70 },
            hovermode: "closest"
        },
        extra || {}
    );
}


function emptyPlot(containerId, message) {

    const node = element(containerId);

    if (node) {
        node.innerHTML =
            `<div class="empty-state">${escapeHtml(message)}</div>`;
    }
}


async function getJson(url) {

    const response = await fetch(
        `${url}${url.includes("?") ? "&" : "?"}_=${Date.now()}`,
        { cache: "no-store" }
    );

    if (!response.ok) {
        throw new Error(`Request failed: ${url}`);
    }

    return response.json();
}


function attendanceColor(value) {

    if (value >= 80) {
        return PALETTE.mint;
    }

    if (value >= 60) {
        return PALETTE.blue;
    }

    if (value >= 40) {
        return PALETTE.amber;
    }

    return PALETTE.coral;
}


// ============================================================
// CHARTS
// ============================================================

function renderGroupChart(groups) {

    if (!groups.length) {

        emptyPlot(
            "group-chart",
            "No recorded sessions for this quarter."
        );

        return;
    }

    const sorted = groups
        .slice()
        .sort(
            (first, second) =>
                second.average_attendance - first.average_attendance
        );

    Plotly.newPlot(
        "group-chart",
        [
            {
                type: "bar",
                x: sorted.map(group => group.label),
                y: sorted.map(group => group.average_attendance),
                marker: {
                    color: sorted.map(group =>
                        attendanceColor(group.average_attendance)
                    ),
                    line: { width: 0 }
                },
                text: sorted.map(
                    group => `${group.average_attendance}%`
                ),
                textposition: "outside",
                hovertemplate:
                    "%{x}<br>Average: %{y}%<extra></extra>"
            },
            {
                type: "scatter",
                mode: "lines",
                name: "Threshold",
                x: sorted.map(group => group.label),
                y: sorted.map(() => 80),
                line: {
                    color: PALETTE.coral,
                    width: 2,
                    dash: "dot"
                },
                hoverinfo: "skip"
            }
        ],
        baseLayout({
            height: 380,
            showlegend: false,
            xaxis: { tickangle: -25, automargin: true },
            yaxis: {
                title: { text: "% inside", font: PLOT_FONT },
                range: [0, 108],
                gridcolor: PALETTE.border
            }
        }),
        PLOT_CONFIG
    );
}


function renderEvolutionChart(groups) {

    if (!groups.length) {

        emptyPlot("evolution-chart", "Nothing to plot.");

        return;
    }

    const traces = groups.map((group, index) => ({
        type: "scatter",
        mode: "lines+markers",
        name: group.label,
        x: group.session_labels,
        y: group.session_averages,
        line: {
            color: GROUP_COLORS[index % GROUP_COLORS.length],
            width: 3,
            shape: "spline"
        },
        marker: { size: 7 },
        hovertemplate:
            `${escapeHtml(group.label)}<br>` +
            "%{x}<br>Average: %{y}%<extra></extra>"
    }));

    Plotly.newPlot(
        "evolution-chart",
        traces,
        baseLayout({
            height: 380,
            xaxis: { tickangle: -40, automargin: true },
            yaxis: {
                title: { text: "% inside", font: PLOT_FONT },
                range: [0, 105],
                gridcolor: PALETTE.border
            },
            legend: { orientation: "h", y: -0.32 }
        }),
        PLOT_CONFIG
    );
}


function renderQuadrantChart(groups) {

    if (!groups.length) {

        emptyPlot("quadrant-chart", "Nothing to plot.");

        return;
    }

    const maxRisk = Math.max(
        1,
        ...groups.map(group => group.students_below_threshold)
    );

    Plotly.newPlot(
        "quadrant-chart",
        [
            {
                type: "scatter",
                mode: "markers+text",
                x: groups.map(group => group.average_attendance),
                y: groups.map(group => group.average_consistency),
                text: groups.map(group => group.group_name),
                textposition: "middle center",
                textfont: {
                    family: PLOT_FONT.family,
                    color: "#ffffff",
                    size: 13
                },
                marker: {
                    size: groups.map(
                        group =>
                            26 +
                            (group.students_below_threshold /
                                maxRisk) *
                                34
                    ),
                    color: groups.map(group =>
                        attendanceColor(group.average_attendance)
                    ),
                    line: { width: 2, color: "#ffffff" },
                    opacity: 0.92
                },
                customdata: groups.map(group => [
                    group.label,
                    group.students_below_threshold,
                    group.average_trend
                ]),
                hovertemplate:
                    "%{customdata[0]}<br>" +
                    "Attendance: %{x}%<br>" +
                    "Consistency: %{y}<br>" +
                    "Below threshold: %{customdata[1]} students<br>" +
                    "Trend: %{customdata[2]} pts/session<extra></extra>"
            }
        ],
        baseLayout({
            height: 420,
            showlegend: false,
            shapes: [
                {
                    type: "line",
                    x0: 80,
                    x1: 80,
                    y0: 0,
                    y1: 100,
                    line: {
                        color: PALETTE.coral,
                        width: 2,
                        dash: "dot"
                    }
                }
            ],
            xaxis: {
                title: {
                    text: "Average attendance (%)",
                    font: PLOT_FONT
                },
                range: [0, 105],
                gridcolor: PALETTE.border
            },
            yaxis: {
                title: {
                    text: "Average consistency",
                    font: PLOT_FONT
                },
                range: [0, 105],
                gridcolor: PALETTE.border
            }
        }),
        PLOT_CONFIG
    );
}


function isDemoGroup(group) {

    return String(group.course_name || "").startsWith("[DEMO]");
}


function toggleDemoBanner(groups) {

    const banner = element("demo-banner");

    if (!banner) {
        return;
    }

    banner.classList.toggle(
        "visible",
        groups.some(isDemoGroup)
    );
}


function cleanCourseName(courseName) {

    return String(courseName || "").replace("[DEMO] ", "");
}


function renderTable(groups) {

    const body = element("group-table-body");

    if (!body) {
        return;
    }

    body.innerHTML = groups
        .slice()
        .sort(
            (first, second) =>
                second.average_attendance - first.average_attendance
        )
        .map(group => {

            const level =
                group.average_attendance >= 80
                    ? "low"
                    : group.average_attendance >= 60
                    ? "medium"
                    : "high";

            return `
                <tr>
                    <td>
                        ${escapeHtml(
                            cleanCourseName(group.course_name)
                        )}
                        ${
                            isDemoGroup(group)
                                ? '<span class="tag tag-medium" ' +
                                  'style="margin-left:6px">DEMO</span>'
                                : ""
                        }
                    </td>
                    <td>${group.quarter}</td>
                    <td>${escapeHtml(group.group_name)}</td>
                    <td>${group.sessions}</td>
                    <td>${group.students}</td>
                    <td>
                        <span class="tag tag-${level}">
                            ${group.average_attendance}%
                        </span>
                    </td>
                    <td>${group.average_consistency}</td>
                    <td>${group.average_trend}</td>
                    <td>${group.students_below_threshold}</td>
                </tr>
            `;
        })
        .join("");
}


// ============================================================
// LOAD
// ============================================================

async function loadOverview() {

    const query =
        currentQuarter === null || currentQuarter === ""
            ? ""
            : `?quarter=${encodeURIComponent(currentQuarter)}`;

    const data = await getJson(
        `/api/analytics/coordinator${query}`
    );

    const groups = data.groups || [];

    toggleDemoBanner(groups);

    setText("metric-groups", data.total_groups);

    setText(
        "metric-institution",
        `${data.institution_average}%`
    );

    setText("metric-best", data.best_group || "—");

    setText("metric-worst", data.worst_group || "—");

    renderGroupChart(groups);

    renderEvolutionChart(groups);

    renderQuadrantChart(groups);

    renderTable(groups);

    return data;
}


function populateQuarters(quarters) {

    const select = element("quarter-select");

    if (!select) {
        return;
    }

    select.innerHTML =
        "<option value=''>All quarters</option>";

    quarters.forEach(quarter => {

        const option = document.createElement("option");

        option.value = String(quarter);
        option.textContent = `Quarter ${quarter}`;

        select.appendChild(option);
    });

    select.addEventListener("change", async () => {

        currentQuarter =
            select.value === "" ? null : Number(select.value);

        await loadOverview();
    });
}


// ============================================================
// INITIALIZE
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        try {

            const data = await loadOverview();

            populateQuarters(data.quarters || []);

        } catch (error) {

            console.error("Coordinator error:", error);

            emptyPlot(
                "group-chart",
                "Could not load the coordinator overview."
            );
        }
    }
);
