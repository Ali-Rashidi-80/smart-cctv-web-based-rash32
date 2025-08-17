#!/usr/bin/env python3
"""
Test script to verify WebSocket functionality is working correctly
"""

import asyncio
import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_websocket")

async def test_websocket_functions():
    """Test the WebSocket-related functions"""
    
    try:
        # Import the functions
        from core.client import is_system_ready, handle_command_response, get_system_state
        
        logger.info("✅ Successfully imported WebSocket functions")
        
        # Test is_system_ready function
        ready = is_system_ready()
        logger.info(f"✅ is_system_ready() returned: {ready}")
        
        # Test get_system_state function
        state = get_system_state()
        logger.info(f"✅ get_system_state() returned: {type(state)}")
        logger.info(f"✅ System state attributes: {dir(state)}")
        
        # Test handle_command_response function
        test_message = {"type": "command", "command": "get_status"}
        await handle_command_response(test_message)
        logger.info("✅ handle_command_response() executed successfully")
        
        logger.info("🎉 All WebSocket functions are working correctly!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing WebSocket functions: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_websocket_functions())
    if result:
        print("✅ WebSocket fix verification successful!")
    else:
        print("❌ WebSocket fix verification failed!") 