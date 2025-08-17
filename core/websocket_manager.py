"""
WebSocket connection manager for the spy_servo system.
This module provides proper WebSocket connection management, rate limiting, and cleanup.
"""

import asyncio
import logging
import json
import time
from typing import Dict, Set, Optional, Callable, Any
from datetime import datetime, timedelta
from fastapi import WebSocket, WebSocketDisconnect
from .config import MAX_WEBSOCKET_CLIENTS, INACTIVE_CLIENT_TIMEOUT, WEBSOCKET_ERROR_THRESHOLD

# Setup logger
logger = logging.getLogger("websocket_manager")

class WebSocketConnection:
    """Individual WebSocket connection wrapper"""
    
    def __init__(self, websocket: WebSocket, client_id: str, client_type: str = "unknown"):
        self.websocket = websocket
        self.client_id = client_id
        self.client_type = client_type
        self.connected_at = datetime.now()
        self.last_activity = datetime.now()
        self.message_count = 0
        self.error_count = 0
        self.is_active = True
        
    async def send_message(self, message: Any) -> bool:
        """Send message to client with error handling"""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message)
            elif not isinstance(message, str):
                message = str(message)
            
            await self.websocket.send_text(message)
            self.last_activity = datetime.now()
            self.message_count += 1
            return True
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Error sending message to {self.client_id}: {e}")
            return False
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()
    
    def is_inactive(self, timeout_seconds: int) -> bool:
        """Check if connection is inactive"""
        return (datetime.now() - self.last_activity).total_seconds() > timeout_seconds
    
    def has_too_many_errors(self, threshold: int) -> bool:
        """Check if connection has too many errors"""
        return self.error_count >= threshold
    
    async def close(self, reason: str = "normal"):
        """Close the WebSocket connection"""
        try:
            self.is_active = False
            await self.websocket.close(code=1000, reason=reason)
            logger.info(f"WebSocket connection {self.client_id} closed: {reason}")
        except Exception as e:
            logger.error(f"Error closing WebSocket {self.client_id}: {e}")

