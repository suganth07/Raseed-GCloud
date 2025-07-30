from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from .utils.config import settings
from .utils.logging import configure_logging, get_logger
from .api.simple_routes import router as api_router
from .api.graph_routes import router as graph_router
from .api.ui_routes import router as ui_router
from .api.wallet_routes import router as wallet_router
from .api.warranty_reminder_routes import router as warranty_reminder_router
from .api.economix_bot_routes import router as economix_router
from .api.middleware import setup_middleware

# Configure logging
configure_logging(debug=settings.debug)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Raseed Backend API")
    logger.info(f"Environment: {'development' if settings.debug else 'production'}")
    yield
    # Shutdown
    logger.info("Shutting down Raseed Backend API")


# Create FastAPI app
app = FastAPI(
    title="Raseed Backend API",
    description="AI-powered receipt processing and expense management system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Setup middleware
setup_middleware(app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)
app.include_router(graph_router)
app.include_router(ui_router)
app.include_router(wallet_router)
app.include_router(warranty_reminder_router)
app.include_router(economix_router)


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {
        "message": "Raseed Backend API",
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    import datetime
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "service": "raseed-backend"
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint for Cloud Run."""
    return {"status": "ready", "service": "raseed-backend"}


if __name__ == "__main__":
    # This only runs when the script is executed directly, not when imported by gunicorn
    import os
    try:
        # Get port from environment variable (Cloud Run sets this automatically)
        port = 8080
        debug = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")
        logger.info(f"Starting development server on port {port}")
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=port,
            reload=debug,
            log_level="debug" if debug else "info"
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise