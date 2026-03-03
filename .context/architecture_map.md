# Workspace Repository Map

> [!IMPORTANT]
> **TARGET REPOSITORY IDs**: Use the exact ID in the brackets below (e.g., `testing_agentic_engineering_team`).
> **ENVIRONMENT**: This is a restricted sandbox. You MUST use ONLY Python Standard Libraries for implementation and verification (no flask, no requests, no boto3).

## 1. testing_agentic_engineering_team [ID: testing_agentic_engineering_team]
*Main sandbox for the Agentic Engineering Team.*

### Backend (FastAPI - Logic Only)
- `backend/app/api/`: API route handlers.
- `backend/app/core/`: Security (password logic) and configurations.
- `backend/app/services/`: Business logic.

### Frontend (Next.js - Logic Only)
- `frontend/src/app/`: App Router pages.
- `frontend/src/services/`: API client.
