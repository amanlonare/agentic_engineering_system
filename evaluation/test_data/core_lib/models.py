"""
Core Models for the Agentic Engineering System Evaluation.
This module defines the baseline data structures used across the entire platform.
It serves as the 'source of truth' for object schemas.
"""

from typing import Optional
from pydantic import BaseModel, Field

class BaseRecord(BaseModel):
    """
    Abstract base class for all persistent records in the system.
    Provides common fields like 'id' and 'created_at' for traceability.
    """
    id: str = Field(..., description="Unique identifier for the record")
    metadata: dict = Field(default_factory=dict, description="Extensible metadata storage")

class User(BaseModel):
    """
    Represents a user entity within the ecosystem.
    Users are the primary actors who interact with the agentic services.
    
    Attributes:
        id (str): The unique access token or identifier.
        username (str): The display name chosen by the user.
        email (str): Validated electronic mail address.
    """
    id: str
    username: str
    email: str
    is_active: bool = True
    role: str = "developer"

def get_system_status() -> str:
    """
    Returns the current operational status of the core library.
    Used for health checks and system monitoring across services.
    """
    return "HEALTHY"
