# Agentic Engineering System (Prototype)

This is a prototype multi-agent system designed to orchestrate complex engineering tasks using specialized autonomous agents (Planning, Coder, Ops, and Growth).

> [!WARNING]
> This is a **Prototype**. Most agent actions are currently mocked to demonstrate the end-to-end workflow, routing logic, and state persistence.

## 🚀 Getting Started

### 1. Prerequisites
- [uv](https://github.com/astral-sh/uv) (Highly recommended for dependency management)
- Python 3.11+

### 2. Setup
Clone the repository and install dependencies:
```bash
make install
```

### 3. Environment Configuration
Copy the example environment file and add your API keys:
```bash
cp .env.example .env
```
*At minimum, you need an `OPENAI_API_KEY` to run the supervisor and agents.*

### 4. Running the System
Start the interactive CLI to chat with the Chief Orchestrator:
```bash
make run
```

## 🏗️ Architecture
The system uses **LangGraph** to manage the state machine and agent handoffs:
- **Supervisor**: The "brain" that routes tasks to specialized agents.
- **Planning Agent**: Designs technical architecture and implementations.
- **Coder Agent**: Implements code changes and fixes.
- **Ops Agent**: Handles testing, verification, and deployment.
- **Growth Agent**: Analyzes user needs and proposes strategy.

## 🛠️ Development
- `make lint`: Run code quality checks.
- `make format`: Auto-format source code.
- `make ingest`: Ingest codebase context into the long-term memory (ChromaDB).
- `make reset-db`: Wipe the local SQLite database (`engineering_agents.db`) and evaluation stores.

## 📊 RAG Evaluation
The system includes an automated evaluation pipeline using **Ragas** to measure retrieval and generation quality.

- `make eval-rag`: Run the full evaluation pipeline (Ingest -> Generate Testset -> Evaluate).
- **Results**: Detailed scores for Faithfulness, Relevancy, Precision, and Recall are saved to `evaluation/data/results.csv`.
- **Visualization**: A radar plot of the aggregate metrics is generated at `evaluation/data/metrics_summary.png`.

## 📝 Quick Example
Here is what a typical end-to-end task looks like in the terminal:

```bash
👤 User Request: need to improve the accuracy of ml model

INFO: Identified relevant repository: mobile-predictor
INFO: Supervisor decided: NodeName.PLANNING (Reason: No existing plan)
INFO: Planning Agent generated plan (Auto-approved)
INFO: Supervisor decided: NodeName.CODER (Reason: Plan is approved)
INFO: Coder Agent executing code changes...
INFO: Supervisor decided: NodeName.OPS (Reason: Testing is required)
INFO: Ops Agent verifying implementation...
INFO: Supervisor decided: NodeName.FINISH (Reason: All tests passed)

✅ Task Processing Complete.
```

## ⚙️ Configuration

The system uses a layered YAML configuration system located in the `config/` directory.

### Switching Environments
The environment is determined by the `APP_ENV` variable. You can set it in two ways:

1.  **In `.env` file** (Recommended):
    ```env
    APP_ENV=prod
    ```
2.  **Via shell**:
    ```bash
    export APP_ENV=prod
    ```

### How it works
1. **`default.yaml`** is loaded first for baseline settings.
2. **`{APP_ENV}.yaml`** is loaded next, overriding specific values.
3. **`.env`** is used for sensitive secrets like `OPENAI_API_KEY` and the `APP_ENV` toggle.