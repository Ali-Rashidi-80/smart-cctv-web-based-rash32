"""
Server management module for the spy_servo system.
This module handles server startup, port management, and server lifecycle operations.
"""

import os
import sys
import time
import socket
import logging
import subprocess
import signal
from typing import Optional, Dict, Any, List
from datetime import datetime

# Setup logger
logger = logging.getLogger("server_manager")

# Global system state reference (will be set by main server)
system_state = None

def set_system_state(state):
    """Set the system state reference from main server"""
    global system_state
    system_state = state

def get_system_state():
    """Safely get system state, creating temporary one if needed"""
    global system_state
    if system_state is None:
        logger.warning("⚠️ system_state not initialized yet, creating temporary state")
        # Create a temporary system state for initialization
        class TempSystemState:
            def __init__(self):
                self.server_processes = {}
                self.port_assignments = {}
                self.server_status = {}
        system_state = TempSystemState()
    return system_state

# Server Management Functions
def kill_existing_server():
    """Kill any existing server processes"""
    try:
        # Find and kill existing Python processes running the server
        if os.name == 'nt':  # Windows
            cmd = f'tasklist /FI "IMAGENAME eq python.exe" /FO CSV'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if 'server_fastapi.py' in result.stdout:
                # Kill processes containing server_fastapi.py
                kill_cmd = f'taskkill /F /IM python.exe /FI "WINDOWTITLE eq *server_fastapi*"'
                subprocess.run(kill_cmd, shell=True)
                logger.info("Killed existing server processes on Windows")
        else:  # Linux/Mac
            # Find processes by name
            cmd = "ps aux | grep 'server_fastapi.py' | grep -v grep"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.stdout.strip():
                # Kill processes
                kill_cmd = "pkill -f 'server_fastapi.py'"
                subprocess.run(kill_cmd, shell=True)
                logger.info("Killed existing server processes on Unix")
                
    except Exception as e:
        logger.error(f"Error killing existing server: {e}")

def pick_unique_port():
    """Pick a unique port for the server"""
    try:
        # Use port 3001 as it's commonly used by other services
        # Skip port 3001 as it's commonly used by other services
        base_port = 3002
        
        # Try ports in sequence
        for port_offset in range(100):
            port = base_port + port_offset
            
            # Check if port is available
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(('localhost', port))
                    if result != 0:  # Port is available
                        logger.info(f"Selected port {port} for server")
                        return port
            except Exception:
                continue
        
        # If no port found, use a random high port
        import random
        random_port = random.randint(8000, 9000)
        logger.warning(f"No available ports found, using random port {random_port}")
        return random_port
        
    except Exception as e:
        logger.error(f"Error picking port: {e}")
        return 3002  # Fallback port

def run_server_on_port(port, service_name):
    """Run server on specified port"""
    try:
        # Build command to run server
        python_cmd = sys.executable
        server_script = "server_fastapi.py"
        
        # Set environment variables
        env = os.environ.copy()
        env['PORT'] = str(port)
        env['SERVICE_NAME'] = service_name
        
        # Build command
        cmd = [python_cmd, server_script]
        
        # Run server process
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Store process info
        get_system_state().server_processes[service_name] = {
            'process': process,
            'port': port,
            'started_at': datetime.now(),
            'pid': process.pid
        }
        
        logger.info(f"Started {service_name} server on port {port} with PID {process.pid}")
        return process
        
    except Exception as e:
        logger.error(f"Error running server on port {port}: {e}")
        return None

