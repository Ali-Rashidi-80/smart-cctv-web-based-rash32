#!/usr/bin/env python3
"""
Simple test script to check server startup
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Testing basic imports...")
    
    # Test basic imports
    import fastapi
    print("✅ FastAPI imported successfully")
    
    import uvicorn
    print("✅ Uvicorn imported successfully")
    
    # Test core imports
    try:
        from core import config
        print("✅ Core config imported successfully")
    except Exception as e:
        print(f"❌ Core config import failed: {e}")
    
    try:
        from core.tools.dynamic_port_manager import DynamicPortManager
        print("✅ DynamicPortManager imported successfully")
    except Exception as e:
        print(f"❌ DynamicPortManager import failed: {e}")
    
    print("\nTesting port manager...")
    try:
        port_manager = DynamicPortManager(start=3000, end=3001, enable_background_logging=False)
        port = port_manager.pick_port()
        print(f"✅ Port manager test successful, picked port: {port}")
        port_manager.release_port()
    except Exception as e:
        print(f"❌ Port manager test failed: {e}")
    
    print("\nAll tests completed!")
    
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc() 