# Changelog

## [2026-03-26]

### Summary of Bedrock Multi-Region Stability & Execution Hardening
Successfully stabilized the agentic system for **Amazon Bedrock inference profiles**, specifically targeting the Tokyo (`ap-northeast-1`) region using `apac.` regional IDs. Hardened the execution environment by resolving **sandbox isolation** (enabling Coder/Ops to share state) and **branch duplication** (replacing Aider's auto-branching with a clean AES commit strategy). This update ensures 100% git continuity and resource efficiency across complex multi-step tasks.

### Added
- **APAC Regional Support**: Whitelisted `apac.` and `jp.` prefixes for Bedrock models and reconfigured the system for Tokyo regional inference profiles.
- **Manual Commit Protocol**: Added a manual git commit layer in `src/tools/e2b_aider_tool.py` using `--no-auto-commits`, preventing Aider from creating redundant `feature/` branches.

### Modified
- **Sandbox Reuse Logic**: Updated `src/nodes/ops.py` to pass the `sandbox_id` to verification tasks, enabling agents to interoperate within the same microVM.
- **Claude 3.7 Thinking Integration**: Standardized the use of `thinking` blocks and `budget_tokens` configuration in the E2B aider tool.
- **Config Management**: Updated `src/core/config_manager.py` to handle dynamic prefix stripping for Bedrock cross-region inference IDs.

### Fixed
- **Branch Duplication**: Resolved a race condition where Aider would create a parallel branch for task "staging," misaligning the local and remote repo states.
- **Sandbox Redundancy**: Eliminated a bug where the `ops` node would spawn a fresh sandbox for every verification step, losing the Coder's build artifacts.
- **Bedrock Connectivity**: Fixed model resolution errors for `anthropic.claude-3-7-sonnet-20250219-v1:0` when invoked via inference profiles.

## [2026-03-25]

### Summary of Persona-Driven Architecture & Verification Hardening
Successfully modernized the agentic execution environment by transitioning to a **git-native, persona-driven Aider model**. This update eliminates fragile MCP tool-calling hallucinations by delegating file operations to Aider's native engine. Implemented a **Strict Verification Gate** in the Supervisor to ensure that all Coder-led reworks are finalized and signed off by the Ops agent before step completion.

### Added
- **Re-Verification Guard**: Implemented logic in `src/core/supervisor.py` that forces a routing back-pass to the Ops agent after any Coder rework, ensuring that "Success" is only granted by the verification specialist.
- **Language-Agnostic Stack Detection**: Hardened the system to support Python, JS, Go, Rust, and Terraform with automated execution context detection.
- **Three-Strike Diagnostic Loop**: Standardized the Ops agent's ability to perform deep environmental diagnostics in E2B sandboxes using language-idiomatic verification scripts.

### Modified
- **Persona Hardening**: Completely refactored `src/agents/coder.yaml` and `src/agents/ops.yaml` to be git-native and removed all "Allowed Tools" metadata to prevent hallucinated tool calls in source code.
- **Config Loader Update**: Refactored `src/core/config_loader.py` to suppress the injection of tool lists into system prompts, supporting the "Identity-Only" prompt strategy.
- **Supervisor Routing**: Updated the deterministic step resolver to check `execution_history` for agent-specific sign-offs.

### Fixed
- **Tool-Call Hallucinations**: Resolved critical issues where the Coder agent would attempt to write meta-instructions (bash commands, tool calls) into implementation files.
- **Premature Step Completion**: Fixed a bug where successful Coder reworks would bypass final Ops validation.

## [2026-03-23]

### Summary of System Reliability & Multi-Repo Robustness
Successfully implemented a robust file-patching system and dynamic branch resolution engine. These updates eliminate "SEARCH/REPLACE" mismatch errors caused by LLM hallucinations and ensure compatibility across repositories using `main`, `master`, or custom default branches. Hardened security by blocking direct commits to critical branches and improved observability through refined logging and exception handling.

### Added
- **Dynamic Branch Resolution**: Implemented `_get_default_branch` in `src/tools/github.py` to query the GitHub API, allowing PRs and branches to target the correct repository-specific default branch automatically.
- **Fuzzy Patching Fallback**: Added a normalization layer to `restricted_replace_in_file` in `src/tools/codebase_tools.py` that ignores superficial whitespace/indentation differences when applying diffs.
- **Flexible Tag Support**: Updated the patching regex to support common LLM hallucinations like `>>>>>>> UPDATED`, `>>>>>>> DONE`, and `>>>>>>> REPLACEMENT`.

### Modified
- **Coder Instruction Set**: Updated `src/agents/coder.yaml` with strict "Single Block Constraints" and unified SEARCH/REPLACE formatting rules.
- **Auto-Connect Logic**: Integrated `_ensure_mcp_connection` across all GitHub tools to prevent mid-task disconnection errors.
- **Security Hardening**: Updated `src/core/resource_manager.py` to strictly block direct `create_or_update` operations on `main` or `master` branches, enforcing feature-branch-only workflows.

### Fixed
- **ContextVar Cleanup Errors**: Suppressed noisy `ValueError` and `LookupError` during async session cleanup in `src/core/mcp_client.py`.
- **Linting & Stability**: Resolved over a dozen Pydantic, Pylint, and Pyright warnings across the `tools/` and `core/` layers, including f-string vs lazy logging consistency.
- **PR Base Target**: Fixed a bug where `create_pull_request` defaulted to `main`, causing validation failures on older `master`-based repositories.

## [2026-03-19]

### Summary of Traceability & Resource Resilience
Successfully resolved initialization errors in **Langfuse Tracing** and hardened the **ResourceManager** to prevent "AttributeError" and "Unexpected keyword" crashes during task cleanup. Refined the **CLI interactive loop** to ensure seamless handoffs between the Supervisor and Planning nodes.

### Modified
- **Tracing Initialization**: Updated `src/core/tracing.py` to use environment variables for `secret_key` and `host`, resolving constructor signature mismatches.
- **Main Execution Loop**: Fixed `main.py` to propagate `thread_id` and `user_id` via LangChain metadata for accurate trace attribution.
- **Ops Node Stability**: Corrected the `ResourceManager` cleanup logic in `src/nodes/ops.py` to properly await the `cleanup()` method.

## [2026-03-19]

### Summary of Agentic Architecture Overhaul & Tracing Integration
Implemented a major architectural upgrade to the core orchestration layer. Introduced **Langfuse Tracing** for deep observability across the agentic graph and the **ResourceManager** for managing ephemeral GitHub/GDrive contexts. Standardized all agent nodes (`planning`, `coder`, `ops`, `growth`) to use native `RunnableConfig` for tracing and metadata propagation.

### Added
- **Langfuse Observability**: Deployed `src/core/tracing.py` and integrated `CallbackHandler` across all LLM and tool-calling boundaries.
- **Unified Resource Manager**: Introduced `src/core/resource_manager.py` to handle remote file access, smart context discovery, and automated workspace cleanup.
- **Ingestion Pipeline**: Deployed `src/core/ingestion.py` to consolidate repository analysis and semantic indexing.
- **Google Drive Tooling**: Added `src/tools/gdrive.py` for direct document operations through MCP.
- **Task Cleanup Node**: Introduced `src/nodes/cleanup.py` to systematically prune transient stores and workspaces after completion.

### Modified
- **Orchestration Nodes**: Fully refactored `src/nodes/` to pass `config` through all `ainvoke` and tool calls.
- **State Schema Expansion**: Updated `EngineeringState` with `branch_name`, `is_lightweight`, and `active_step_id` for deterministic execution tracking.
- **Supervisor Workflow**: Overhauled `supervisor.yaml` and `supervisor.py` for plan-driven multi-step orchestration.

### Fixed
- **Search/Replace Block Hallucination**: Hardened the `coder.yaml` instructions to prioritize exact whitespace matches and first-occurrence patches.
- **Import Path Consistency**: Resolved lingering `ModuleNotFoundError` issues by enforcing absolute imports across the entire `src/` directory.

## [2026-03-16]

### Summary of MCP Expansion & RAG Optimization
Standardized the system to use the Model Context Protocol (MCP) for both context retrieval and action-oriented tasks. Integrated the **GitHub MCP Server** for issues/PR management and the **Google Drive MCP Server** for remote document discovery. Optimized the **RAG Evolution Engine** to benchmark against real remote data sources and resolved critical asynchronous test failures in the core orchestration nodes.

### Added
- **GitHub MCP Integration**: Integrated the official GitHub MCP server to provide agents with tool-based access to repository management (issues, comments, PRs).
- **Google Drive MCP Integration**: Added support for remote Google Drive content discovery via MCP, decoupling the system from local storage requirements.
- **Remote RAG Evaluation**: Retooling the `evaluate_rag.py` and `ingest_eval_data.py` to index and test against live remote sources (GitHub/GDrive).
- **MCP Client Manager**: Implemented `src/core/mcp_client.py` to provide a centralized, async context manager for managing multiple MCP server connections simultaneously.

### Modified
- **Asynchronous Test Standard**: Migrated `coder`, `manual`, and `ops` deterministic tests to `anyio`-compatible async tests to resolve persistent `AttributeError` and `TypeError` issues.
- **RAG Ingestion Routine**: Updated ingestion pipelines to prefer remote MCP-provided tools over legacy local fetchers for better architectural consistency.
- **Secret Management Consistency**: Hardened `webhooks.py` to gracefully handle Pydantic `SecretStr` objects across all deployment environments.
- **Evaluation Preservation**: Refined `reset_db.py` to ensure evaluation datasets and results are preserved during system resets while correctly clearing vector and graph stores.

### Fixed
- **Async Mock Chaining**: Resolved "coroutine object has no attribute" errors in `tests/test_ops_deterministic.py` by correctly shimming synchronous LangChain tool manipulation methods.
- **Webhook Signature Validation**: Fixed HMAC validation failures caused by incorrect `SecretStr` handling.
- **Linter Compliance**: Eliminated unused variable warnings and `FieldInfo` access errors in the API and test layers.


## [2026-03-13]

### Summary of MCP Integration & Structural Graph Discovery
Successfully integrated the **Model Context Protocol (MCP)** to expose the "Smart Context" capabilities as standardized tools. Developed a modular MCP server using **FastMCP**, enabling external agents to interface with the knowledge engines. Enhanced the **Kùzu Graph Engine** with structural schema discovery and hardened system logging for stdio-based protocol stability.

### Added
- **MCP Server Implementation**: Deployed a dedicated modular server in `src/mcp_server/` leveraging the **FastMCP** framework. Includes specialized handling for health checks, tool registration, and resource management.
- **Graph Schema Discovery**: Implemented `GraphStore.get_schema()` to return a complete structural map of Kùzu node/relationship tables, properties, and connections, aiding agentic graph navigation.
- **MCP Operations Infrastructure**: Added `make run-mcp` and `make inspect-mcp` to the `Makefile` to streamline server lifecycle management and protocol inspection.

### Modified
- **Logging for Stdio Compatibility**: Refactored `src/utils/logger.py` to route all diagnostic logs to `sys.stderr`, ensuring the `sys.stdout` stream remains reserved for MCP JSON-RPC communication.
- **License Header Skill**: Overhauled `.agent/skills/license-header-adder/SKILL.md` with support for multi-language comment syntax (C-style, Hash-style, XML-style) and refined procedural instructions.
- **System Dependencies**: Added `mcp[cli]` to `pyproject.toml` and synchronized `uv.lock` to support the new protocol layers.

### Removed
- **Evaluation Artifact Clean-up**: Purged legacy evaluation data (`results.csv`, `metrics_summary.png`) and isolated vector stores to maintain workspace cleanliness.

## [2026-03-12]

### Summary of RAG Evaluation Framework
Implemented a comprehensive evaluation pipeline using **Ragas 0.4.x** to quantitatively assess the accuracy, relevancy, and faithfulness of the Smart Context retrieval system. Established a baseline for performance using synthetic test data and automated result visualization.

### Added
- **RAG Evaluation Suite**: Deployed an isolated evaluation environment in `evaluation/rag/` including scripts for ingestion, synthetic testset generation, and multi-metric scoring.
- **Evaluation Automation**: Created `scripts/eval_rag.sh` and integrated `make eval-rag` to orchestrate end-to-end benchmarking in a single command.
- **Automated Visualization**: Implemented a radar plot generator (`metrics_summary.png`) to provide visual feedback on Faithfulness, Answer Relevancy, Context Precision, and Context Recall.
- **Evaluation Isolation**: Hardened `reset_db.py` and `Makefile` to manage isolated ChromaDB and Kùzu stores specifically for evaluation runs.

### Fixed
- **Ragas 0.4.x Compatibility**: Resolved `TypeError` and `AttributeError` by shimming legacy `embed_query` and `embed_documents` methods onto modern OpenAI embedding providers.
- **Token Management**: Fixed response truncation by increasing context-aware `max_tokens` for Ragas LLM calls.
- **Result Aggregation**: Resolved data-type reduction errors in result processing by enforcing numeric conversion for aggregate scores.
- **Reset Logic**: Fixed an issue where `evaluation/graph` was not being correctly cleared during full system resets.

### Evaluation Baseline (Dummy Data)
- **Context Recall**: 0.958 (Excellent retrieval coverage)
- **Faithfulness**: 0.866 (High output groundedness)
- **Answer Relevancy**: 0.804 (Strong intent alignment)
- **Context Precision**: 0.507 (High noise-to-signal ratio; identified for future reranking)

## [2026-03-11]

### Summary of Knowledge Ingestion & Advanced Retrieval
Successfully expanded the **Smart Chunker** to support document sources (PDFs, Google Docs, Google Sheets) and transitioned the system to a hybrid knowledge store. Integrated **Kùzu Graph Database** for structural code relationships and **ChromaDB** for semantic search. Developed the **ContextRetriever** module to perform graph-augmented retrieval, enabling agents to leverage cross-file and cross-class context.

### Added
- **Unified Knowledge Store**: Integrated **Kùzu** (`GraphStore`) and **ChromaDB** (`VectorStore`) as the dual-engine backbone for long-term memory and repository context.
- **Multi-Source Smart Chunkers**: Deployed specialized engines for `PDF` (heuristic heading detection), `Google Docs` (hierarchical structural parsing), and `Google Sheets` (tabular context injection).
- **Language-Aware Code Engine**: Enhanced the code chunker to support **Java** and **Kotlin**, extracting `CALLS` and `INHERITS` relationships using Tree-sitter.
- **Advanced Retrieval Module**: Implemented `ContextRetriever` which performs hybrid search (semantic hit + graph neighbor expansion) to provide 10x richer context to agents.
- **Ingestion Pipeline**: Created a unified `src/ingestion/pipeline.py` and `fetcher.py` to automate the discovery, fetching, and indexing of entire repositories and document folders.
- **Persistence Layer Refactoring**: Migrated `LongTermMemory` and `WorkspaceManager` to use the new unified stores, ensuring data isolation through dedicated ChromaDB collections.

### Fixed
- **Cross-Language Relationship Mapping**: Resolved Tree-sitter query issues for Java/Kotlin that were causing incorrect symbol identification.
- **Memory Consistency**: Fixed an issue where legacy memories were being mixed with repository context by introducing isolated collection namespaces in the `VectorStore`.

## [2026-03-10]

### Summary of Smart Chunker: Universal Code Chunker
Successfully implemented the core engines for the **Smart Chunker**, a decoupled and modular module designed for high-precision code and documentation ingestion. Developed specialized engines for Python (AST-aware), Markdown (structural), and Jupyter Notebooks, ensuring complete context preservation during the chunking process.

### Added
- **Decoupled Module Structure**: Created `src/smart_chunker/` as a standalone package with separate `base`, `schemas`, and `engines` layers for clean internal integration.
- **Python AST Engine**: Integrated `Tree-sitter` for production-grade parsing, enabling extraction of atomic symbols (classes/functions) and inheritance tracking.
- **Markdown Structural Engine**: Implemented heading-based splitting (H1-H3) that preserves "breadcrumb" paths for hierarchical context.
- **Jupyter Notebook Engine**: Added support for `.ipynb` files, extracting code cells and processing them through the Python AST pipeline with cell-index metadata.
- **Recursive Splitting Logic**: Introduced a context-aware splitting mechanism that breaks large code blocks while prepending signatures to prevent context loss.
- **Production Test Suite**: Deployed `tests/test_smart_chunker.py` and `tests/data/` with multi-language sample files (Python, JS, PHP, Dart, MD) for end-to-end verification.

### Fixed
- **Environment Compatibility**: Resolved a `TypeError` in `tree-sitter-languages` by standardizing the `.venv` on `tree-sitter==0.21.3`.
- **Hierarchical Indexing**: Resolved Pydantic validation issues by standardizing `chunk_index` as a string (e.g., "1.0", "1.1") to support nested symbol mapping.
- **Dependency Map Noise**: Refined dependency extraction to exclude self-references and focus on external symbol markers (TitleCase identification).
- **Import Portability**: Switched to absolute imports within the module to ensure compliance with standard Python packaging requirements.

## [2026-03-09]

### Summary of Smart Context Manager: Phase 1 (Source Discovery)
Successfully initiated the "Smart Context Manager" project to enhance AI agent context gathering. Implemented and verified **Phase 1: Source Discovery & Identification**, establishing a unified engine that identifies and health-checks diverse data sources (GitHub, Google Docs/Sheets, Slack, PDFs) before ingestion.

### Added
- **Unified Ingestion Module**: Created `src/ingestion` with `SourceIdentifier` logic for robust URL and path classification.
- **API Connector Strategy**: Integrated live health checks for GitHub (OAuth Token) and Google Drive (Service Account JSON) to verify accessibility.
- **Centralized Ingestion Schemas**: Deployed `src/schemas/ingestion.py` to provide a common Pydantic-based language for all data sources.
- **Extended Configuration**: Updated `config/default.yaml` and `src/core/config.py` with structured `ingestion.connectors` parameters.
- **Secrets Management**: Added placeholders for `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` and `SLACK_BOT_TOKEN` in `.env` (guarded by `.gitignore`).

### Fixed
- **Google API Integration**: Resolved environment-specific library gaps by installing `google-api-python-client` and related auth handlers.
- **Path Resolution**: Fixed relative path handling for service account keys to ensure reliable initialization across different execution environments.

## [2026-03-06]

### Summary of AWS Bedrock Integration & Multi-Provider Capability
Successfully integrated AWS Bedrock into the core system architecture, transitioning from an OpenAI-only model to a flexible, multi-provider engine. Implemented a dynamic factory in the `ConfigManager` that allows any agent to be configured with either OpenAI or Bedrock models (Anthropic, Meta, DeepSeek) via simple YAML settings.

### Added
- **AWS Bedrock Core Integration**: Deployed `ChatBedrockConverse` support across the entire agentic graph.
- **Multi-Provider LLM Factory**: Upgraded `ConfigManager` to dynamically initialize and route LLM requests based on `provider` tags.
- **DeepSeek Support**: Verified and integrated `deepseek.v3-v1:0` as a high-performance alternative model on Bedrock.
- **Tokyo Region Deployment**: Pin-pointed `ap-northeast-1` as the default region for minimal latency and regional compliance.
- **Structured Debug Logging**: Introduced "Robot" telemetry logs (`🤖 [Agent] -> [Provider] | [Model]`) to provide real-time visibility into LLM routing.

### Fixed
- **Legacy Model Dead-ends**: Eliminated `ResourceNotFoundException` by migrating to modern Converse-compatible IDs (Claude 3.5 Sonnet, Llama 3).
- **Retry Validation Errors**: Resolved `max_retries` initialization warnings in Bedrock clients by handling provider-specific parameter schemas.

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
