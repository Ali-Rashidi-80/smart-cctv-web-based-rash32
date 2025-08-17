#!/usr/bin/env python3
"""
Update Admin Credentials Script
This script updates existing admin credentials with safe ones that avoid problematic characters.
"""

import os
import sys
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main function to update admin credentials"""
    try:
        # Import the credential management functions
        from core.config import regenerate_admin_credentials, validate_credential_safety, generate_safe_admin_credentials, generate_safe_secret_key
        
        logger.info("🔄 Starting admin credentials update...")
        
        # Check existing credentials
        credentials_file = Path("core/admin_credentials.txt")
        fallback_file = Path("admin_credentials.txt")
        
        existing_credentials = {}
        
        # Check if existing credentials exist and are problematic
        for file_path in [credentials_file, fallback_file]:
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                    
                    # Parse the file content
                    for line in content.split('\n'):
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            existing_credentials[key.strip()] = value.strip()
                    
                    logger.info(f"📁 Found existing credentials in {file_path}")
                    
                    # Check if credentials are safe
                    admin_username = existing_credentials.get('ADMIN_USERNAME', '')
                    admin_password = existing_credentials.get('ADMIN_PASSWORD', '')
                    secret_key = existing_credentials.get('SECRET_KEY', '')
                    
                    if (validate_credential_safety(admin_username) and 
                        validate_credential_safety(admin_password) and 
                        validate_credential_safety(secret_key)):
                        logger.info("✅ Existing credentials are already safe!")
                        logger.info(f"   Username: {admin_username}")
                        logger.info(f"   Password: {admin_password}")
                        logger.info(f"   Secret Key: {secret_key[:20]}...")
                        return
                    else:
                        logger.warning("⚠️ Existing credentials contain problematic characters")
                        break
                        
                except Exception as e:
                    logger.warning(f"⚠️ Error reading {file_path}: {e}")
                    continue
        
        # Regenerate credentials
        logger.info("🔄 Regenerating admin credentials with safe characters...")
        admin_username, admin_password, secret_key = regenerate_admin_credentials()
        
        logger.info("✅ Admin credentials updated successfully!")
        logger.info(f"   Username: {admin_username}")
        logger.info(f"   Password: {admin_password}")
        logger.info(f"   Secret Key: {secret_key[:20]}...")
        logger.info("")
        logger.info("🔐 New credentials are safe for microcontrollers and can be used in quotes.")
        logger.info("📝 Credentials saved to both core/admin_credentials.txt and admin_credentials.txt")
        
    except ImportError as e:
        logger.error(f"❌ Error importing core modules: {e}")
        logger.error("Make sure you're running this script from the project root directory")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error updating credentials: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 