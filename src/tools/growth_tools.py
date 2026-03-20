import csv
import os
from collections import Counter
from typing import Optional

from langchain_core.tools import tool

from src.core.resource_manager import ResourceManager
from src.utils.logger import configure_logging

logger = configure_logging("growth_tools")
resource_manager = ResourceManager()


async def _get_abs_path(path: str, repo_name: Optional[str] = None) -> str:
    """Resolves tool paths dynamically via ResourceManager."""
    if repo_name:
        # If repo is provided, resolve its base directory
        try:
            base_dir = await resource_manager.resolve_resource_path(repo_name)
            return os.path.join(base_dir, path)
        except Exception:
            pass

    # Return path as-is if no repo provided or resolution fails
    return path


@tool
async def analyze_prediction_accuracy(
    path: str = "data/movement_predictions.csv", repo_name: Optional[str] = None
) -> str:
    """
    Analyzes mobility prediction accuracy (predicted vs actual modes).
    Returns per-region and per-mode accuracy and confusion clusters.
    """
    abs_path = await _get_abs_path(path, repo_name)
    logger.info("📊 Analyzing prediction accuracy in %s...", abs_path)

    if not os.path.exists(abs_path):
        return f"Error: Data file {abs_path} not found."

    stats = {}  # (region, mode) -> {correct: 0, total: 0}
    confusion = Counter()  # (region, predicted, actual) -> count

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                region = row.get("region", "unknown")
                pred = row.get("predicted_mode", "unknown")
                actual = row.get("actual_mode", "")

                if not actual:  # Skip if no feedback
                    continue

                key = (region, actual)
                if key not in stats:
                    stats[key] = {"correct": 0, "total": 0}

                stats[key]["total"] += 1
                if pred == actual:
                    stats[key]["correct"] += 1
                else:
                    confusion[(region, pred, actual)] += 1

        # Format results
        output = ["### Prediction Accuracy Report\n"]
        regions = sorted(list(set(k[0] for k in stats.keys())))

        if not regions:
            return "No valid regions or feedback data found in CSV."

        for r in regions:
            output.append(f"#### Region: {r}")
            r_total = 0
            r_correct = 0
            for (reg, mode), data in stats.items():
                if reg == r:
                    acc = (data["correct"] / data["total"]) * 100
                    acc_text = f"{acc:.1f}% ({data['correct']}/{data['total']})"
                    output.append(f"- {mode.capitalize()}: {acc_text}")
                    r_total += data["total"]
                    r_correct += data["correct"]

            total_acc = (r_correct / r_total) * 100 if r_total > 0 else 0
            output.append(f"**Regional Average: {total_acc:.1f}%**\n")

        # Significant Confusions
        output.append("### Major Confusion Clusters (Error > 10%)")
        found_confusion = False
        for (reg, pred, actual), count in confusion.most_common():
            total_for_mode = stats[(reg, actual)]["total"]
            error_rate = (count / total_for_mode) * 100
            if error_rate > 10:
                output.append(
                    f"- {reg}: Predicted '{pred}' instead of '{actual}' "
                    f"in {error_rate:.1f}% of cases."
                )
                found_confusion = True

        if not found_confusion:
            output.append("No major confusion clusters detected.")

        return "\n".join(output)

    except Exception as e:
        return f"Error analyzing data: {str(e)}"


@tool
async def detect_activity_trends(
    path: str = "data/movement_predictions.csv", repo_name: Optional[str] = None
) -> str:
    """
    Detects declining user activity trends which might indicate churn.
    Returns a list of users with significant drops in movement volume.
    """
    abs_path = await _get_abs_path(path, repo_name)
    logger.info("📈 Detecting activity trends in %s...", abs_path)

    if not os.path.exists(abs_path):
        return f"Error: Data file {abs_path} not found."

    user_activity = {}  # user_id -> count

    try:
        # Simple count for now to show activity levels
        with open(abs_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row.get("user_id", "unknown")
                user_activity[uid] = user_activity.get(uid, 0) + 1

        # Sort users by activity
        sorted_users = sorted(user_activity.items(), key=lambda x: x[1])

        output = ["### User Activity Trend Analysis\n"]
        output.append("**Low Activity Users (Potential Churn):**")
        for uid, count in sorted_users[:10]:
            output.append(f"- {uid}: {count} trips in session")

        output.append(f"\nTotal Active Users: {len(user_activity)}")
        return "\n".join(output)

    except Exception as e:
        return f"Error analyzing trends: {str(e)}"
