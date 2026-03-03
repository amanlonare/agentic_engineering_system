# Mobile Predictor Repository

This repository contains the core Machine Learning models for the mobile platform.

## Architectural Overview
This is a standalone Python package responsible purely for model definition, training scripts, and inference logic. It does *not* expose an API. Instead, it is consumed as a library or its serialized artifacts are loaded by the `mobile-prediction-service`.

## Core Responsibilities
- **Model Training**: Scripts to train the user retention and recommendation models.
- **Inference Logic**: Optimized mathematical implementations for generating predictions from raw data (`src/inference.py`).
- **Data Engineering**: Feature extraction logic (`src/features.py`).

## Directory Structure
- `src/model.py`: PyTorch/Scikit-Learn model definitions.
- `src/inference.py`: Helper functions for fast prediction generation.
- `src/train.py`: Training pipelines.
- `notebooks/`: Jupyter notebooks for exploratory data analysis.

## Key Technologies
- **Frameworks**: PyTorch, Scikit-Learn
- **Data Processing**: Pandas, NumPy

*Note: For the mock environment, actual implementation files may be missing. Assume the interfaces exist as described.*
