from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()

@router.get("/profile")
def get_user_profile(user_id: int):
    # Mock get profile logic
    return {"id": user_id, "name": "John Doe", "email": "john@example.com"}

@router.put("/profile")
def update_user_profile(user_id: int, update_data: dict):
    # Mock update profile logic
    return {"message": "Profile updated successfully", "data": update_data}
