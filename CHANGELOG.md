# Changelog

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
