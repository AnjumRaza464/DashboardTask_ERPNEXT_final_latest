"""Vercel serverless entry point.

Vercel exposes this file as the ``/api`` function. ``vercel.json`` rewrites every
``/api/*`` request here, and the FastAPI app (which already mounts its routes
under ``/api/...``) handles the original path. The backend package itself lives
in ``backend/app`` and is shared with local development (``uvicorn app.main:app``
run from ``backend/``).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.main import app  # noqa: E402  (Vercel picks up the ASGI `app` object)
