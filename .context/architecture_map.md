# Architecture Map: Engineering Sandboxes

This map defines the target repositories and their internal structures. Use this to route `write_file` and `read_file` calls.

---

## [ID: testing_agentic_engineering_team]
**Role**: Prototype Mobility Activity Tracker (Monolith).
**Context Path**: `.context/testing_agentic_engineering_team/`

### 🗺️ Repository Map:
- **`src/api/main.py`**: The entry point for the REST API. Contains route definitions for `/predict` (telemetry ingress) and `/feedback` (user ground-truth verification).
- **`src/services/mobile_prediction_service/service.py`**: Business logic layer that orchestrates data flow between the API and the ML models. Handles data cleaning and session management.
- **`src/models/mobile_predictor/model.py`**: The "Brain" of the application. Contains the logic for the Movement Prediction Model (inference, weight loading, and retraining triggers).
- **`src/db/schema.sql`**: Definitive database structure. Defines the `trips` table (predictions vs feedback), `users`, and `challenges` configurations.
- **`infra/terraform/main.tf`**: Infrastructure specification. Describes the AWS stack (RDS for trip data, Lambda for serverless inference, and S3 for telemetry logging).
- **`.github/workflows/ci.yml`**: Automation pipeline. Handles unit testing for the model, terraform verification, and scheduled "Drift Check" analysis jobs.
- **`data/movement_predictions.csv`**: Analytical dataset. Contains 500 rows of mobility telemetry used by the Growth Agent to identify model drift and user churn patterns.

### 🛠️ Environment Constraints:
- **Language**: Python 3.11+ / SQL
- **Frameworks**: FastAPI, SQLAlchemy, Terraform
- **Sandbox Rules**: Standard libraries only for scripts. No `pip install`. No internet access.

---

## Environment Reminder:
- Always use relative paths starting with `.context/testing_agentic_engineering_team/`.
- If a directory doesn't exist, create it with `write_file`.