class WebSocketManager:
    """WebSocket connection manager with rate limiting and cleanup"""
    
    def __init__(self):
        self.connections: Dict[str, WebSocketConnection] = {}
        self.connection_types: Dict[str, Set[str]] = {}
        self.rate_limits: Dict[str, Dict] = {}
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Initialize connection type tracking
        for client_type in ["pico", "esp32cam", "web", "mobile"]:
            self.connection_types[client_type] = set()
    
    async def start(self):
        """Start the WebSocket manager"""
        if self.is_running:
            logger.warning("WebSocket manager already running")
            return
        
        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("WebSocket manager started")
    
    async def stop(self):
        """Stop the WebSocket manager and close all connections"""
        self.is_running = False
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        close_tasks = []
        for connection in self.connections.values():
            close_tasks.append(connection.close("manager_shutdown"))
        
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        
        logger.info("WebSocket manager stopped")
    
    async def connect(self, websocket: WebSocket, client_id: str, 
                     client_type: str = "unknown") -> bool:
        """Accept new WebSocket connection"""
        try:
            # Check connection limits
            if len(self.connections) >= MAX_WEBSOCKET_CLIENTS:
                logger.warning(f"Maximum WebSocket connections reached ({MAX_WEBSOCKET_CLIENTS})")
                await websocket.close(code=1013, reason="Too many connections")
                return False
            
            # Accept the connection
            await websocket.accept()
            
            # Create connection wrapper
            connection = WebSocketConnection(websocket, client_id, client_type)
            self.connections[client_id] = connection
            
            # Track by type
            if client_type not in self.connection_types:
                self.connection_types[client_type] = set()
            self.connection_types[client_type].add(client_id)
            
            # Initialize rate limiting
            self.rate_limits[client_id] = {
                "message_count": 0,
                "last_reset": time.time(),
                "window_size": 60  # 1 minute window
            }
            
            logger.info(f"WebSocket connected: {client_id} ({client_type}) - Total: {len(self.connections)}")
            return True
            
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection {client_id}: {e}")
            return False
    
    async def disconnect(self, client_id: str, reason: str = "normal"):
        """Disconnect a WebSocket connection"""
        if client_id in self.connections:
            connection = self.connections[client_id]
            
            # Remove from type tracking
            if connection.client_type in self.connection_types:
                self.connection_types[connection.client_type].discard(client_id)
            
            # Close connection
            await connection.close(reason)
            
            # Clean up
            del self.connections[client_id]
            if client_id in self.rate_limits:
                del self.rate_limits[client_id]
            
            logger.info(f"WebSocket disconnected: {client_id} - Total: {len(self.connections)}")
    
    async def broadcast(self, message: Any, client_type: Optional[str] = None, 
                       exclude_client: Optional[str] = None):
        """Broadcast message to all connections or specific type"""
        if not self.connections:
            return
        
        target_connections = []
        
        if client_type:
            # Send to specific client type
            if client_type in self.connection_types:
                for client_id in self.connection_types[client_type]:
                    if client_id in self.connections and client_id != exclude_client:
                        target_connections.append(self.connections[client_id])
        else:
            # Send to all connections
            for connection in self.connections.values():
                if connection.client_id != exclude_client:
                    target_connections.append(connection)
        
        # Send messages concurrently
        if target_connections:
            send_tasks = [conn.send_message(message) for conn in target_connections]
            results = await asyncio.gather(*send_tasks, return_exceptions=True)
            
            success_count = sum(1 for result in results if result is True)
            logger.debug(f"Broadcast sent to {success_count}/{len(target_connections)} connections")
    
    async def send_to_client(self, client_id: str, message: Any) -> bool:
        """Send message to specific client"""
        if client_id in self.connections:
            connection = self.connections[client_id]
            return await connection.send_message(message)
        return False
    
    def check_rate_limit(self, client_id: str, max_messages: int = 100) -> bool:
        """Check if client has exceeded rate limit"""
        if client_id not in self.rate_limits:
            return True
        
        rate_limit = self.rate_limits[client_id]
        current_time = time.time()
        
        # Reset counter if window has passed
        if current_time - rate_limit["last_reset"] > rate_limit["window_size"]:
            rate_limit["message_count"] = 0
            rate_limit["last_reset"] = current_time
        
        # Check limit
        if rate_limit["message_count"] >= max_messages:
            logger.warning(f"Rate limit exceeded for client {client_id}")
            return False
        
        rate_limit["message_count"] += 1
        return True
    
    async def _cleanup_loop(self):
        """Background cleanup loop for inactive connections"""
        while self.is_running:
            try:
                await self._cleanup_inactive_connections()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(5)
    
    async def _cleanup_inactive_connections(self):
        """Clean up inactive and problematic connections"""
        current_time = datetime.now()
        to_disconnect = []
        
        for client_id, connection in self.connections.items():
            # Check for inactive connections
            if connection.is_inactive(INACTIVE_CLIENT_TIMEOUT):
                to_disconnect.append((client_id, "inactive"))
                continue
            
            # Check for connections with too many errors
            if connection.has_too_many_errors(WEBSOCKET_ERROR_THRESHOLD):
                to_disconnect.append((client_id, "too_many_errors"))
                continue
        
        # Disconnect problematic connections
        for client_id, reason in to_disconnect:
            await self.disconnect(client_id, reason)
        
        if to_disconnect:
            logger.info(f"Cleaned up {len(to_disconnect)} inactive/error-prone connections")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics"""
        stats = {
            "total_connections": len(self.connections),
            "connections_by_type": {},
            "rate_limited_clients": 0,
            "timestamp": datetime.now().isoformat()
        }
        
        # Count connections by type
        for client_type, client_ids in self.connection_types.items():
            stats["connections_by_type"][client_type] = len(client_ids)
        
        # Count rate-limited clients
        for client_id, rate_limit in self.rate_limits.items():
            if rate_limit["message_count"] >= rate_limit.get("max_messages", 100):
                stats["rate_limited_clients"] += 1
        
        return stats
    
    def get_connection_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific connection"""
        if client_id not in self.connections:
            return None
        
        connection = self.connections[client_id]
        return {
            "client_id": connection.client_id,
            "client_type": connection.client_type,
            "connected_at": connection.connected_at.isoformat(),
            "last_activity": connection.last_activity.isoformat(),
            "message_count": connection.message_count,
            "error_count": connection.error_count,
            "is_active": connection.is_active
        }

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

# Decorator for WebSocket operations
def websocket_operation(operation_type: str = "general"):
    """Decorator for WebSocket operations with automatic error handling"""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected during {operation_type}")
                raise
            except Exception as e:
                logger.error(f"Error in WebSocket {operation_type}: {e}")
                raise
        return wrapper
    return decorator 