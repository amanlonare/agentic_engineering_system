from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()

@router.post("/login")
def login(user_data: dict):
    # Mock login logic
    return {"access_token": "mock_jwt_token", "token_type": "bearer"}

@router.post("/signup")
def signup(user_data: dict):
    # Mock signup logic
    return {"message": "User created successfully"}