def check_port_availability(port: int) -> bool:
    """Check if a port is available"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            return result != 0  # Port is available if connection fails
    except Exception:
        return False

def get_available_ports(start_port: int = 3002, count: int = 10) -> List[int]:
    """Get list of available ports starting from start_port"""
    available_ports = []
    port = start_port
    
    while len(available_ports) < count and port < 65535:
        if check_port_availability(port):
            available_ports.append(port)
        port += 1
    
    return available_ports

def stop_server(service_name: str) -> bool:
    """Stop a specific server"""
    try:
        if service_name in get_system_state().server_processes:
            process_info = get_system_state().server_processes[service_name]
            process = process_info['process']
            
            # Try graceful shutdown first
            process.terminate()
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
                process.kill()
                process.wait()
            
            # Remove from tracking
            del get_system_state().server_processes[service_name]
            
            logger.info(f"Stopped {service_name} server")
            return True
        else:
            logger.warning(f"Server {service_name} not found")
            return False
            
    except Exception as e:
        logger.error(f"Error stopping server {service_name}: {e}")
        return False

def stop_all_servers():
    """Stop all running servers"""
    try:
        servers = list(get_system_state().server_processes.keys())
        for service_name in servers:
            stop_server(service_name)
        
        logger.info("Stopped all servers")
        
    except Exception as e:
        logger.error(f"Error stopping all servers: {e}")

def get_server_status(service_name: str) -> Dict[str, Any]:
    """Get status of a specific server"""
    try:
        if service_name in get_system_state().server_processes:
            process_info = get_system_state().server_processes[service_name]
            process = process_info['process']
            
            # Check if process is still running
            is_running = process.poll() is None
            
            return {
                'service_name': service_name,
                'port': process_info['port'],
                'pid': process_info['pid'],
                'started_at': process_info['started_at'].isoformat(),
                'is_running': is_running,
                'return_code': process.returncode if not is_running else None
            }
        else:
            return {
                'service_name': service_name,
                'is_running': False,
                'error': 'Server not found'
            }
            
    except Exception as e:
        logger.error(f"Error getting server status for {service_name}: {e}")
        return {
            'service_name': service_name,
            'is_running': False,
            'error': str(e)
        }

def get_all_server_status() -> Dict[str, Any]:
    """Get status of all servers"""
    try:
        status = {}
        for service_name in get_system_state().server_processes.keys():
            status[service_name] = get_server_status(service_name)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'servers': status,
            'total_servers': len(status)
        }
        
    except Exception as e:
        logger.error(f"Error getting all server status: {e}")
        return {
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'servers': {},
            'total_servers': 0
        }

def restart_server(service_name: str) -> bool:
    """Restart a specific server"""
    try:
        # Stop server
        if stop_server(service_name):
            # Wait a moment
            time.sleep(2)
            
            # Get port from previous run
            port = get_system_state().port_assignments.get(service_name, pick_unique_port())
            
            # Start server again
            process = run_server_on_port(port, service_name)
            if process:
                logger.info(f"Successfully restarted {service_name} server")
                return True
            else:
                logger.error(f"Failed to restart {service_name} server")
                return False
        else:
            logger.error(f"Failed to stop {service_name} server for restart")
            return False
            
    except Exception as e:
        logger.error(f"Error restarting server {service_name}: {e}")
        return False

def cleanup_dead_processes():
    """Clean up dead server processes"""
    try:
        dead_servers = []
        
        for service_name, process_info in get_system_state().server_processes.items():
            process = process_info['process']
            
            # Check if process is still running
            if process.poll() is not None:
                dead_servers.append(service_name)
                logger.info(f"Found dead process for {service_name}")
        
        # Remove dead processes
        for service_name in dead_servers:
            del get_system_state().server_processes[service_name]
        
        if dead_servers:
            logger.info(f"Cleaned up {len(dead_servers)} dead server processes")
            
    except Exception as e:
        logger.error(f"Error cleaning up dead processes: {e}")

# Health check functions
def check_server_health(service_name: str) -> Dict[str, Any]:
    """Check health of a specific server"""
    try:
        status = get_server_status(service_name)
        
        if status.get('is_running', False):
            # Try to connect to the server
            port = status.get('port')
            if port:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(5)
                        result = s.connect_ex(('localhost', port))
                        is_responding = result == 0
                except Exception:
                    is_responding = False
            else:
                is_responding = False
        else:
            is_responding = False
        
        return {
            'service_name': service_name,
            'is_running': status.get('is_running', False),
            'is_responding': is_responding,
            'port': status.get('port'),
            'pid': status.get('pid'),
            'uptime': None,  # Could calculate from started_at
            'health_status': 'healthy' if (status.get('is_running') and is_responding) else 'unhealthy'
        }
        
    except Exception as e:
        logger.error(f"Error checking health for {service_name}: {e}")
        return {
            'service_name': service_name,
            'health_status': 'error',
            'error': str(e)
        }

def get_system_health() -> Dict[str, Any]:
    """Get overall system health"""
    try:
        # Check all servers
        server_health = {}
        total_servers = 0
        healthy_servers = 0
        
        for service_name in get_system_state().server_processes.keys():
            health = check_server_health(service_name)
            server_health[service_name] = health
            
            total_servers += 1
            if health.get('health_status') == 'healthy':
                healthy_servers += 1
        
        # Calculate overall health
        overall_health = 'healthy' if healthy_servers == total_servers else 'degraded'
        if total_servers == 0:
            overall_health = 'unknown'
        
        return {
            'timestamp': datetime.now().isoformat(),
            'overall_health': overall_health,
            'total_servers': total_servers,
            'healthy_servers': healthy_servers,
            'unhealthy_servers': total_servers - healthy_servers,
            'servers': server_health
        }
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return {
            'timestamp': datetime.now().isoformat(),
            'overall_health': 'error',
            'error': str(e),
            'total_servers': 0,
            'healthy_servers': 0,
            'unhealthy_servers': 0,
            'servers': {}
        } 