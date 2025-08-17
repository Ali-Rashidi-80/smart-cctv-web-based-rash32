"""
Memory management module for the spy_servo system.
This module provides memory monitoring, cleanup, and optimization utilities.
"""

import gc
import psutil
import logging
import asyncio
import tracemalloc
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# Setup logger
logger = logging.getLogger("memory_manager")

class MemoryManager:
    """Memory management and monitoring system"""
    
    def __init__(self):
        import os
        self.memory_threshold = int(os.getenv("MEMORY_THRESHOLD", "85"))  # Percentage
        self.cleanup_threshold = int(os.getenv("MEMORY_CLEANUP_THRESHOLD", "70"))  # Percentage
        self.monitoring_interval = int(os.getenv("MEMORY_MONITORING_INTERVAL", "30"))  # seconds
        self.cleanup_callbacks: List[Callable] = []
        self.memory_history: List[Dict] = []
        self.max_history_size = int(os.getenv("MEMORY_HISTORY_SIZE", "100"))
        self.is_monitoring = False
        
        # Initialize tracemalloc for detailed memory tracking
        try:
            tracemalloc.start()
            logger.info("Memory tracking initialized with tracemalloc")
        except Exception as e:
            logger.warning(f"Could not initialize tracemalloc: {e}")
    
    def add_cleanup_callback(self, callback: Callable):
        """Add a callback function to be called during memory cleanup"""
        self.cleanup_callbacks.append(callback)
        logger.debug(f"Added memory cleanup callback: {callback.__name__}")
    
    async def start_monitoring(self):
        """Start memory monitoring in background"""
        if self.is_monitoring:
            logger.warning("Memory monitoring already running")
            return
        
        self.is_monitoring = True
        logger.info("Starting memory monitoring")
        
        while self.is_monitoring:
            try:
                await self._check_memory_usage()
                await asyncio.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")
                await asyncio.sleep(5)  # Short delay on error
    
    def stop_monitoring(self):
        """Stop memory monitoring"""
        self.is_monitoring = False
        logger.info("Memory monitoring stopped")
    
    async def _check_memory_usage(self):
        """Check current memory usage and trigger cleanup if needed"""
        try:
            memory_percent = psutil.virtual_memory().percent
            memory_used = psutil.virtual_memory().used / (1024**3)  # GB
            memory_available = psutil.virtual_memory().available / (1024**3)  # GB
            
            # Record memory usage
            self._record_memory_usage(memory_percent, memory_used, memory_available)
            
            # Check if cleanup is needed
            if memory_percent > self.memory_threshold:
                logger.warning(f"Memory usage high: {memory_percent:.1f}%")
                await self._trigger_emergency_cleanup()
            elif memory_percent > self.cleanup_threshold:
                logger.info(f"Memory usage elevated: {memory_percent:.1f}%, triggering cleanup")
                await self._trigger_cleanup()
            
            # Log memory status
            if memory_percent > 90:
                logger.critical(f"CRITICAL: Memory usage at {memory_percent:.1f}%")
            
        except Exception as e:
            logger.error(f"Error checking memory usage: {e}")
    
    def _record_memory_usage(self, percent: float, used_gb: float, available_gb: float):
        """Record memory usage for trend analysis"""
        record = {
            "timestamp": datetime.now(),
            "percent": percent,
            "used_gb": used_gb,
            "available_gb": available_gb
        }
        
        self.memory_history.append(record)
        
        # Keep only recent history
        if len(self.memory_history) > self.max_history_size:
            self.memory_history.pop(0)
    
    async def _trigger_cleanup(self):
        """Trigger normal memory cleanup"""
        logger.info("Starting memory cleanup")
        
        # Run cleanup callbacks
        for callback in self.cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"Error in cleanup callback {callback.__name__}: {e}")
        
        # Force garbage collection
        collected = gc.collect()
        logger.info(f"Garbage collection completed, collected {collected} objects")
        
        # Log memory status after cleanup
        try:
            memory_percent = psutil.virtual_memory().percent
            logger.info(f"Memory usage after cleanup: {memory_percent:.1f}%")
        except Exception as e:
            logger.error(f"Error checking memory after cleanup: {e}")
    
    async def _trigger_emergency_cleanup(self):
        """Trigger emergency memory cleanup"""
        logger.critical("EMERGENCY: Triggering emergency memory cleanup")
        
        # Force multiple garbage collection cycles
        for i in range(3):
            collected = gc.collect()
            logger.info(f"Emergency GC cycle {i+1}: collected {collected} objects")
            await asyncio.sleep(0.1)
        
        # Run cleanup callbacks with higher priority
        for callback in self.cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"Error in emergency cleanup callback {callback.__name__}: {e}")
        
        # Check if cleanup helped
        try:
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > 95:
                logger.critical(f"EMERGENCY: Memory still critical after cleanup: {memory_percent:.1f}%")
                # TODO: Implement more aggressive measures (restart services, etc.)
            else:
                logger.info(f"Emergency cleanup completed, memory: {memory_percent:.1f}%")
        except Exception as e:
            logger.error(f"Error checking memory after emergency cleanup: {e}")
    
    def get_memory_stats(self) -> Dict:
        """Get current memory statistics"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_gb": vm.total / (1024**3),
                "available_gb": vm.available / (1024**3),
                "used_gb": vm.used / (1024**3),
                "percent": vm.percent,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {"error": str(e)}
    
    def get_memory_trend(self, hours: int = 1) -> List[Dict]:
        """Get memory usage trend over specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            record for record in self.memory_history 
            if record["timestamp"] > cutoff_time
        ]
    
    @asynccontextmanager
    async def memory_context(self, context_name: str):
        """Context manager for tracking memory usage in specific contexts"""
        start_memory = self._get_current_memory()
        start_time = datetime.now()
        
        try:
            yield
        finally:
            end_memory = self._get_current_memory()
            end_time = datetime.now()
            
            memory_diff = end_memory - start_memory
            duration = (end_time - start_time).total_seconds()
            
            if memory_diff > 0:
                logger.debug(f"[{context_name}] Memory increased by {memory_diff:.2f} MB over {duration:.2f}s")
            elif memory_diff < 0:
                logger.debug(f"[{context_name}] Memory decreased by {abs(memory_diff):.2f} MB over {duration:.2f}s")
    
    def _get_current_memory(self) -> float:
        """Get current memory usage in MB"""
        try:
            return psutil.Process().memory_info().rss / (1024**2)
        except Exception:
            return 0.0
    
    def optimize_memory(self):
        """Apply memory optimization techniques"""
        logger.info("Applying memory optimizations")
        
        # Clear memory history if too large
        if len(self.memory_history) > self.max_history_size * 2:
            self.memory_history = self.memory_history[-self.max_history_size:]
            logger.info("Cleared excess memory history")
        
        # Force garbage collection
        collected = gc.collect()
        logger.info(f"Memory optimization completed, collected {collected} objects")
        
        return collected

# Global memory manager instance
memory_manager = MemoryManager()

# Decorator for memory monitoring
def monitor_memory(context: str = "general"):
    """Decorator for monitoring memory usage in functions"""
    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            async with memory_manager.memory_context(f"{context}:{func.__name__}"):
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            with memory_manager.memory_context(f"{context}:{func.__name__}"):
                return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator 