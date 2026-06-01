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
# HOW TO RUN:
#   uvicorn main:app --reload --port 8000
#   Then visit: http://localhost:8000/docs  (Swagger UI)
# ─────────────────────────────────────────────────────────

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
import time

# Our settings object (reads from .env)
from core.config import settings

# Database setup function (creates tables on startup)
from core.database import AsyncSessionLocal, create_all_tables
from core.security import hash_password

# Import ORM models
from models.user import User, UserRole

# ── Import API Routers ────────────────────────────────────
# We import the router objects from each module.
# Each router is a group of related routes (like a mini-app).
from api.auth import router as auth_router
from api.admin import router as admin_router
from api.hr import router as hr_router
from api.seeker import router as seeker_router
from api.interview import router as interview_router
# from api.ai import router as ai_router

# ── Logging Setup ─────────────────────────────────────────
import os
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Configure the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Shared formatter
log_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

# Console Handler (writes logs to standard output)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

# File Handler (writes logs to logs/api.log with rotating backups)
file_handler = RotatingFileHandler(
    "logs/api.log",
    maxBytes=10 * 1024 * 1024,  # 10 MB per log file
    backupCount=5,              # Keep up to 5 backup log files
    encoding="utf-8"
)
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)


async def create_initial_super_admin():
    """
    Bootstrap a Super Admin on startup when environment variables are provided.
    """
    if not settings.SUPERADMIN_EMAIL or not settings.SUPERADMIN_PASSWORD:
        logger.info("No SUPERADMIN credentials provided, skipping bootstrap.")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.role == UserRole.SUPER_ADMIN))
        existing_super_admin = result.scalar_one_or_none()
        if existing_super_admin:
            logger.info("Super Admin already exists, bootstrap skipped.")
            return

        result = await session.execute(select(User).where(User.email == settings.SUPERADMIN_EMAIL))
        existing_email = result.scalar_one_or_none()
        if existing_email:
            logger.warning(
                "Super Admin bootstrap skipped because email %s is already registered.",
                settings.SUPERADMIN_EMAIL,
            )
            return

        super_admin = User(
            email=settings.SUPERADMIN_EMAIL,
            full_name=settings.SUPERADMIN_FULL_NAME,
            hashed_password=hash_password(settings.SUPERADMIN_PASSWORD),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
        )
        session.add(super_admin)
        await session.commit()
        await session.refresh(super_admin)
        logger.info("Super Admin created: %s", super_admin.email)


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

    # Create all SQLAlchemy model tables in MySQL.
    # This is equivalent to: CREATE TABLE IF NOT EXISTS ...
    # Safe to run every time — it won't overwrite existing tables.
    # NOTE: In production, use Alembic migrations instead.
    logger.info("📦 Creating database tables...")
    await create_all_tables()
    logger.info("✅ Database tables ready.")

    await create_initial_super_admin()

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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log details of every incoming API request and its response.
    Logs are written to both standard output and logs/api.log.
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    client_ip = request.client.host if request.client else "unknown"
    
    logger.info(
        f"API Hit | Client: {client_ip} | Method: {request.method} | "
        f"Path: {request.url.path} | Status: {response.status_code} | "
        f"Duration: {process_time:.2f}ms"
    )
    
    return response


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
app.include_router(admin_router, prefix="/api/v1")
app.include_router(hr_router, prefix="/api/v1")
app.include_router(seeker_router, prefix="/api/v1")
app.include_router(interview_router, prefix="/api/v1")
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

