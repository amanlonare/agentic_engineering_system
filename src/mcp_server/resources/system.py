import csv
import logging

from ..server import mcp, retriever

logger = logging.getLogger(__name__)


@mcp.resource("context://graph/schema")
def get_graph_schema() -> str:
    """
    Returns the structural schema of the Kùzu Knowledge Graph.
    Includes node tables, relationship definitions, and property types.
    """
    logger.info("Retrieving graph schema resource")
    return retriever.graph_store.get_schema()


@mcp.resource("context://metrics/last_run")
def get_evaluation_metrics() -> str:
    """
    Returns the latest Ragas evaluation metrics from the results file.
    Includes Faithfulness, Relevancy, Precision, and Recall scores.
    """
    results_path = "evaluation/data/results.csv"
    try:
        logger.info("Reading evaluation metrics from: %s", results_path)
        with open(results_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Just return the summary or the last row as a quick metric overview
            rows = list(reader)
            if not rows:
                return "No evaluation results available."

            # Simple summary logic: average metrics across the run
            last_run = rows[-1]
            summary = [
                "Latest RAG Evaluation Summary:",
                f"- Input: {last_run.get('user_input', 'N/A')}",
                f"- Faithfulness: {last_run.get('faithfulness', 'N/A')}",
                f"- Relevancy: {last_run.get('answer_relevancy', 'N/A')}",
                f"- Precision: {last_run.get('context_precision', 'N/A')}",
                f"- Recall: {last_run.get('context_recall', 'N/A')}",
            ]
            return "\n".join(summary)
    except FileNotFoundError:
        return f"Metrics file not found at {results_path}."
    except Exception as e:
        logger.error("Failed to retrieve metrics: %s", e)
        return f"Error reading metrics: {str(e)}"
