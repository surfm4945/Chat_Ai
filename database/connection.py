import os
import sqlite3
import logging
from typing import Optional

# Setup professional logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = "chat_app.db"

def get_db_connection() -> sqlite3.Connection:
    """
    Creates and returns a secure connection to the SQLite database.
    Enforces foreign key constraints automatically.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        # SQLite doesn't enforce Foreign Keys by default. We must turn it on explicitly for every connection.
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise e

def init_db() -> None:
    """
    Initializes the database schema by creating the necessary tables
    if they do not already exist.
    """
    users_table_query = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    messages_table_query = """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (receiver_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Create users table
            cursor.execute(users_table_query)
            # Create messages table
            cursor.execute(messages_table_query)
            conn.commit()
            logger.info("Database initialized successfully with users and messages tables.")
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize database: {e}")
        raise e

if __name__ == "__main__":
    # Running this file directly allows us to test the database initialization locally.
    print("Initializing local database...")
    init_db()
    print("Database ready!")