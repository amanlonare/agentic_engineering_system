# Mobile Prediction Service

This repository houses the orchestration API that serves the Machine Learning models.

## Architectural Overview
A lightweight microservice built to expose the models developed in `mobile-predictor` via a high-performance REST API. It acts as an intermediary between the `mobile-backend` and the heavy ML computations.

## Core Responsibilities
- **Model Serving**: Loading serialized models and exposing prediction endpoints (`src/pipeline.py`).
- **Batch Processing**: Handling asynchronous jobs for large dataset predictions.
- **Data Fetching**: Pulling raw data from S3 buckets as needed (`src/s3_utils.py`).

## Directory Structure
- `src/api.py`: FastAPI endpoints for predictions.
- `src/pipeline.py`: Orchestration logic linking the web request to the ML inference functions.
- `src/s3_utils.py`: Utilities for interacting with AWS storage.

## Key Technologies
- **Framework**: Python / FastAPI
- **Cloud**: AWS S3, Boto3

*Note: For the mock environment, actual implementation files may be missing. Assume the interfaces exist as described.*
