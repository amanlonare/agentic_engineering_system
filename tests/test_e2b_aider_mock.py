import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest

from src.tools.e2b_aider_tool import run_aider_in_e2b


@pytest.mark.asyncio
async def test_run_aider_in_e2b():
    print("Testing e2b_aider_tool logic (with mocks)...")

    # Setup environment variables for test
    os.environ["E2B_API_KEY"] = "test_key"
    os.environ["GITHUB_TOKEN"] = "test_token"

    from src.core.config import settings

    # Patch settings and E2B Sandbox
    with (
        patch.object(settings, "E2B_API_KEY", "test_key"),
        patch.object(settings, "GITHUB_TOKEN", "test_token"),
        patch.object(settings, "OPENAI_API_KEY", "test_openai"),
        patch.object(settings, "ANTHROPIC_API_KEY", "test_anthropic"),
        patch("src.tools.e2b_aider_tool.Sandbox") as mock_sandbox_class,
    ):
        mock_sb = MagicMock()
        mock_sandbox_class.create.return_value = mock_sb
        mock_sandbox_class.connect.return_value = mock_sb

        from e2b.sandbox.commands.command_handle import CommandExitException

        # Mock results
        ok = MagicMock(stdout="ok\n", stderr="", exit_code=0)
        sha = MagicMock(stdout="test_sha_12345\n", stderr="", exit_code=0)

        # Exception to simulate failure
        fail_exc = CommandExitException(
            stdout="", stderr="error", exit_code=1, error="Command failed"
        )

        # New Sandbox Case (checks fail, everything installs)
        mock_sb.commands.run.side_effect = [
            fail_exc,  # 1. test -d (get_sandbox)
            ok,  # 2. git clone (get_sandbox)
            fail_exc,  # 3. git checkout (run_aider_in_e2b)
            ok,  # 4. git checkout -b (run_aider_in_e2b)
            ok,  # 5. git config email (_setup_git_identity)
            ok,  # 6. git config name (_setup_git_identity)
            fail_exc,  # 7. aider --version (run_aider_in_e2b)
            ok,  # 8. pip install (run_aider_in_e2b)
            ok,  # 9. aider run (run_aider_in_e2b)
            ok,  # 10. git push (run_aider_in_e2b)
            sha,  # 11. git rev-parse (run_aider_in_e2b)
        ]
        mock_sb.sandbox_id = "new_sb_123"

        result = await run_aider_in_e2b(
            repo_url="https://github.com/owner/repo",
            instructions="Fix the bug",
            fnames=["app.py"],
            branch="fix-bug",
            base_branch="main",
        )

        if not result["success"]:
            print(f"❌ Result failed: {result.get('error')}")
        assert result["success"] is True
        assert result["sandbox_id"] == "new_sb_123"
        assert result["commit_sha"] == "test_sha_12345"

        # Test Reconnect Case (checks pass, skip clone/install/checkout)
        mock_sb.commands.run.side_effect = [
            ok,  # 1. test -d (get_sandbox)
            ok,  # 2. git checkout (run_aider_in_e2b)
            ok,  # 3. git config email (_setup_git_identity)
            ok,  # 4. git config name (_setup_git_identity)
            ok,  # 5. aider --version (run_aider_in_e2b)
            ok,  # 6. aider run (run_aider_in_e2b)
            ok,  # 7. git push (run_aider_in_e2b)
            sha,  # 8. git rev-parse (run_aider_in_e2b)
        ]
        mock_sb.sandbox_id = "existing_sb_456"
        mock_sandbox_class.connect.return_value = mock_sb

        result_2 = await run_aider_in_e2b(
            repo_url="https://github.com/owner/repo",
            instructions="Fix another bug",
            fnames=[],
            branch="fix-bug",
            sandbox_id="existing_sb_456",
        )

        assert result_2["success"] is True
        assert result_2["sandbox_id"] == "existing_sb_456"
        assert mock_sandbox_class.connect.called

        # Case 3: Reconnection to LOST Sandbox (Self-Healing)
        from e2b import SandboxNotFoundException

        mock_sandbox_class.connect.side_effect = SandboxNotFoundException("Not found")
        mock_sandbox_class.create.return_value = mock_sb
        mock_sb.sandbox_id = "healed_sb_789"

        # Mock results for the new session
        mock_sb.commands.run.side_effect = [
            fail_exc,  # 1. test -d
            ok,  # 2. clone
            ok,  # 3. checkout
            ok,  # 4. git config email
            ok,  # 5. git config name
            ok,  # 6. aider --version
            ok,  # 7. aider run
            ok,  # 8. push
            sha,  # 9. rev-parse
        ]

        result_3 = await run_aider_in_e2b(
            repo_url="https://github.com/owner/repo",
            instructions="Self-heal me",
            fnames=["heal.py"],
            branch="fix-heal",
            sandbox_id="lost_sb_999",  # This ID will fail to connect
        )

        assert result_3["success"] is True
        assert result_3["sandbox_id"] == "healed_sb_789"

        print("✅ E2B Aider tool persistent & self-healing logic verification passed!")


if __name__ == "__main__":
    asyncio.run(test_run_aider_in_e2b())
