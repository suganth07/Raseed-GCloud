from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# Create FastAPI app
app = FastAPI(
    title="Raseed Backend API",
    description="AI-powered receipt processing and expense management system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Starting Raseed Backend API")
    logger.info(f"Environment: {'development' if settings.debug else 'production'}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Shutting down Raseed Backend API")


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
    return {
        "status": "healthy",
        "timestamp": "2025-01-18T00:00:00Z"
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info"
    )