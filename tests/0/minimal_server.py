#!/usr/bin/env python3
"""
Minimal version of the main server to test step by step
"""

import os
import sys
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("minimal_server")

def create_minimal_app() -> FastAPI:
    """Create a minimal FastAPI application"""
    app = FastAPI(
        title="Spy Servo System - Minimal",
        description="Minimal version for testing",
        version="1.0.0"
    )
    
    # Add basic middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Basic routes
    @app.get("/")
    async def root():
        return {"message": "Spy Servo System - Minimal Version"}
    
    @app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    @app.get("/test")
    async def test():
        return {"message": "Test endpoint working"}
    
    return app

def main():
    """Main entry point"""
    try:
        logger.info("Creating minimal FastAPI application...")
        app = create_minimal_app()
        logger.info("✅ FastAPI application created successfully")
        
        # Start server
        host = "0.0.0.0"
        port = 3000
        
        logger.info(f"🚀 Starting minimal server on {host}:{port}")
        
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info"
        )
        
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 