#!/usr/bin/env python3
"""
Cleanup Script for VB Stat Logger

This script removes all generated API endpoint files and configuration,
allowing a fresh rebuild using the generator script.

Usage:
    python cleanup_api_files.py

This will remove:
1. collections.json config file
2. All service files
3. All route files (except core router files)
4. Reset the entity registry
5. Reset the schema imports

After running this script, use generate_basic_crud_api_endpoints.py to rebuild everything:
    python generate_basic_crud_api_endpoints.py --all schemas/
"""
import os
import glob
import shutil
from pathlib import Path

from loguru import logger

def confirm_action():
    """Get user confirmation before proceeding."""
    print("\n⚠️  WARNING: This will delete all generated API endpoints and configurations.")
    print("All service files, route files, and collections configuration will be removed.")
    print("This operation cannot be undone.\n")
    response = input("Are you sure you want to proceed? (yes/no): ")
    if response.lower() != "yes":
        print("Operation cancelled by user")
        exit(0)
    print("User confirmed cleanup operation\n")

def delete_file(filepath):
    """Delete a file if it exists."""
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            logger.info(f"Deleted: {filepath}")
        except Exception as e:
            logger.error(f"Failed to delete {filepath}: {e}")
    else:
        logger.warning(f"File not found: {filepath}")

def reset_file_content(filepath, content):
    """Reset a file to contain only the specified content."""
    try:
        with open(filepath, 'w') as f:
            f.write(content)
        logger.info(f"Reset: {filepath}")
    except Exception as e:
        logger.error(f"Failed to reset {filepath}: {e}")

def cleanup():
    """Run the cleanup process."""
    # Get project root
    project_root = Path(__file__).parent.parent
    
    # 1. Delete collections.json config file
    collections_config = project_root / "backend" / "config" / "collections.json"
    delete_file(collections_config)
    
    # 2. Delete all service files (except core ones)
    services_dir = project_root / "backend" / "services"
    service_files = glob.glob(str(services_dir / "*_service.py"))
    for service_file in service_files:
        delete_file(service_file)
    
    # 3. Delete all route files (except core router files)
    routes_dir = project_root / "backend" / "routes"
    route_files = glob.glob(str(routes_dir / "*_routes.py"))
    for route_file in route_files:
        delete_file(route_file)
    
    # Also delete the entity router JSON file
    entity_router_json = routes_dir / "entity_router.json"
    delete_file(entity_router_json)
    
    # 4. Reset the entity registry file
    entity_registry = routes_dir / "entities.py"
    registry_content = '''"""
Entity router registry - automatically updated by the generator script.
"""
from fastapi import APIRouter

# Import all entity routers
# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE

# Create a list of all routers to be included
entity_routers = [
    # AUTO-GENERATED ROUTERS - DO NOT REMOVE THIS LINE
]
'''
    reset_file_content(entity_registry, registry_content)
    
    # 5. Reset the schemas/__init__.py file
    schemas_init = project_root / "backend" / "schemas" / "__init__.py"
    schemas_content = '''"""Schemas package for VB Stat Logger API."""

# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE

__all__ = [
    # AUTO-GENERATED MODELS - DO NOT REMOVE THIS LINE
]
'''
    reset_file_content(schemas_init, schemas_content)
    
    # 6. Delete generated schema files
    schema_files = glob.glob(str(project_root / "backend" / "schemas" / "*.py"))
    for schema_file in schema_files:
        # Skip __init__.py and other core files
        if os.path.basename(schema_file) not in ['__init__.py']:
            delete_file(schema_file)
    
    print("\n✅ Cleanup complete! All generated API files have been removed.")
    print("\nNext steps:")
    print("1. Run the generator script to rebuild everything with singular collection names:")
    print("   python scripts/generate_basic_crud_api_endpoints.py --all schemas/")
    print("\n2. Initialize the database with the updated collections:")
    print("   python scripts/init_arangodb.py")

if __name__ == "__main__":
    confirm_action()
    cleanup()
