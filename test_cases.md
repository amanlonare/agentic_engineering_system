# Agentic Engineering System - Test Cases

This document outlines various test queries to verify the orchestration logic, agent routing, and tool capabilities of the LangGraph multi-agent system.

To run these tests:
1. Ensure your environment is set up (`make install`, `.env` configured).
2. Start fresh by running: `make reset-db`
3. Start the system: `make run`
4. Paste the queries exactly as written below.

---

## Scenario 1: Standard Feature Flow (Planner -> Coder -> Ops)
**Query:**
> "We need a new GET endpoint in the mobile backend that returns a user's active subscription status."

**Expected Output & Agent Behavior:**
1. **Supervisor** analyzes the request and routes the task to the **Planning Agent** for the `mobile-backend`.
2. **Planning Agent** reads `.context/architecture_map.md` (and strictly NOTHING else) to determine that the endpoint should live in `app/api/users.py`.
3. **Planning Agent** generates a structured `TechnicalPlan` outlining the changes and returns.
4. **Supervisor** sees the approved plan and routes the implementation to the **Coder Agent**.
5. **Coder Agent** reads `app/api/users.py`, mocks the code changes based on the Planner's instructions, and returns.
6. **Supervisor** routes the task to the **Ops Agent** for verification.
7. **Ops Agent** runs (mocked) unit tests, confirms success, and returns.
8. **Supervisor** routes to `FINISH` and completes the task.

---

## Scenario 2: Direct Verification (Supervisor -> Ops)
**Query:**
> "Please review the security of how we hash passwords in the backend authentication logic."

**Expected Output & Agent Behavior:**
1. **Supervisor** analyzes the request. Realizing this is a request for an audit/review rather than a new feature build, it **skips the Planner and Coder**.
2. **Supervisor** routes directly to the **Ops Agent** (or in some prompt variations, the Coder for review).
3. The assigned agent reads `architecture_map.md` to find that security logic lives in `.context/mobile-backend/app/core/security.py`.
4. The agent reads the contents of `security.py`, analyzes the mock hashing functions, and outputs a terminal response evaluating the security logic.
5. Task completes successfully.

---

## Scenario 3: Cross-Functional Analysis (Supervisor -> Growth)
**Query:**
> "Look at our mobile app analytics. Are users dropping off when they hit the login screen, or is it a backend authentication failure?"

**Expected Output & Agent Behavior:**
1. **Supervisor** parses strategic keywords ("analytics", "dropping off", "failure") and correctly routes the entirely non-code task to the **Growth Agent**.
2. **Growth Agent** reads `architecture_map.md` to identify the relevant files (`AnalyticsService.js` and `auth.py`).
3. **Growth Agent** reads those mock files and formulates a strategic report combining frontend tracking and backend error patterns.
4. The final output is a strategic recommendation rather than a code plan.

---

## Scenario 4: Missing Context / Out of Scope Graceful Failure
**Query:**
> "Write me a smart contract in Solidity for the Ethereum blockchain."

**Expected Output & Agent Behavior:**
1. **Supervisor** checks the available mock repositories in the system.
2. It determines that none of the available repositories (`mobile-app`, `mobile-backend`, `mobile-predictor`, etc.) have block-chain or solidity contexts.
3. The system gracefully responds to the user stating that it does not have the context or capabilities to fulfill the request within the current workspace limitations, terminating quickly without wasting agent API calls.
