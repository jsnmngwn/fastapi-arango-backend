#!/usr/bin/env python3
"""
Script to drop the application ArangoDB database.

This script will completely delete the configured application database from the ArangoDB server.
Use with caution as this action cannot be undone.
"""

import os
import sys

from arango import ArangoClient
from loguru import logger

# Add the project root to the path so we can import the backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import database configuration
from backend.db import DB_HOST, DB_NAME, DB_PASS, DB_USER



def drop_database():
    """Drop the entire application database from the ArangoDB server."""
    logger.info(f"Starting to drop the {DB_NAME} database")

    # Connect to the _system database to drop our application database
    client = ArangoClient(hosts=DB_HOST)
    sys_db = client.db("_system", username=DB_USER, password=DB_PASS)

    # Check if the database exists
    if sys_db.has_database(DB_NAME):
        logger.info(f"Database {DB_NAME} exists, proceeding with deletion")

        # Drop the database
        try:
            sys_db.delete_database(DB_NAME)
            logger.info(f"Database {DB_NAME} successfully dropped")
        except Exception as e:
            logger.error(f"Failed to drop database {DB_NAME}: {str(e)}")
            raise
    else:
        logger.info(f"Database {DB_NAME} does not exist, nothing to drop")

    logger.info("Database drop operation completed")


def confirm_drop():
    """Get user confirmation before dropping the database."""
    response = input(
        f"WARNING: This will completely delete the {DB_NAME} database. This operation cannot be undone. Are you sure? (yes/no): "
    )
    if response.lower() != "yes":
        logger.info("Operation cancelled by user")
        sys.exit(0)
    logger.info("User confirmed database drop operation")


if __name__ == "__main__":
    confirm_drop()
    drop_database()
