# Mobile App Repository

This is the frontend repository for the Mobile ecosystem, built with React Native.

## Architectural Overview
This application serves as the primary user interface for end-users. It communicates exclusively with the `mobile-backend` API for data persistence, authentication, and core business logic.

## Directory Structure
- `src/components/`: Reusable, stateless UI components (e.g., buttons, inputs, banners).
- `src/screens/`: Stateful screen components representing distinct views (e.g., Login, Profile, Home).
- `src/services/`: API clients and business logic abstractions (e.g., `AuthService` for login logic, `AnalyticsService` for tracking).
- `src/navigation/`: App routing configuration.

## Key Technologies
- **Framework**: React Native
- **State Management**: Redux Toolkit
- **Navigation**: React Navigation
- **Styling**: Vanilla Styled Components

## Testing
- Unit tests run via Jest.
- E2E tests run via Detox.
