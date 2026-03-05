# Changelog

## [2026-03-05]

### Summary of Prompt Enhancements & Growth Capabilities
Successfully refined the strictness of the Planning and Coder agents via prompt optimizations, drastically improving reliability across the architecture. Hardened testing pathways to ensure robust cross-agent cooperation, integrated persistent Growth Agent recommendations, and validated the system end-to-end on diverse architectural tasks.

### Added
- **Strict Anti-Guessing Rule**: Enforced a "Never Guess Imports" rule in `coder.yaml`, requiring the Coder to natively scrape implementation files before attempting to write verification scripts.
- **Persistent Growth Integration**: Established long-term state persistence for business and analytics insights (`accumulated_growth_notes`), which seamlessly inject into Git Ops commits despite intermediate memory resets.
- **Universal Test Path Standardization**: Pinned all Verification scripts across Planning, Coder, and Ops agents to the root `tests/` directory to permanently eradicate path mismatch errors.

### Fixed
- **Testing Import Errors**: Eliminated hallucinatory `ImportErrors` during Ops verification by forcing the Coder to definitively verify exported function/class names before testing.
- **Ops Infinite Loop Prevention**: Deployed a "Success Override" fallback in `ops.py` to intercept code 0 test scripts misinterpreted as LLM failures.

## [2026-03-04]

### Summary of Configuration System & Lightweight Task Mode Rollout
Successfully migrated the entire project away from hardcoded settings to a flexible, environment-aware YAML configuration system. Additionally, implemented a "Lightweight Task Mode" to streamline execution for simpler tasks, avoiding unnecessary scaffolding and rigorous structural validation protocols. 

### Added
- **Dynamic Configuration Management**: Introduced `ConfigManager` to aggregate settings automatically across `default.yaml` and environment-specific overrides (`dev.yaml`, `staging.yaml`, `prod.yaml`).
- **Unified Environment Settings**: Merged secrets control via `.env` with explicit values specified in YAML configuration files, improving transparency over system variables.
- **Ops Agent Configuration**: Officially mapped the Ops Agent parameters (e.g. `verification_timeout`, `max_rework`, LLM configs) into the fully centralized YAML configurations.
- **Lightweight Task Tracking**: Injected an `is_lightweight` heuristic into the Supervisor, detecting low-complexity prompts automatically based on keywords and missing repositories.
- **Protocol Bypasses**: The Planning and Coder personas now explicitly skip demanding mocking routines (e.g. boto3/requests verification templates) when operating under the "Lightweight Task Protocol".

### Fixed
- **Pytest Instabilities**: Re-linked legacy test frameworks (`test_ops_deterministic.py`, `test_webhook.py`) to the new unified `ConfigManager`, resolving outdated mock `AttributeError` tracebacks.
- **Orchestration Boilerplate Issues**: Lightweight Mode prevents infinite scaling or looping issues on simple commands (like basic bash outputs) by using direct execution scripts instead of deep verification templates.
- **Extraneous Module Loading**: Systematically eliminated the obsolete `src/providers` directory and references, saving computational overhead during LLM initialization across agents.

## [2026-03-03]

### Summary of GitHub Webhook Integration & Routing Optimizations
Successfully implemented a production-ready GitHub Issues webhook integration. Resolved critical API failures related to database connection management and optimized repository routing to eliminate cross-repo "hallucinations" during multi-step tasks.

### Added
- **GitHub Webhook Integration**: New FastAPI layer (`/webhooks/github`) to synchronously trigger the agentic graph from GitHub events.
- **HMAC-SHA256 Validation**: Implemented secure payload verification using GitHub secrets.
- **Deterministic Routing**: Enhanced `WorkspaceManager` with keyword-based prioritization (e.g., "Agentic Team") to prevent semantic misrouting.
- **Explicit Repo Mapping**: Updated `architecture_map.md` with explicit `[ID]` tags for unambiguous repository identification by the Planner.
- **Lifecycle Management**: Refactored `SqliteSaver` initialization to use a generator-based dependency, fixing internal server errors.

### Fixed
- **403 Forbidden**: Resolved signature mismatches by enforcing strict `application/json` parsing.
- **500 Internal Error**: Fixed an incorrectly handled context manager in the LangGraph checkpointer initialization.
- **Infinite Execution Loops**: Blocked redundant rework cycles by providing the Supervisor with explicit failure context from the Ops agent.


## [2026-03-02]

### Summary of Ops Agent Completion & Resilience Fixes
Finalized the Ops agent and integrated a robust sandbox execution environment. Implemented deterministic loop prevention and language-agnostic verification strategies to handle complex enterprise repositories and empty states.

### Added
- **Ops Agent Integration**: Fully functional `ops_node` that validates Coder outputs using repository-locked tools.
- **Execution Runner**: Integrated `run_command` to execute verification scripts (Python, Node.js) in a restricted sandbox.
- **Pre-loaded Repo Tree**: Optimized Coder start-up by pre-injecting the directory structure, eliminating redundant discovery calls.
- **Tiered Verification**: Added support for language-native execution (Python/JS) and structural verification fallbacks.

