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