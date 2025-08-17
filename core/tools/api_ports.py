from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from core.tools.dynamic_port_manager import DynamicPortManager
import os

router = APIRouter()
# Use singleton pattern to avoid multiple instances
_port_manager_instance = None

def get_port_manager():
    global _port_manager_instance
    if _port_manager_instance is None:
        _port_manager_instance = DynamicPortManager(3000, 9000, json_path="utils/port_state/dynamic_ports_service1.json", refresh_interval=60, enable_background_logging=False)
    return _port_manager_instance

@router.get("/port/state")
def get_port_state():
    return get_port_manager().get_state()

@router.get("/port/free")
def get_free_ports():
    return {"free_ports": get_port_manager().state.get("free_ports", [])}

@router.get("/port/used")
def get_used_ports():
    return {"used_ports": get_port_manager().state.get("used_ports", [])}

@router.get("/port/history")
def get_history():
    return {"history": get_port_manager().state.get("history", [])}

@router.get("/port/backup/list")
def list_backups():
    backup_dir = os.path.join(os.path.dirname(get_port_manager().json_path), "backups")
    if not os.path.exists(backup_dir):
        return {"backups": []}
    return {"backups": sorted(os.listdir(backup_dir))}

@router.get("/port/backup/download")
def download_backup(filename: str = Query(...)):
    backup_dir = os.path.join(os.path.dirname(get_port_manager().json_path), "backups")
    file_path = os.path.join(backup_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(file_path, filename=filename)


# در main.py یا server_fastapi.py:
# app.include_router(router, prefix="/api/v1")