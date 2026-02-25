# Mobile Backend Repository

This is the central API gateway and business logic provider for the Mobile ecosystem.

## Architectural Overview
The backend is a monolithic FastAPI application that handles all core platform functionality. It serves as the primary data interface for the `mobile-app` and orchestrates calls to internal microservices like the `mobile-prediction-service`.

## Core Responsibilities
- **Authentication & Authorization**: Handled via JWT tokens (logic in `app/core/security.py`).
- **User Management**: Profile CRUD operations (logic in `app/api/users.py`, schema in `app/models/user.py`).
- **Payments**: Integration with Stripe for subscription processing.

## Directory Structure
- `app/api/`: REST API route definitions.
- `app/core/`: Core internal logic, security, and configuration.
- `app/models/`: Database schemas and Pydantic models.
- `app/services/`: Specific business logic encapsulations.
- `app/db/`: Database connection and session management.

## Key Technologies
- **Framework**: Python / FastAPI
- **Database**: PostgreSQL (interacted via SQLModel or SQLAlchemy)
- **Caching**: Redis

## Notes for Planners
All endpoints are prefixed with `/api/v1/`. Ensure new API features are cleanly separated into their respective domain modules in `app/api/`.
