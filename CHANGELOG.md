# Changelog

## [2026-02-24]

### Added
- **Interactive CLI**: Dynamic communication loop with task-specific threads and automated repository discovery using RAG.
- **Workflow Orchestration**: Refined Supervisor routing logic with loop prevention and strict persona-driven handoffs (Planning -> Coder -> Ops).
- **Branding & Context**: Complete transition to the "Mobile" naming convention across all system prompts and `.context` README files.
- **Persona System**: YAML-based configuration for Planning, Coder, Ops, and Growth agent identities.
- **Onboarding Assets**: Comprehensive `README.md` with system examples and `.env.example` for environment setup.
- **State Persistence**: SQLite-based checkpointer integration for long-term task memory and session continuity.
- **Verification Walkthrough**: Detailed technical walkthrough and daily status reporting infrastructure.
