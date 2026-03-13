#!/bin/bash

# RAG Evaluation Automation Script
# This script resets the evaluation environment and runs the full pipeline.

set -e  # Exit on error

echo "🧹 Resetting RAG Evaluation environment..."

# 1. Remove isolated evaluation data (preserving test_data directory)
rm -rf evaluation/vector
rm -rf evaluation/graph
rm -rf evaluation/data/*.json
rm -rf evaluation/data/*.csv
rm -rf evaluation/data/*.png

echo "✅ Evaluation data cleared (test_data preserved)."

# 2. Ingest Data
echo "🚀 Step 1/3: Ingesting Evaluation Data..."
uv run python evaluation/rag/ingest_eval_data.py

# 3. Generate Testset
echo "🧠 Step 2/3: Generating Synthetic Testset..."
uv run python evaluation/rag/generate_testset.py

# 4. Run Evaluation
echo "🧮 Step 3/3: Running RAG Evaluation..."
uv run python evaluation/rag/evaluate_rag.py

echo "============================================================"
echo "✨ RAG Evaluation Complete!"
echo "📍 Results : evaluation/data/results.csv"
echo "📍 Plot    : evaluation/data/metrics_summary.png"
echo "============================================================"
