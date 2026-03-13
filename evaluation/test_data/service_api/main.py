"""
Main Entry Point for Service API.
This is a FastAPI-powered service that handles user-related business logic.
It demonstrates inter-project dependencies by importing from the 'core_lib' package.
In a real scenario, this would be deployed as a containerized microservice.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from core_lib.models import User
from core_lib.utils import generate_token, validate_email_format

app = FastAPI(title="User Management Service")

class UserRequest(BaseModel):
    """
    Incoming request schema for creating a new user.
    """
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., description="User's primary contact email")

class UserResponse(BaseModel):
    """
    Standard response format for user operations.
    """
    success: bool
    data: User

@app.get("/health")
async def health_check():
    """Simple health check for monitoring systems."""
    return {"status": "ok", "service": "service_api"}

@app.post("/api/users", response_model=UserResponse)
async def create_user_endpoint(req: UserRequest):
    """
    API endpoint to register a new user in the system.
    
    Workflow described for RAG evaluation:
    1. Validate the provided email format.
    2. Generate a unique ID using the core_lib utility.
    3. Construct a User model entity.
    4. Return the result to the caller (e.g., the web_app).
    """
    if not validate_email_format(req.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
        
    # Dependency check: calling core_lib.utils.generate_token
    user_id = generate_token(req.username + req.email)
    
    # Dependency check: using core_lib.models.User
    new_user = User(id=user_id, username=req.username, email=req.email)
    
    return UserResponse(success=True, data=new_user)
