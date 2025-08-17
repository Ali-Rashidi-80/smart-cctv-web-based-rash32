#!/usr/bin/env python3
"""
Simple FastAPI Server for Testing
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

# Create FastAPI app
app = FastAPI(title="Spy Servo Simple Server")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint - show login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Simple server is running"}

@app.get("/test")
async def test():
    """Test endpoint"""
    return {"message": "Server is working!", "port": 3000}

if __name__ == "__main__":
    print("🚀 Starting Simple FastAPI Server...")
    print("📍 Server will run on http://127.0.0.1:3000")
    print("🔧 Press Ctrl+C to stop")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=3000,
        log_level="info"
    ) 