# Workspace Repository Map

This document contains a map of the mock repositories and their vital files. 
You can use this map to identify which files exist and what they do, without needing to read the actual code files themselves.

## 1. mobile-app
*Frontend application (React Native).*
- `src/components/LoginButton.js`: User interface for the login flow.
- `src/screens/ProfileScreen.js`: User profile display and editing interface.
- `src/services/AuthService.js`: Handles API requests for authentication.
- `src/services/AnalyticsService.js`: Tracks user events and interactions.

## 2. mobile-backend
*Core API gateway and database logic (FastAPI / Node).*
- `app/api/auth.py`: Endpoints for user signup, login, and token generation.
- `app/api/users.py`: Endpoints for user profile management (GET/PUT/DELETE).
- `app/models/user.py`: Database schema for the User object.
- `app/core/security.py`: JWT hashing and password verification logic.

## 3. mobile-predictor
*Machine Learning model logic.*
- *Note:* Code has been removed. Assume implementation exists in `src/model.py` and `src/inference.py`.

## 4. mobile-prediction-service
*Pipeline orchestration for ML.*
- *Note:* Code has been removed. Assume implementation exists in `src/pipeline.py` and `src/s3_utils.py`.

## 5. mobile-terraform
*Infrastructure as Code (AWS).*
- *Note:* Code has been removed. Assume implementation exists in `main.tf` and `variables.tf`.
