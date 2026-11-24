from fastapi import FastAPI, Request

from fastapi.responses import HTMLResponse

from fastapi.staticfiles import StaticFiles

from fastapi.templating import Jinja2Templates


from app.api import analytics
from app.api import dashboard
from app.api import session
from app.api import reports

from app.api.intrudenrs import (
    router as intruders_router
)

from app.api.attendance import (
    router as attendance_router
)

from app.api.classes import (
    router as classes_router
)

from app.api.students import (
    router as students_router
)

from app.config import (
    STATIC_DIR,
    TEMPLATES_DIR,
    ensure_directories,
)

from app.database.database import (
    initialize_database
)


# ============================================================
# INITIALIZATION
# ============================================================

ensure_directories()

initialize_database()


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="ClassLY",

    description=(
        "Intelligent attendance system "
        "using facial recognition"
    ),

    version="2.0.0",
)


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory=STATIC_DIR
    ),
    name="static",
)


# ============================================================
# TEMPLATES
# ============================================================

templates = Jinja2Templates(
    directory=TEMPLATES_DIR,
)


# ============================================================
# ROUTERS
# ============================================================

app.include_router(
    students_router
)

app.include_router(
    classes_router
)

app.include_router(
    attendance_router
)

app.include_router(
    dashboard.router
)

app.include_router(
    session.router
)

app.include_router(
    reports.router
)

app.include_router(
    intruders_router
)

app.include_router(
    analytics.router
)


# ============================================================
# WEB PAGE
# ============================================================

# ------------------------------------------------------------
# Stage 1 - During class (professor, live monitoring)
# ------------------------------------------------------------

@app.get(
    "/",
    response_class=HTMLResponse,
)
async def home(
    request: Request
):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )


# ------------------------------------------------------------
# Stage 2 - After class (professor, course analysis)
# ------------------------------------------------------------

@app.get(
    "/analytics",
    response_class=HTMLResponse,
)
async def analytics_page(
    request: Request
):

    return templates.TemplateResponse(
        request=request,
        name="analytics.html",
    )


# ------------------------------------------------------------
# Stage 3 - End of course (coordinator, group assessment)
# ------------------------------------------------------------

@app.get(
    "/coordinator",
    response_class=HTMLResponse,
)
async def coordinator_page(
    request: Request
):

    return templates.TemplateResponse(
        request=request,
        name="coordinator.html",
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
async def health_check():

    return {
        "status": "ok",
        "application": "ClassLY",
        "version": "2.0.0",
    }