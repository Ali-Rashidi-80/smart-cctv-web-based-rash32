"""
Centralized error handling module for the spy_servo system.
This module provides consistent error handling and logging across all components.
"""

import logging
import traceback
import asyncio
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

# Setup logger
logger = logging.getLogger("error_handler")

class ErrorHandler:
    """Centralized error handler for consistent error management"""
    
    def __init__(self):
        self.error_counts = {}
        self.error_thresholds = {
            'database': 5,
            'websocket': 10,
            'authentication': 3,
            'file_upload': 5,
            'general': 20
        }
        self.error_reset_interval = 3600  # 1 hour
    
    async def handle_error(self, error: Exception, context: str, 
                          request: Optional[Request] = None, 
                          user_id: Optional[int] = None,
                          severity: str = "medium") -> Dict[str, Any]:
        """Handle errors with consistent logging and response formatting"""
        
        error_type = type(error).__name__
        error_message = str(error)
        timestamp = datetime.now().isoformat()
        
        # Log error details
        log_message = f"[{context}] {error_type}: {error_message}"
        
        if severity == "critical":
            logger.critical(log_message)
        elif severity == "error":
            logger.error(log_message)
        elif severity == "warning":
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        # Track error counts for rate limiting
        await self._track_error(context, error_type)
        
        # Check if we should trigger alerts
        if await self._should_alert(context):
            await self._trigger_alert(context, error_type, error_message, severity)
        
        # Return standardized error response
        return {
            "error": True,
            "type": error_type,
            "message": error_message,
            "context": context,
            "timestamp": timestamp,
            "severity": severity
        }
    
    async def _track_error(self, context: str, error_type: str):
        """Track error counts for monitoring and alerting"""
        key = f"{context}:{error_type}"
        if key not in self.error_counts:
            self.error_counts[key] = {"count": 0, "first_seen": datetime.now()}
        
        self.error_counts[key]["count"] += 1
        self.error_counts[key]["last_seen"] = datetime.now()
    
    async def _should_alert(self, context: str) -> bool:
        """Determine if an alert should be triggered based on error thresholds"""
        for key, count in self.error_counts.items():
            if key.startswith(context) and count["count"] >= self.error_thresholds.get(context, 10):
                return True
        return False
    
    async def _trigger_alert(self, context: str, error_type: str, 
                           error_message: str, severity: str):
        """Trigger appropriate alerts for critical errors"""
        alert_message = f"ALERT: {context} - {error_type} - {error_message} - Severity: {severity}"
        
        if severity == "critical":
            logger.critical(f"🚨 {alert_message}")
            # TODO: Send admin notification, SMS, email, etc.
        elif severity == "error":
            logger.error(f"⚠️ {alert_message}")
    
    def create_http_exception(self, status_code: int, detail: str, 
                            context: str = "general") -> HTTPException:
        """Create HTTP exceptions with consistent error handling"""
        logger.warning(f"[{context}] HTTP {status_code}: {detail}")
        return HTTPException(status_code=status_code, detail=detail)
    
    async def handle_database_error(self, error: Exception, operation: str) -> Dict[str, Any]:
        """Handle database-specific errors"""
        return await self.handle_error(
            error, 
            f"database:{operation}", 
            severity="error"
        )
    
    async def handle_websocket_error(self, error: Exception, connection_id: str) -> Dict[str, Any]:
        """Handle WebSocket-specific errors"""
        return await self.handle_error(
            error, 
            f"websocket:{connection_id}", 
            severity="warning"
        )
    
    async def handle_authentication_error(self, error: Exception, username: str) -> Dict[str, Any]:
        """Handle authentication-specific errors"""
        return await self.handle_error(
            error, 
            f"authentication:{username}", 
            severity="error"
        )
    
    async def handle_file_upload_error(self, error: Exception, filename: str) -> Dict[str, Any]:
        """Handle file upload errors"""
        return await self.handle_error(
            error, 
            f"file_upload:{filename}", 
            severity="warning"
        )
    
    def cleanup_old_errors(self):
        """Clean up old error tracking data"""
        current_time = datetime.now()
        keys_to_remove = []
        
        for key, data in self.error_counts.items():
            if (current_time - data["first_seen"]).total_seconds() > self.error_reset_interval:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.error_counts[key]
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} old error entries")

# Global error handler instance
error_handler = ErrorHandler()

# Decorator for automatic error handling
def handle_errors(context: str = "general", severity: str = "medium"):
    """Decorator for automatic error handling in async functions"""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await error_handler.handle_error(e, context, severity=severity)
                raise
        return wrapper
    return decorator

# Decorator for automatic error handling in sync functions
def handle_errors_sync(context: str = "general", severity: str = "medium"):
    """Decorator for automatic error handling in sync functions"""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # For sync functions, we need to handle errors differently
                logger.error(f"[{context}] {type(e).__name__}: {str(e)}")
                raise
        return wrapper
    return decorator 