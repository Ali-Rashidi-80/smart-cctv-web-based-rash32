from fastapi import APIRouter, HTTPException
from .dynamic_port_manager import DynamicPortManager

port_router = APIRouter()

@port_router.get("/status")
async def get_port_status():
    """Get port router status"""
    return {"status": "Port router active", "message": "Port management system is running"}

@port_router.get("/info")
async def get_port_info():
    """Get port router information"""
    return {
        "name": "Port Router",
        "version": "1.0.0",
        "description": "Dynamic port management for Spy Servo system",
        "status": "active"
    } 