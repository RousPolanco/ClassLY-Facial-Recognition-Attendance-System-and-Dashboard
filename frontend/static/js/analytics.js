// ============================================================
// CLASSLY — STAGE 2 : AFTER CLASS
// ============================================================
//
// Course level analysis for the professor.
//
// Data sources:
//   /api/analytics/course            aggregated history
//   /api/analytics/timeline/{id}     occupancy of one session
//   /api/analytics/clusters          K-Means profiles
//   /api/analytics/risk              logistic regression
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
    muted: "#72788F",
    border: "#E7E5F0"
};


const PLOT_FONT = {
    family: "Georgia, 'Times New Roman', serif",
    size: 12,
    color: PALETTE.text
};


const PLOT_CONFIG = {
    displayModeBar: false,
    responsive: true
};


let currentScope = null;
let currentCourse = null;
let currentClusters = null;


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


function shortName(fullName) {

    const parts = String(fullName || "")
        .trim()
        .split(/\s+/);

    if (parts.length <= 2) {
        return fullName;
    }

    return `${parts[0]} ${parts[1]}`;
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
            margin: { l: 60, r: 24, t: 24, b: 60 },
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


function scopeQuery(scope) {

    return (
        `course_name=${encodeURIComponent(scope.course_name)}` +
        `&quarter=${encodeURIComponent(scope.quarter)}` +
        `&group_name=${encodeURIComponent(scope.group_name)}`
    );
}


// ============================================================
// SCOPES
// ============================================================

function toggleDemoBanner(scope) {

    const banner = element("demo-banner");

    if (!banner) {
        return;
    }

    const isDemo =
        Boolean(scope) &&
        String(scope.course_name || "").startsWith("[DEMO]");

    banner.classList.toggle("visible", isDemo);
}


async function loadScopes() {

    const select = element("scope-select");

    if (!select) {
        return;
    }

    const data = await getJson("/api/analytics/scopes");

    const scopes = data.scopes || [];

    select.innerHTML = "";

    if (scopes.length === 0) {

        select.innerHTML =
            "<option value=''>No recorded sessions yet</option>";

        emptyPlot(
            "heatmap-chart",
            "No sessions recorded. Run a class first, or generate " +
            "demo data with: python -m scripts.seed_demo_data"
        );

        return;
    }

    scopes.forEach((scope, index) => {

        const option = document.createElement("option");

        option.value = String(index);

        option.textContent =
            `${scope.course_name} · Q${scope.quarter} · ` +
            `Group ${scope.group_name} (${scope.sessions} sessions)`;

        select.appendChild(option);
    });

    // Default to the scope with the richest history, which is the
    // one where the analysis is actually meaningful.
    const richest = scopes.reduce(
        (best, scope, index) =>
            scope.sessions > scopes[best].sessions ? index : best,
        0
    );

    select.value = String(richest);

    currentScope = scopes[richest];

    toggleDemoBanner(currentScope);

    select.addEventListener("change", () => {

        currentScope = scopes[Number(select.value)];

        toggleDemoBanner(currentScope);

        refresh();
    });
}


// ============================================================
// KEY METRICS
// ============================================================

function updateMetrics(course) {

    setText("metric-sessions", course.scope.total_sessions);
    setText("metric-students", course.scope.total_students);

    setText(
        "metric-average",
        `${course.course_average_attendance}%`
    );

    setText(
        "metric-risk",
        course.students_below_threshold
    );
}


// ============================================================
// HEATMAP
// ============================================================

function renderHeatmap(course) {

    const heatmap = course.heatmap;

    if (!heatmap.x.length || !heatmap.y.length) {

        emptyPlot(
            "heatmap-chart",
            "This scope has no recorded sessions."
        );

        return;
    }

    Plotly.newPlot(
        "heatmap-chart",
        [
            {
                type: "heatmap",
                x: heatmap.x,
                y: heatmap.y.map(shortName),
                z: heatmap.z,
                zmin: 0,
                zmax: 100,
                colorscale: [
                    [0, "#F6D7D2"],
                    [0.4, "#F3E3C9"],
                    [0.8, "#CFE4F3"],
                    [1, "#7765AE"]
                ],
                hovertemplate:
                    "%{y}<br>%{x}<br>" +
                    "Inside: %{z}%<extra></extra>",
                colorbar: {
                    title: { text: "% inside", font: PLOT_FONT },
                    tickfont: PLOT_FONT,
                    thickness: 12
                }
            }
        ],
        baseLayout({
            height: Math.max(
                320,
                heatmap.y.length * 26 + 130
            ),
            margin: { l: 170, r: 24, t: 14, b: 74 },
            xaxis: { tickangle: -40, automargin: true },
            yaxis: { automargin: true }
        }),
        PLOT_CONFIG
    );
}


// ============================================================
// SESSION TREND
// ============================================================

function renderTrend(course) {

    const sessions = course.sessions || [];

    if (!sessions.length) {

        emptyPlot("trend-chart", "No sessions to plot.");

        return;
    }

    const labels = sessions.map(session => session.label);

    Plotly.newPlot(
        "trend-chart",
        [
            {
                type: "scatter",
                mode: "lines+markers",
                name: "Group average",
                x: labels,
                y: sessions.map(
                    session => session.average_attendance
                ),
                line: {
                    color: PALETTE.purpleDeep,
                    width: 3,
                    shape: "spline"
                },
                marker: { size: 8, color: PALETTE.purple },
                fill: "tozeroy",
                fillcolor: "rgba(169,155,215,.16)",
                hovertemplate:
                    "%{x}<br>Average: %{y}%<extra></extra>"
            },
            {
                type: "scatter",
                mode: "lines",
                name: "Present threshold",
                x: labels,
                y: labels.map(() => 80),
                line: {
                    color: PALETTE.coral,
                    width: 2,
                    dash: "dot"
                },
                hoverinfo: "skip"
            }
        ],
        baseLayout({
            height: 330,
            yaxis: {
                title: { text: "% inside", font: PLOT_FONT },
                range: [0, 105],
                gridcolor: PALETTE.border
            },
            xaxis: { tickangle: -40, automargin: true },
            legend: { orientation: "h", y: -0.28 }
        }),
        PLOT_CONFIG
    );
}


// ============================================================
// SESSION SELECTOR
// ============================================================

function populateSessionSelect(course) {

    const select = element("session-select");

    if (!select) {
        return;
    }

    const sessions = course.sessions || [];

    select.innerHTML = "";

    if (!sessions.length) {

        select.innerHTML =
            "<option value=''>No sessions</option>";

        emptyPlot("occupancy-chart", "No sessions to plot.");
        emptyPlot("bands-chart", "No sessions to plot.");

        return;
    }

    sessions.forEach(session => {

        const option = document.createElement("option");

        option.value = String(session.id);

        option.textContent =
            `${session.label} · avg ` +
            `${session.average_attendance}%`;

        select.appendChild(option);
    });

    // The most recent session is the one the professor just gave.
    select.value = String(sessions[sessions.length - 1].id);

    select.onchange = () => {
        loadTimeline(Number(select.value));
    };

    loadTimeline(Number(select.value));
}


// ============================================================
// OCCUPANCY + PRESENCE BANDS
// ============================================================

async function loadTimeline(classId) {

    try {

        const timeline = await getJson(
            `/api/analytics/timeline/${classId}`
        );

        renderOccupancy(timeline);

        renderBands(timeline);

    } catch (error) {

        console.error("Timeline error:", error);

        emptyPlot(
            "occupancy-chart",
            "Could not load the session timeline."
        );
    }
}


function renderOccupancy(timeline) {

    const points = timeline.points || [];

    if (!points.length) {

        emptyPlot(
            "occupancy-chart",
            timeline.message ||
            "This session has no recorded events."
        );

        return;
    }

    Plotly.newPlot(
        "occupancy-chart",
        [
            {
                type: "scatter",
                mode: "lines",
                name: "Students inside",
                x: points.map(point => point.minute),
                y: points.map(point => point.inside),
                line: {
                    color: PALETTE.blueDeep,
                    width: 3,
                    shape: "hv"
                },
                fill: "tozeroy",
                fillcolor: "rgba(140,200,232,.24)",
                customdata: points.map(point => point.clock),
                hovertemplate:
                    "Minute %{x}<br>%{customdata}<br>" +
                    "Inside: %{y}<extra></extra>"
            },
            {
                type: "scatter",
                mode: "lines",
                name: "Retention (%)",
                yaxis: "y2",
                x: (timeline.dropoff || []).map(
                    point => point.minute
                ),
                y: (timeline.dropoff || []).map(
                    point => point.retention
                ),
                line: {
                    color: PALETTE.purpleDeep,
                    width: 2,
                    dash: "dot"
                },
                hovertemplate:
                    "Minute %{x}<br>Retention: %{y}%<extra></extra>"
            }
        ],
        baseLayout({
            height: 330,
            xaxis: {
                title: {
                    text: "Minutes since session start",
                    font: PLOT_FONT
                },
                gridcolor: PALETTE.border
            },
            yaxis: {
                title: { text: "Students inside", font: PLOT_FONT },
                gridcolor: PALETTE.border,
                rangemode: "tozero"
            },
            yaxis2: {
                title: { text: "% of peak", font: PLOT_FONT },
                overlaying: "y",
                side: "right",
                range: [0, 105],
                showgrid: false
            },
            legend: { orientation: "h", y: -0.3 }
        }),
        PLOT_CONFIG
    );
}


function renderBands(timeline) {

    const bands = timeline.bands || [];

    if (!bands.length) {

        emptyPlot(
            "bands-chart",
            "No presence intervals recorded for this session."
        );

        return;
    }

    const traces = [];

    bands.forEach((band, index) => {

        band.intervals.forEach((interval, intervalIndex) => {

            traces.push({
                type: "bar",
                orientation: "h",
                name: shortName(band.full_name),
                y: [shortName(band.full_name)],
                x: [
                    Math.max(
                        0.2,
                        interval.end_minute - interval.start_minute
                    )
                ],
                base: [interval.start_minute],
                marker: {
                    color:
                        index % 2 === 0
                            ? PALETTE.blue
                            : PALETTE.purple,
                    line: { width: 0 }
                },
                showlegend: false,
                hovertemplate:
                    `${escapeHtml(band.full_name)}<br>` +
                    `${interval.start_clock} → ` +
                    `${interval.end_clock}<extra></extra>`,
                customdata: [intervalIndex]
            });
        });
    });

    Plotly.newPlot(
        "bands-chart",
        traces,
        baseLayout({
            height: Math.max(300, bands.length * 30 + 120),
            barmode: "overlay",
            margin: { l: 170, r: 24, t: 14, b: 60 },
            xaxis: {
                title: {
                    text: "Minutes since session start",
                    font: PLOT_FONT
                },
                gridcolor: PALETTE.border,
                rangemode: "tozero"
            },
            yaxis: { automargin: true }
        }),
        PLOT_CONFIG
    );
}


// ============================================================
// ML - CLUSTERS
// ============================================================

async function loadClusters() {

    const select = element("cluster-select");

    const k = select ? Number(select.value) : 3;

    const clusters = await getJson(
        `/api/analytics/clusters?${scopeQuery(currentScope)}&k=${k}`
    );

    currentClusters = clusters;

    renderClusters(clusters);

    return clusters;
}


function renderClusters(clusters) {

    const note = element("cluster-note");

    const cards = element("cluster-cards");

    if (!clusters.trained) {

        emptyPlot("cluster-chart", clusters.reason || "");

        if (cards) {
            cards.innerHTML = "";
        }

        if (note) {
            note.textContent = clusters.reason || "";
        }

        return;
    }

    const colorByCluster = {};

    clusters.clusters.forEach(cluster => {
        colorByCluster[cluster.cluster] = cluster.color;
    });

    const traces = clusters.clusters.map(cluster => {

        const members = clusters.assignments.filter(
            student => student.cluster === cluster.cluster
        );

        return {
            type: "scatter",
            mode: "markers",
            name: `${cluster.label} (${cluster.size})`,
            x: members.map(student => student.average_attendance),
            y: members.map(student => student.consistency),
            text: members.map(student => student.full_name),
            marker: {
                size: members.map(
                    student =>
                        12 + Math.min(18, Math.abs(student.trend) * 3)
                ),
                color: cluster.color,
                line: { width: 1.5, color: "#ffffff" },
                opacity: 0.9
            },
            hovertemplate:
                "%{text}<br>Average: %{x}%<br>" +
                "Consistency: %{y}<extra></extra>"
        };
    });

    Plotly.newPlot(
        "cluster-chart",
        traces,
        baseLayout({
            height: 400,
            xaxis: {
                title: {
                    text: "Average attendance (%)",
                    font: PLOT_FONT
                },
                range: [-5, 105],
                gridcolor: PALETTE.border
            },
            yaxis: {
                title: {
                    text: "Consistency (100 = identical every session)",
                    font: PLOT_FONT
                },
                gridcolor: PALETTE.border
            },
            legend: { orientation: "h", y: -0.25 }
        }),
        PLOT_CONFIG
    );

    if (cards) {

        cards.innerHTML = clusters.clusters
            .map(
                cluster => `
                    <article
                        class="cluster-card"
                        style="border-left-color:${cluster.color}"
                    >
                        <h4>${escapeHtml(cluster.label)}</h4>
                        <p>${escapeHtml(cluster.description)}</p>
                        <span>
                            ${cluster.size} students ·
                            avg ${cluster.average_attendance}% ·
                            trend ${cluster.average_trend} pts/session
                        </span>
                    </article>
                `
            )
            .join("");
    }

    if (note) {

        note.innerHTML =
            `<strong>Model:</strong> ${escapeHtml(clusters.algorithm)} · ` +
            `k = ${clusters.k} · ` +
            `silhouette = ${clusters.silhouette} ` +
            `(1 = perfectly separated, 0 = overlapping) · ` +
            `features: ${clusters.features.join(", ")}. ` +
            `Bubble size grows with the magnitude of the trend.`;
    }
}


// ============================================================
// ML - RISK
// ============================================================

async function loadRisk() {

    const risk = await getJson(
        `/api/analytics/risk?${scopeQuery(currentScope)}`
    );

    renderRisk(risk);
}


function renderRisk(risk) {

    const body = element("risk-table-body");

    const note = element("risk-note");

    if (body) {

        body.innerHTML = (risk.predictions || [])
            .map(student => {

                const level = String(student.risk).toLowerCase();

                const percentage = Math.round(
                    student.probability * 100
                );

                return `
                    <tr>
                        <td>${escapeHtml(student.full_name)}</td>
                        <td>${escapeHtml(student.student_code)}</td>
                        <td>${student.average_attendance}%</td>
                        <td>
                            ${
                                student.last_attendance === undefined
                                    ? "—"
                                    : `${student.last_attendance}%`
                            }
                        </td>
                        <td>${student.trend}</td>
                        <td>
                            <span class="tag tag-${level}">
                                ${escapeHtml(student.risk)}
                            </span>
                        </td>
                        <td>
                            <div class="risk-bar risk-${level}">
                                <i style="width:${percentage}%"></i>
                            </div>
                            <small>${percentage}%</small>
                        </td>
                    </tr>
                `;
            })
            .join("");
    }

    if (!note) {
        return;
    }

    if (!risk.trained) {

        note.innerHTML =
            `<strong>Model not trained.</strong> ` +
            escapeHtml(risk.reason || "");

        return;
    }

    const metrics = risk.metrics || {};

    note.innerHTML =
        `<strong>Model:</strong> ${escapeHtml(risk.algorithm)} · ` +
        `target: ${escapeHtml(risk.target)} · ` +
        `${risk.training_samples} training samples. ` +
        `<strong>Hold-out (last session):</strong> ` +
        `accuracy ${metrics.accuracy ?? "—"}, ` +
        `precision ${metrics.precision ?? "—"}, ` +
        `recall ${metrics.recall ?? "—"}, ` +
        `F1 ${metrics.f1 ?? "—"} over ${metrics.samples ?? 0} samples. ` +
        `The split is chronological, never random, so the model is ` +
        `never trained on the session it is evaluated against.`;
}


// ============================================================
// STUDENT TABLE
// ============================================================

function renderStudents(course, clusters) {

    const body = element("students-table-body");

    if (!body) {
        return;
    }

    const profileById = {};

    if (clusters && clusters.trained) {

        const labelByCluster = {};

        clusters.clusters.forEach(cluster => {
            labelByCluster[cluster.cluster] = cluster;
        });

        clusters.assignments.forEach(student => {

            profileById[student.id] =
                labelByCluster[student.cluster] || null;
        });
    }

    body.innerHTML = (course.students || [])
        .slice()
        .sort(
            (first, second) =>
                first.average_attendance - second.average_attendance
        )
        .map(student => {

            const profile = profileById[student.id];

            const badge = profile
                ? `<span
                       class="tag"
                       style="background:${profile.color}33;color:${profile.color}"
                   >${escapeHtml(profile.label)}</span>`
                : "—";

            return `
                <tr>
                    <td>${escapeHtml(student.full_name)}</td>
                    <td>${escapeHtml(student.student_code)}</td>
                    <td>${student.average_attendance}%</td>
                    <td>${student.consistency}</td>
                    <td>${student.trend}</td>
                    <td>${student.sessions_attended}</td>
                    <td>${student.sessions_missed}</td>
                    <td>${badge}</td>
                </tr>
            `;
        })
        .join("");
}


// ============================================================
// REFRESH
// ============================================================

async function refresh() {

    if (!currentScope) {
        return;
    }

    try {

        currentCourse = await getJson(
            `/api/analytics/course?${scopeQuery(currentScope)}`
        );

        updateMetrics(currentCourse);

        renderHeatmap(currentCourse);

        renderTrend(currentCourse);

        populateSessionSelect(currentCourse);

        const clusters = await loadClusters();

        renderStudents(currentCourse, clusters);

        await loadRisk();

    } catch (error) {

        console.error("Analytics error:", error);
    }
}


// ============================================================
// INITIALIZE
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        const clusterSelect = element("cluster-select");

        if (clusterSelect) {

            clusterSelect.addEventListener(
                "change",
                async () => {

                    const clusters = await loadClusters();

                    if (currentCourse) {
                        renderStudents(currentCourse, clusters);
                    }
                }
            );
        }

        await loadScopes();

        await refresh();
    }
);
