import re

def validate_username(username: str) -> tuple[bool, str]:
    """
    Validates a username based on length and allowed characters.
    Returns a tuple of (is_valid, error_message).
    """
    cleaned = username.strip()
    if len(cleaned) < 3 or len(cleaned) > 20:
        return False, "Username must be between 3 and 20 characters long."
    
    # Alphanumeric and underscores only
    if not re.match(r"^[a-zA-Z0-9_]+$", cleaned):
        return False, "Username can only contain letters, numbers, and underscores."
    
    return True, ""

def validate_password(password: str) -> tuple[bool, str]:
    """
    Validates password strength.
    Returns a tuple of (is_valid, error_message).
    """
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    
    return True, ""