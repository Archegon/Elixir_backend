"""
Elixir Backend - Main FastAPI Application

This is the main entry point for the Elixir Backend API server
that interfaces with the S7-200 PLC system.
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import time
import os
from dotenv import load_dotenv

# Import our routes
from api.routes import router as api_router
from modules.logger import setup_logger, ContextLogger

# Load environment variables
load_dotenv()

# Initialize logger
logger = setup_logger("main")

# Create FastAPI app
app = FastAPI(
    title="Elixir Backend API",
    description="API for S7-200 PLC Integration with Elixir Hyperbaric Chamber System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS middleware - configure based on your frontend needs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    with ContextLogger(logger, 
                      operation="HTTP_REQUEST", 
                      method=request.method, 
                      path=request.url.path,
                      client=request.client.host if request.client else "unknown"):
        response = await call_next(request)
        
        process_time = time.time() - start_time
        logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
        
        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response

# Include API routes
app.include_router(api_router, prefix="", tags=["api"])

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Elixir Backend API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "authentication": "/api/auth/*",
            "language": "/api/language/*",
            "control": "/api/control/*",
            "pressure": "/api/pressure/*",
            "session": "/api/session/*",
            "modes": "/api/modes/*",
            "ac": "/api/ac/*",
            "sensors": "/api/sensors/*",
            "calibration": "/api/calibration/*",
            "manual": "/api/manual/*",
            "status": "/api/status/*",
            "websockets": "/ws/*"
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # You could add PLC connectivity check here
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "service": "elixir-backend"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time(),
                "service": "elixir-backend"
            }
        )

# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception in {request.method} {request.url.path}: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error": str(exc) if os.getenv("DEBUG", "false").lower() == "true" else "Internal error"
        }
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info("Starting Elixir Backend API server")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"PLC IP: {os.getenv('PLC_IP', 'not configured')}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info("Shutting down Elixir Backend API server")
    
    # Clean up PLC connections if needed
    try:
        from api.routes import plc_instance
        if plc_instance:
            plc_instance.disconnect()
            logger.info("PLC connection closed")
    except Exception as e:
        logger.error(f"Error during PLC cleanup: {e}")

if __name__ == "__main__":
    # Development server
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting development server on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )
