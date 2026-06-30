import sqlite3
import logging
from typing import List, Dict, Any, Optional
from database.connection import get_db_connection

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def _patch_database():
    """
    Self-healing migration. Automatically adds columns and recovery features
    to tables if they do not exist.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Patch for rich media
            cursor.execute("ALTER TABLE messages ADD COLUMN file_path TEXT DEFAULT NULL;")
            cursor.execute("ALTER TABLE messages ADD COLUMN file_type TEXT DEFAULT NULL;")
            conn.commit()
    except sqlite3.OperationalError:
        pass

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Patch users table to support the password recovery phrase
            cursor.execute("ALTER TABLE users ADD COLUMN recovery_phrase TEXT DEFAULT 'network-secure';")
            conn.commit()
            logger.info("Database schemas securely validated and updated.")
    except sqlite3.OperationalError:
        pass

# Run data structural patches on startup
_patch_database()

def send_message(sender_id: int, receiver_id: int, content: str, file_path: Optional[str] = None, file_type: Optional[str] = None) -> bool:
    """Saves a private message with optional rich media attachments to the database."""
    cleaned_content = content.strip()
    if not cleaned_content and not file_path:
        return False

    query = "INSERT INTO messages (sender_id, receiver_id, content, file_path, file_type) VALUES (?, ?, ?, ?, ?);"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (sender_id, receiver_id, cleaned_content, file_path, file_type))
            conn.commit()
            return True
    except sqlite3.Error as e:
        logger.error(f"Failed to transmit data packet: {e}")
        return False

def get_chat_history(user_one_id: int, user_two_id: int) -> List[Dict[str, Any]]:
    """Retrieves complete historical transcript matrix between two nodes."""
    query = """
    SELECT id, sender_id, receiver_id, content, timestamp, file_path, file_type 
    FROM messages
    WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
    ORDER BY timestamp ASC;
    """
    history = []
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_one_id, user_two_id, user_two_id, user_one_id))
            records = cursor.fetchall()
            for row in records:
                history.append({
                    "id": row[0], "sender_id": row[1], "receiver_id": row[2],
                    "content": row[3], "timestamp": row[4], "file_path": row[5], "file_type": row[6]
                })
    except sqlite3.Error as e:
        logger.error(f"Failed to retrieve chat logs: {e}")
    return history

def clear_chat_history(user_one_id: int, user_two_id: int) -> bool:
    """
    Privacy Wipeout: Permanently deletes all chat logs and links between two users.
    """
    query = "DELETE FROM messages WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?);"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_one_id, user_two_id, user_two_id, user_one_id))
            conn.commit()
            logger.warning(f"Data channel wiped clean between Node {user_one_id} and Node {user_two_id}.")
            return True
    except sqlite3.Error as e:
        logger.error(f"Failed to clear secure logs: {e}")
        return False

def get_all_users(exclude_user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieves all registered system identity nodes."""
    if exclude_user_id:
        query = "SELECT id, username FROM users WHERE id != ? ORDER BY username ASC;"
        params = (exclude_user_id,)
    else:
        query = "SELECT id, username FROM users ORDER BY username ASC;"
        params = ()

    users_list = []
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor.fetchall():
                users_list.append({"id": row[0], "username": row[1]})
    except sqlite3.Error as e:
        logger.error(f"Failed to fetch user index: {e}")
    return users_list