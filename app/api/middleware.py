from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid
from typing import Callable

from ..utils.logging import get_logger

logger = get_logger(__name__)


def setup_middleware(app: FastAPI):
    """Setup all middleware for the FastAPI application."""
    
    # Request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next: Callable):
        """Add request ID to all requests for tracing."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    
    # Logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable):
        """Log all incoming requests."""
        start_time = time.time()
        
        # Log request
        logger.info(
            "Request started",
            method=request.method,
            url=str(request.url),
            request_id=getattr(request.state, 'request_id', None),
            client_ip=request.client.host if request.client else None
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response
        logger.info(
            "Request completed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time=round(process_time, 4),
            request_id=getattr(request.state, 'request_id', None)
        )
        
        response.headers["X-Process-Time"] = str(process_time)
        return response
    
    # Error handling middleware
    @app.middleware("http")
    async def handle_errors(request: Request, call_next: Callable):
        """Global error handling middleware."""
        try:
            response = await call_next(request)
            return response
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            # Log unexpected errors
            logger.error(
                "Unexpected error",
                error=str(e),
                error_type=type(e).__name__,
                request_id=getattr(request.state, 'request_id', None),
                method=request.method,
                url=str(request.url)
            )
            
            # Return generic error response
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": getattr(request.state, 'request_id', None)
                }
            )
    
    # Rate limiting middleware (basic implementation)
    @app.middleware("http")
    async def rate_limit(request: Request, call_next: Callable):
        """Basic rate limiting middleware."""
        # This is a simple implementation - in production, use Redis or similar
        client_ip = request.client.host if request.client else "unknown"
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/redoc"]:
            return await call_next(request)
        
        # In a real implementation, you would check against a rate limit store
        # For now, just pass through
        return await call_next(request)
    
    logger.info("Middleware setup completed")