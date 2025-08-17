#!/usr/bin/env python3
"""
Test script to check imports step by step
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_import(module_name, import_func):
    """Test importing a specific module"""
    try:
        print(f"Testing import: {module_name}")
        result = import_func()
        print(f"✅ {module_name} imported successfully")
        return True
    except Exception as e:
        print(f"❌ {module_name} import failed: {e}")
        return False

def main():
    """Test imports step by step"""
    print("Testing imports step by step...\n")
    
    # Test 1: Basic FastAPI imports
    test_import("FastAPI", lambda: __import__("fastapi"))
    test_import("Uvicorn", lambda: __import__("uvicorn"))
    
    # Test 2: Core config
    test_import("Core config", lambda: __import__("core.config"))
    
    # Test 3: Core modules one by one
    test_import("Core db", lambda: __import__("core.db"))
    test_import("Core Security", lambda: __import__("core.Security"))
    test_import("Core sms", lambda: __import__("core.sms"))
    test_import("Core token", lambda: __import__("core.token"))
    test_import("Core sanitize_validate", lambda: __import__("core.sanitize_validate"))
    test_import("Core status", lambda: __import__("core.status"))
    test_import("Core pico", lambda: __import__("core.pico"))
    test_import("Core esp32cam", lambda: __import__("core.esp32cam"))
    test_import("Core OTP", lambda: __import__("core.OTP"))
    test_import("Core google_auth", lambda: __import__("core.google_auth"))
    test_import("Core login_fun", lambda: __import__("core.login_fun"))
    test_import("Core websocket_manager", lambda: __import__("core.websocket_manager"))
    test_import("Core utils", lambda: __import__("core.utils"))
    test_import("Core system_manager", lambda: __import__("core.system_manager"))
    test_import("Core server_manager", lambda: __import__("core.server_manager"))
    test_import("Core client", lambda: __import__("core.client"))
    test_import("Core error_handler", lambda: __import__("core.error_handler"))
    test_import("Core memory_manager", lambda: __import__("core.memory_manager"))
    
    # Test 4: Tools modules
    test_import("JalaliFormatter", lambda: __import__("core.tools.jalali_formatter"))
    test_import("DynamicPortManager", lambda: __import__("core.tools.dynamic_port_manager"))
    test_import("Port router", lambda: __import__("core.tools.port_router"))
    
    print("\nAll import tests completed!")

if __name__ == "__main__":
    main() 