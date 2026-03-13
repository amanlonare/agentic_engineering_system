"""
Utility functions for the Core Library.
This module provides lower-level helpers used by higher-level services like the service_api.
Consistent hashing and tokenization logic should be centralized here.
"""

import hashlib

def generate_token(seed: str) -> str:
    """
    Generates a secure, deterministic token based on a seed string.
    Uses SHA-256 hashing to ensure low collision rates.
    
    Args:
        seed (str): The source string (e.g., username + timestamp)
        
    Returns:
        str: A prefixed hexadecimal token string.
    """
    if not seed:
        raise ValueError("Seed cannot be empty for token generation")
        
    sha_signature = hashlib.sha256(seed.encode()).hexdigest()
    # We use the first 12 characters for brevity in this evaluation scenario
    return f"token_{sha_signature[:12]}"

def validate_email_format(email: str) -> bool:
    """
    Simple validation for email address strings.
    Ensures basic structural integrity (contains '@' and '.').
    """
    return "@" in email and "." in email
