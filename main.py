import uuid
import time
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from logging_config import get_logger, setup_logging
from dotenv import load_dotenv
from water_monitor import register_routes

# Load environment variables from .env file
load_dotenv()

setup_logging()
logger = get_logger(__name__)

# Create FastAPI app with documentation settings
app = FastAPI(
    title="Monitor de Agua en tiempo real",
    description="",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

register_routes(app)

# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    logger.info(f"[{request_id}] Request: {request.method} {request.url.path}")

    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            f"[{request_id}] Response: {response.status_code} ({process_time:.4f}s)"
        )
        return response
    except Exception as e:
        logger.error(f"[{request_id}] Error: {str(e)}")
        raise
    
# Exception handler for HTTP exceptions
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.get("/")
async def root():
    return {"message": "Welcome to the Nexus API!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting Nexus API service on {host}:{port}")
    
    # Run the uvicorn server with reload enabled
    uvicorn.run("main:app", host=host, port=port, reload=True)