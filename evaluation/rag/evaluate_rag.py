"""
RAG Pipeline Evaluation Script.

Uses the pre-generated synthetic testset (evaluation/data/rag_testset.json)
against the isolated evaluation stores so production data is never touched.

Compatibility: Ragas 0.4.x (using modern collections and factories)
Usage:
  python evaluation/rag/evaluate_rag.py
"""

import os
import sys
import logging
import json
import numpy as np
import matplotlib.pyplot as plt
from typing import Any, cast

# Add project root to path
sys.path.append(os.getcwd())

# ── Third-party imports ──────────────────────────────────────────────────────
from datasets import Dataset                                         # type: ignore
from ragas import evaluate                                           # type: ignore
from ragas.evaluation import EvaluationResult                        # type: ignore
from ragas.metrics import (                                       # type: ignore
    Faithfulness,
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
)
from ragas.llms import BaseRagasLLM                                  # type: ignore
from ragas.embeddings import BaseRagasEmbedding                      # type: ignore
from openai import OpenAI

from datetime import datetime

# ── Project imports ───────────────────────────────────────────────────────────
from src.core.config import settings
from src.core.vector_store import VectorStore
from src.core.graph_store import GraphStore
from src.core.context_retriever import ContextRetriever

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

TESTSET_PATH = "evaluation/data/rag_testset.json"
RESULTS_PATH = "evaluation/data/results.csv"
PLOT_PATH = "evaluation/data/metrics_summary.png"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_testset(path: str) -> list[dict]:
    """Load testset samples from rag_testset.json."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Testset not found at '{path}'. "
            "Please run evaluation/rag/generate_testset.py first."
        )
    with open(path) as f:
        return json.load(f)


def build_rag_retriever() -> ContextRetriever:
    """Initialize ContextRetriever pointed at the EVALUATION stores."""
    print(f"🔌 ChromaDB collection : {settings.EVAL_CHROMA_COLLECTION_NAME}")
    print(f"🔌 Kuzu DB path        : {settings.EVAL_KUZU_DB_PATH}")
    vector_store = VectorStore(
        db_path=settings.EVAL_CHROMA_DB_PATH,
        collection_name=settings.EVAL_CHROMA_COLLECTION_NAME,
    )
    graph_store = GraphStore(db_path=settings.EVAL_KUZU_DB_PATH)
    return ContextRetriever(vector_store=vector_store, graph_store=graph_store)


def run_rag_for_sample(
    retriever: ContextRetriever,
    openai_client: OpenAI,
    question: str,
) -> tuple[str, list[str]]:
    """
    Run the full RAG pipeline for a single question.
    """
    # Step 1 — Retrieve contexts from eval stores
    result = retriever.retrieve(query=question, n_results=5, expand_graph=True)
    contexts: list[str] = [ctx.content for ctx in result.contexts if ctx.content]

    if not contexts:
        return "No relevant context found.", []

    # Step 2 — Build prompt for GPT-4o-mini
    context_block = "\n\n---\n\n".join(contexts)
    messages = [
        {"role": "system", "content": "You are a helpful code assistant. Use ONLY the provided context."},
        {"role": "user", "content": f"CONTEXT:\n{context_block}\n\nQUESTION: {question}"}
    ]

    # Step 3 — Generate using direct OpenAI client (fastest for simple prompt)
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,  # type: ignore
        temperature=0
    )
    answer = response.choices[0].message.content or "No answer generated."
    return answer, contexts


def visualize_results(eval_result: Any, output_path: str) -> None:
    """Generate a Radar Plot for the aggregate metrics."""
    print(f"📈 Generating visualization: {output_path}")
    
    # Extract aggregate scores
    scores = {}
    import pandas as pd
    df = eval_result.to_pandas()
    for col in df.columns:
        if col not in ["question", "answer", "contexts", "ground_truth", "reference"]:
            # Ensure numeric conversion to avoid reduction errors
            scores[col] = pd.to_numeric(df[col], errors='coerce').mean()  # type: ignore

    if not scores:
        print("⚠️ No metrics found to visualize.")
        return

    # Radar chart setup
    labels = list(scores.keys())
    values = list(scores.values())
    num_vars = len(labels)

    # Compute angle for each axis
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    
    # The plot is circular, so we need to "complete the loop"
    values += values[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    
    # Draw one axe per variable + add labels
    plt.xticks(angles[:-1], labels, color='grey', size=10)

    # Draw ylabels
    ax.set_rlabel_position(0)  # type: ignore
    plt.yticks([0.2, 0.4, 0.6, 0.8, 1.0], ["0.2", "0.4", "0.6", "0.8", "1.0"], color="grey", size=7)
    plt.ylim(0, 1)

    # Plot data
    ax.plot(angles, values, linewidth=1, linestyle='solid', label='RAG Performance')
    ax.fill(angles, values, 'b', alpha=0.1)

    plt.title("RAG Evaluation Metrics Summary", size=15, color='blue', y=1.1)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, bbox_inches='tight')
    plt.close()
    print("✅ Visualization saved.")


# ── Main evaluation loop ──────────────────────────────────────────────────────

def evaluate_rag() -> None:
    """Main evaluation entry point."""
    print("=" * 60)
    print("  RAG Pipeline Evaluation")
    print("=" * 60)

    if not settings.OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY not set. Please check your .env file.")
        return

    # 1. Load testset
    print(f"📂 Loading testset from {TESTSET_PATH}...")
    samples = load_testset(TESTSET_PATH)
    print(f"   Found {len(samples)} samples.")

    # 2. Initialize Components
    retriever = build_rag_retriever()
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    # Ragas Modern 0.4.x approach
    from ragas.llms import llm_factory
    from ragas.embeddings import OpenAIEmbeddings
    ragas_llm = llm_factory("gpt-4o-mini", client=client, max_tokens=2048)
    ragas_emb = OpenAIEmbeddings(model="text-embedding-3-small", client=client)
    
    # Compatibility shim: some metrics expect embed_query (older interface)
    if not hasattr(ragas_emb, "embed_query"):
        setattr(ragas_emb, "embed_query", ragas_emb.embed_text)
    if not hasattr(ragas_emb, "embed_documents"):
        setattr(ragas_emb, "embed_documents", ragas_emb.embed_texts)

    # 3. Run RAG on each sample
    print(f"\n⚡ Running RAG pipeline on {len(samples)} questions...")
    questions, answers, contexts_list, ground_truths = [], [], [], []

    for i, sample in enumerate(samples, 1):
        q: str = sample.get("user_input") or sample.get("question", "")
        gt: str = sample.get("reference", "")

        if not q:
            continue

        print(f"   [{i}/{len(samples)}] {q[:60]}...")
        ans, ctxs = run_rag_for_sample(retriever, client, q)

        questions.append(q)
        answers.append(ans)
        contexts_list.append(ctxs)
        ground_truths.append(gt)

    if not questions:
        print("❌ No valid questions found in testset.")
        return

    # 4. Build Dataset
    eval_dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts_list,
        "ground_truth": ground_truths,
    })

    # 5. Evaluate with Ragas metrics
    print("\n🧮 Running Ragas evaluation...")
    
    # Standard Ragas metrics (classes from ragas.metrics satisfy evaluate() requirements)
    metrics = [
        Faithfulness(llm=ragas_llm),
        AnswerRelevancy(llm=ragas_llm, embeddings=ragas_emb),
        ContextPrecision(llm=ragas_llm),
        ContextRecall(llm=ragas_llm)
    ]

    # Create an experiment name with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    experiment_name = f"rag_eval_{timestamp}"
    print(f"📊 Experiment: {experiment_name}")

    result = evaluate(
        dataset=eval_dataset,
        metrics=metrics,
        experiment_name=experiment_name,
    )

    # 6. Handle return type (EvaluationResult | Executor)
    from ragas.executor import Executor
    if isinstance(result, Executor):
        print("⏳ Waiting for async results...")
        eval_result = cast(EvaluationResult, result.results())
    elif hasattr(result, "to_pandas"):
        eval_result = cast(EvaluationResult, result)
    else:
        # Fallback for complex Union types in some Ragas versions
        eval_result = cast(EvaluationResult, result)

    # 7. Display & Save Results
    print("\n" + "=" * 60)
    print("  📊 AGGREGATE SCORES")
    print("=" * 60)
    
    import pandas as pd
    result_df = eval_result.to_pandas()
    for col in result_df.columns:
        if col not in ["question", "answer", "contexts", "ground_truth"]:
            avg = pd.to_numeric(result_df[col], errors='coerce').mean()  # type: ignore
            if not np.isnan(avg):
                print(f"    {col:<25}: {avg:.3f}")

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    result_df.to_csv(RESULTS_PATH, index=False)
    print(f"\n✅ Full results saved to {RESULTS_PATH}")

    # 8. Visualize
    visualize_results(eval_result, PLOT_PATH)


if __name__ == "__main__":
    evaluate_rag()
