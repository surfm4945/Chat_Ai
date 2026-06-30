import os
import hashlib
import secrets
import sqlite3
import logging
from typing import Optional, Dict, Any
from database.connection import get_db_connection

# Setup logging
logger = logging.getLogger(__name__)

def hash_password(password: str) -> str:
    """
    Generates a secure, salted PBKDF2 hash of a plain text password.
    Requires no external packages (uses built-in hashlib).
    """
    # Generate a secure, random 16-byte salt
    salt = os.urandom(16)
    # Set standard security iterations (100,000 rounds)
    iterations = 100000
    
    # Generate the raw binary hash
    hashed_bytes = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    
    # Format as a single string to save in the database easily: iterations:salt:hash
    return f"{iterations}:{salt.hex()}:{hashed_bytes.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifies an incoming plain text password against a stored PBKDF2 hash string.
    """
    try:
        # Extract our parameters back out of the saved database string
        iterations_str, salt_hex, hashed_hex = stored_hash.split(":")
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        original_hash = bytes.fromhex(hashed_hex)
        
        # Hash the incoming password attempt using the exact same salt and iterations
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
        
        # Use secrets.compare_digest to prevent timing attacks (constant-time comparison)
        return secrets.compare_digest(original_hash, new_hash)
    except (ValueError, TypeError, AttributeError):
        # If the string layout is corrupted or unreadable, safely reject authentication
        return False

def register_user(username: str, password: str) -> tuple[bool, str]:
    """
    Hashes the password and registers a unique user in the database.
    Returns (success_status, status_message).
    """
    cleaned_username = username.strip()
    hashed_pwd = hash_password(password)

    query = "INSERT INTO users (username, password_hash) VALUES (?, ?);"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (cleaned_username, hashed_pwd))
            conn.commit()
            logger.info(f"User '{cleaned_username}' registered successfully.")
            return True, "Registration successful!"
    except sqlite3.IntegrityError:
        logger.warning(f"Registration failed: Username '{cleaned_username}' is already taken.")
        return False, "Username is already taken."
    except sqlite3.Error as e:
        logger.error(f"Database error during registration: {e}")
        return False, "An unexpected error occurred. Please try again later."

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticates a user. If successful, returns user record details.
    """
    cleaned_username = username.strip()
    query = "SELECT id, username, password_hash FROM users WHERE username = ?;"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (cleaned_username,))
            user_record = cursor.fetchone()

            if user_record:
                user_id, db_username, stored_hash = user_record
                if verify_password(password, stored_hash):
                    logger.info(f"User '{cleaned_username}' authenticated successfully.")
                    return {"id": user_id, "username": db_username}
            
            logger.warning(f"Failed login attempt for username: '{cleaned_username}'.")
            return None
    except sqlite3.Error as e:
        logger.error(f"Database error during authentication: {e}")
        return None