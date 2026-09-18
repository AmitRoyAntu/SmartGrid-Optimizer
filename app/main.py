"""
Application Entrypoint & HTTP Routing (Member 1).

Exposes:
- GET /health: Instant liveness check returning {"status": "ok"}
- POST /optimize-energy: Full campus microgrid energy scheduling endpoint
- Global error handling: Clean JSON responses with strict secret sanitization
"""

import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.schemas import OptimizeEnergyRequest, OptimizeEnergyResponse
from app.core.orchestrator import orchestrate

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gridwise")

app = FastAPI(
    title="GridWise LLM Smart Campus Energy Optimizer",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

# Enable CORS for frontend / judge visualization
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle schema validation errors cleanly without exposing internals.
    """
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Invalid field")
        errors.append(f"{loc}: {msg}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed",
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler to ensure no secrets or stack traces leak.
    """
    logger.error("Unhandled error processing %s: %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal error occurred during optimization processing.",
        },
    )


@app.get("/health", status_code=status.HTTP_200_OK)
async def health():
    """
    Liveness and readiness health check endpoint.
    Must respond immediately with {"status": "ok"}.
    """
    return {"status": "ok"}


@app.post(
    "/optimize-energy",
    response_model=OptimizeEnergyResponse,
    status_code=status.HTTP_200_OK,
)
async def optimize_energy(request: OptimizeEnergyRequest):
    """
    Core campus energy optimization endpoint.
    Accepts scenario with operator notes, hourly generation/demand/tariffs, and battery specs.
    Returns optimal 24-hour schedule, validated directive interpretations, and costs.
    """
    return await orchestrate(request)