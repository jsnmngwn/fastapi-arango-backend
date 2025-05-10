"""
FastAPI ArangoDB Backend

This module serves as the entry point for the FastAPI backend application with ArangoDB integration.
"""

import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from dotenv import load_dotenv  # Add this import

# Load environment variables from .env file
load_dotenv()  # Add this line

# Configure logger to show debug logs
logger.remove()
logger.configure(handlers=[{"sink": sys.stderr, "level": "DEBUG"}])
logger.debug("Logger configured to show debug messages")

from .db import init_db
from .routes.api_router import create_api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler to initialize the database on startup."""
    try:
        logger.info("Initializing database")
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        # Continue running the app even if database init fails
        # This allows the API to start and the error to be investigated
    yield


# Create FastAPI app
app = FastAPI(
    title="FastAPI ArangoDB API",
    description="Backend API for general purpose applications using FastAPI and ArangoDB",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development. In production, specify domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint that confirms the API is running."""
    return {"message": "FastAPI ArangoDB API is running", "status": "ok"}


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}


# Include API router with all routes
app.include_router(create_api_router())


def start():
    """Start the FastAPI application with Uvicorn server."""
    port = int(os.environ.get("API_PORT", 8000))
    logger.info(f"Starting FastAPI ArangoDB backend service on port {port}")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    start()
