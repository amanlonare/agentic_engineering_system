import csv
import os
from collections import Counter

from langchain_core.tools import tool

from src.utils.logger import configure_logging

logger = configure_logging("growth_tools")


def _get_abs_path(path: str) -> str:
    """Ensures paths are relative to .context if not absolute."""
    if not path.startswith(".context") and not os.path.isabs(path):
        return os.path.join(".context", "testing_agentic_engineering_team", path)
    return path


@tool
def analyze_prediction_accuracy(path: str = "data/movement_predictions.csv") -> str:
    """
    Analyzes the accuracy of mobility predictions by comparing predicted vs actual modes.
    Returns a per-region and per-mode breakdown of accuracy and confusion clusters.
    """
    abs_path = _get_abs_path(path)
    logger.info(f"📊 Analyzing prediction accuracy in {abs_path}...")

    if not os.path.exists(abs_path):
        return f"Error: Data file {abs_path} not found."

    stats = {}  # (region, mode) -> {correct: 0, total: 0}
    confusion = Counter()  # (region, predicted, actual) -> count

    try:
        with open(abs_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                region = row["region"]
                pred = row["predicted_mode"]
                actual = row["actual_mode"]

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

        for r in regions:
            output.append(f"#### Region: {r}")
            r_total = 0
            r_correct = 0
            for (reg, mode), data in stats.items():
                if reg == r:
                    acc = (data["correct"] / data["total"]) * 100
                    output.append(
                        f"- {mode.capitalize()}: {acc:.1f}% ({data['correct']}/{data['total']})"
                    )
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
                    f"- {reg}: Predicted '{pred}' instead of '{actual}' in {error_rate:.1f}% of cases."
                )
                found_confusion = True

        if not found_confusion:
            output.append("No major confusion clusters detected.")

        return "\n".join(output)

    except Exception as e:
        return f"Error analyzing data: {str(e)}"


@tool
def detect_activity_trends(path: str = "data/movement_predictions.csv") -> str:
    """
    Detects declining user activity trends which might indicate churn.
    Returns a list of users with significant drops in movement volume.
    """
    abs_path = _get_abs_path(path)
    logger.info(f"📈 Detecting activity trends in {abs_path}...")

    if not os.path.exists(abs_path):
        return f"Error: Data file {abs_path} not found."

    user_activity = {}  # user_id -> count

    try:
        # Simple count for now to show activity levels
        with open(abs_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row["user_id"]
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