### Fixed
- **ModuleNotFoundError**: Resolved by enforcing `sys.modules` mocking for 3rd-party dependencies in verification scripts.
- **Deterministic Loop Prevention**: Implemented turn-based tool history to block oscillating or redundant tool calls.



## [2026-02-27]

### Summary of Coder Agent Completion & Orchestration Fixes
Successfully finalized the Coder agent's tool-calling loop and least-privilege scoping. Resolved infinite orchestration loops by introducing structured step tracking and a visual progress checklist for the Supervisor.

### Added
- **Coder Agent Implementation**: Fully operational `coder_node` with a tool-calling loop, `MAX_TOOL_CALLS` safety cap, and repo-locked tools (`write_file`, `read_file`, `list_directory`).
- **Structured Step Tracking**: Introduced `StepExecutionRecord` to capture granular outcomes (agent, status, outcome summary) for every engineering step.
- **Supervisor Visual Checklist**: The Supervisor now formats the Technical Plan as a clean `[x]/[ ]` checklist, providing the LLM with definitive progress context.
- **Strict Step Compliance**: Optimized Coder and Ops nodes to strictly follow assigned `Step IDs`, preventing "guessing" or premature step advancement.

### Fixed
- **Conversation Sequence Integrity**: Fixed a bug where empty AI messages with `tool_calls` were being filtered out, breaking the OpenAI message sequence.
- **Orchestration Loop Redundancy**: Eliminated "blind" re-routing by ensuring the Supervisor and Workers share the same structured execution history.


## [2026-02-26]

### Major Enhancements: Tool Integration & Plan-Aware Orchestration
We shifted the system from a rigid "Planning -> Coder" flow to a dynamic, plan-driven model where the Supervisor dispatches work based on a structured TechnicalPlan.

### Added
- **Plan-Aware Orchestration**: The Supervisor now cross-references the `TechnicalPlan` with `completed_step_ids` to dynamically route to the next assigned agent.
- **Structured Plan Data**: Implemented `.model_dump()` in the orchestration loop to provide the Supervisor with clean, machine-readable JSON context instead of generic strings.
- **Step Completion Tracking**: Workers (Coder/Ops) now report their specific `step_id` completion to the system state.
- **Deterministic Testing Suite**: Added isolated testing scripts to verify Supervisor and Planning logic without running the full graph.

### Fixed
- **Missing Task Description**: Resolved a bug where the user's initial request was lost during transition to the Planning node.
- **Persona Tooling**: Standardized tool binding across all agents, ensuring `read_file`, `search_codebase`, and `list_directory` are available globally.

## [2026-02-25]

### Summary of Major Architectural & Reliability Enhancements
Today's updates focused on stabilizing the multi-agent orchestration loop, eliminating hallucinations through stricter context control, and implementing professional-grade error handling and observability.

### Added
- **Global Error Handling Framework**: Introduced `error_message` state tracking across all nodes (Planning, Coder, Ops, Growth). The Supervisor now performs a "Priority 0" safety check to halt execution immediately on failure, preventing infinite retry loops.
- **Context-Bound Planning Node**: Completely removed tool-calling loops from the Planning agent. It now operates as a pure Solution Architect using strictly filtered architecture context injected via Python, ensuring 100% predictable research.
- **Growth Agent Integration**: New specialized agent and schema for analyzing business metrics and triggers (engagement, churn, promotions), providing high-level strategy signals to the Supervisor.
- **Repository Context Filtering**: Implemented regex-based context injection that hides irrelevant repository documentation from the agent, drastically reducing cross-repository hallucinations.
- **Agent Prompt Engineering**: Crafted high-fidelity system prompts and personas for Planning, Supervisor, and Growth agents, ensuring strict adherence to zero-tool constraints and structured output schemas.

### Fixed
- **Persona Hallucinations**: Resolved issue where agents would fallback to generic templates
- **Schema Compliance**: Fixed several "AttributeErrors" in terminal logging where agents were attempting to access deprecated or incorrect metadata fields.
- **Codebase Cleanliness**: Performed a global refactoring pass to standardize Pydantic v2 syntax, import ordering, and whitespace across all core modules.

## [2026-02-24]

### Added
- **Interactive CLI**: Dynamic communication loop with task-specific threads and automated repository discovery using RAG.
- **Workflow Orchestration**: Refined Supervisor routing logic with loop prevention and strict persona-driven handoffs (Planning -> Coder -> Ops).
- **Branding & Context**: Complete transition to the "Mobile" naming convention across all system prompts and `.context` README files.
- **Persona System**: YAML-based configuration for Planning, Coder, Ops, and Growth agent identities.
- **Onboarding Assets**: Comprehensive `README.md` with system examples and `.env.example` for environment setup.
- **State Persistence**: SQLite-based checkpointer integration for long-term task memory and session continuity.
- **Verification Walkthrough**: Detailed technical walkthrough and daily status reporting infrastructure.
