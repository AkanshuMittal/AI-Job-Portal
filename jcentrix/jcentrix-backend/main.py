# ─────────────────────────────────────────────────────────
# main.py — FastAPI Application Entry Point
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   This is the ROOT file of the entire backend.
#   It does 4 critical things:
#   1. Creates the FastAPI application instance
#   2. Configures CORS (Cross-Origin Resource Sharing)
#      so the Next.js frontend can call our API
#   3. Registers all API routers (auth, hr, admin, seeker, ai)
#   4. On startup: creates database tables automatically
#
# HOW TO RUN:
#   uvicorn main:app --reload --port 8000
#   Then visit: http://localhost:8000/docs  (Swagger UI)
# ─────────────────────────────────────────────────────────

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Our settings object (reads from .env)
from core.config import settings

# Database setup function (creates tables on startup)
from core.database import create_all_tables

# ── Import API Routers ────────────────────────────────────
# We import the router objects from each module.
# Each router is a group of related routes (like a mini-app).
from api.auth import router as auth_router
# Phase 2 routers — will be imported as we build them:
# from api.admin import router as admin_router
# from api.hr import router as hr_router
# from api.seeker import router as seeker_router
# from api.ai import router as ai_router

# ── Logging Setup ─────────────────────────────────────────
# Configure Python's built-in logging for debug messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


# ── Lifespan Context Manager ──────────────────────────────
# @asynccontextmanager turns this into a startup/shutdown handler.
# FastAPI runs the code BEFORE `yield` on startup,
# and the code AFTER `yield` on shutdown.
# This replaces the older @app.on_event("startup") pattern.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.
    Startup: Create database tables if they don't exist.
    Shutdown: Log graceful shutdown.
    """
    # ── STARTUP ───────────────────────────────────────────
    logger.info("🚀 Starting Jcentrix AI Job Portal backend...")
    logger.info(f"   Environment : {settings.ENVIRONMENT}")
    logger.info(f"   Database    : {settings.DATABASE_URL}")

    # Create all SQLAlchemy model tables in PostgreSQL.
    # This is equivalent to: CREATE TABLE IF NOT EXISTS ...
    # Safe to run every time — it won't overwrite existing tables.
    # NOTE: In production, use Alembic migrations instead.
    logger.info("📦 Creating database tables...")
    await create_all_tables()
    logger.info("✅ Database tables ready.")

    # Hand control over to FastAPI (app runs here)
    yield

    # ── SHUTDOWN ──────────────────────────────────────────
    logger.info("🛑 Shutting down Jcentrix backend...")


# ── Create FastAPI Application ────────────────────────────
# FastAPI(): Creates the application instance.
# title: Shown in Swagger UI header
# version: API version shown in docs
# description: Markdown description shown in Swagger UI
# lifespan: Registers our startup/shutdown handler above
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="""
    ## Jcentrix AI Job Portal API

    A three-role AI-powered hiring platform.

    ### Roles
    - **Super Admin**: Full platform control
    - **HR Partner**: Manage jobs and candidates
    - **Job Seeker**: Apply for jobs and take AI interviews

    ### AI Features
    - AI Job Description Generator
    - Resume Parser
    - Candidate Matching Engine
    - AI Interview Bot
    - Feedback Generator
    """,
    lifespan=lifespan,
    docs_url="/docs",    # Swagger UI at http://localhost:8000/docs
    redoc_url="/redoc",  # ReDoc UI at http://localhost:8000/redoc
)


# ── CORS Middleware ───────────────────────────────────────
# CORS (Cross-Origin Resource Sharing) controls which
# frontend URLs are allowed to call this API.
# Without this, the browser will BLOCK requests from Next.js
# (localhost:3000) to our API (localhost:8000).
#
# allow_origins: List of allowed frontend URLs
# allow_credentials: Allow cookies and Authorization headers
# allow_methods: Which HTTP methods are allowed (GET, POST, etc.)
# allow_headers: Which request headers are allowed
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],    # Allow all methods
    allow_headers=["*"],    # Allow all headers including Authorization
)


# ── Static File Serving ───────────────────────────────────
# Serves uploaded files (resumes, logos) at /files/...
# e.g., GET /files/resumes/john_doe_cv.pdf
# directory: Where files are stored on disk (./storage)
# name: Internal name for this mount
import os
os.makedirs(settings.STORAGE_PATH, exist_ok=True)  # Create dir if missing
app.mount(
    "/files",
    StaticFiles(directory=settings.STORAGE_PATH),
    name="storage"
)


# ── Register Routers ──────────────────────────────────────
# Each router handles a group of routes.
# We use `include_router()` to add them to the main app.
# prefix="/api/v1": All routes are prefixed with /api/v1
#                   e.g., /auth/login → /api/v1/auth/login
# This versioning allows future API changes without breaking clients.

app.include_router(auth_router, prefix="/api/v1")

# These will be uncommented as we build each phase:
# app.include_router(admin_router, prefix="/api/v1")
# app.include_router(hr_router, prefix="/api/v1")
# app.include_router(seeker_router, prefix="/api/v1")
# app.include_router(ai_router, prefix="/api/v1")


# ── Root Health Check ─────────────────────────────────────
# A simple route to verify the server is running.
# Used by load balancers and monitoring tools.
@app.get("/", tags=["Health"])
async def root():
    """
    Health check endpoint.
    Returns basic server info to confirm the API is live.
    """
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check for monitoring."""
    return {"status": "healthy", "database": "connected"}
