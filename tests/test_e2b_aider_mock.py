import asyncio
import os
from unittest.mock import MagicMock, patch
from src.tools.e2b_aider_tool import run_aider_in_e2b

async def test_run_aider_in_e2b():
    print("Testing e2b_aider_tool logic (with mocks)...")
    
    # Setup environment variables for test
    os.environ["E2B_API_KEY"] = "test_key"
    os.environ["GITHUB_TOKEN"] = "test_token"
    
    from src.core.config import settings
    
    # Patch settings and E2B Sandbox
    with patch.object(settings, "E2B_API_KEY", "test_key"), \
         patch.object(settings, "GITHUB_TOKEN", "test_token"), \
         patch.object(settings, "OPENAI_API_KEY", "test_openai"), \
         patch.object(settings, "ANTHROPIC_API_KEY", "test_anthropic"), \
         patch("src.tools.e2b_aider_tool.Sandbox") as mock_sandbox_class:
        
        mock_sb = MagicMock()
        mock_sandbox_class.create.return_value = mock_sb
        mock_sandbox_class.connect.return_value = mock_sb
        
        from e2b.sandbox.commands.command_handle import CommandExitException
        
        # Mock results
        ok = MagicMock(stdout="ok\n", stderr="", exit_code=0)
        diff = MagicMock(stdout="diff content\n", stderr="", exit_code=0)
        sha = MagicMock(stdout="test_sha_12345\n", stderr="", exit_code=0)
        branch_res = MagicMock(stdout="main\n", stderr="", exit_code=0)
        
        # Exception to simulate failure - CommandExitException(stdout, stderr, exit_code, error)
        fail_exc = CommandExitException(stdout="", stderr="error", exit_code=1, error="Command failed")

        # New Sandbox Case (checks fail, everything installs)
        mock_sb.commands.run.side_effect = [
            fail_exc,   # 1. test -d (raises -> goes to except)
            ok,         # 2. git clone
            branch_res, # 3. git branch --show-current
            fail_exc,   # 4. git checkout (raises -> goes to except -> git checkout -b)
            ok,         # 5. git checkout -b
            fail_exc,   # 6. aider --version (raises -> goes to except -> pip install)
            ok,         # 7. pip install aider
            ok,         # 8. aider run
            diff,       # 9. git diff
            ok,         # 10. git push
            sha,        # 11. git rev-parse
        ]
        mock_sb.sandbox_id = "new_sb_123"
        
        result = await run_aider_in_e2b(
            repo_url="https://github.com/owner/repo",
            instructions="Fix the bug",
            fnames=["app.py"],
            branch="fix-bug",
            base_branch="main"
        )
        
        if not result["success"]:
            print(f"❌ Result failed: {result.get('error')}")
        assert result["success"] is True
        assert result["sandbox_id"] == "new_sb_123"
        assert result["commit_sha"] == "test_sha_12345"
        
        # Test Reconnect Case (checks pass, skip clone/install)
        branch_res_2 = MagicMock(stdout="fix-bug\n", stderr="", exit_code=0)
        mock_sb.commands.run.side_effect = [
            ok,           # 1. test -d (repo exists)
            branch_res_2, # 2. git branch --show-current (already on branch)
            ok,           # 3. aider --version (exists)
            ok,           # 4. aider run
            diff,         # 5. git diff
            ok,           # 6. git push
            sha,          # 7. git rev-parse
        ]
        mock_sb.sandbox_id = "existing_sb_456"
        mock_sandbox_class.connect.return_value.__enter__.return_value = mock_sb

        result_2 = await run_aider_in_e2b(
            repo_url="https://github.com/owner/repo",
            instructions="Fix another bug",
            fnames=[],
            branch="fix-bug",
            sandbox_id="existing_sb_456"
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
        # Note: We need another set of side effects for the subsequent calls
        mock_sb.commands.run.side_effect = [
            fail_exc,   # test -d (fail -> clone)
            ok,         # clone
            branch_res, # show-current
            ok,         # checkout
            fail_exc,   # aider --version
            ok,         # pip install
            ok,         # aider run
            diff,       # diff
            ok,         # push
            sha,        # rev-parse
        ]
        
        result_3 = await run_aider_in_e2b(
            repo_url="https://github.com/owner/repo",
            instructions="Self-heal me",
            fnames=["heal.py"],
            branch="fix-heal",
            sandbox_id="lost_sb_999" # This ID will fail
        )
        
        assert result_3["success"] is True
        assert result_3["sandbox_id"] == "healed_sb_789"
        
        print("✅ E2B Aider tool persistent & self-healing logic verification passed!")

if __name__ == "__main__":
    asyncio.run(test_run_aider_in_e2b())
