import os
import re
import shlex
from typing import Any, List, Optional

import httpcore
from e2b import Sandbox, SandboxNotFoundException
from e2b.sandbox.commands.command_handle import CommandExitException
from langfuse import observe
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import settings
from src.utils.logger import configure_logging

logger = configure_logging("e2b_aider_tool")


async def get_sandbox(
    repo_url: Optional[str] = None,
    sandbox_id: Optional[str] = None,
    e2b_api_key: Optional[str] = None,
    github_token: Optional[str] = None,
) -> tuple[Sandbox, str]:
    """
    Initialize or connect to a sandbox and clone the repo if needed.
    """
    e2b_api_key = e2b_api_key or settings.E2B_API_KEY
    if not e2b_api_key:
        raise ValueError("E2B_API_KEY not found in settings.")

    sb = None
    if sandbox_id:
        try:
            sb = Sandbox.connect(sandbox_id, api_key=e2b_api_key)
        except SandboxNotFoundException:
            logger.warning("⚠️ Sandbox %s not found. Starting fresh...", sandbox_id)
            sb = None

    if not sb:
        sb = Sandbox.create(template="base", api_key=e2b_api_key)

    repo_path = "/home/user/repo"
    if repo_url:
        token = github_token or settings.GITHUB_TOKEN
        if "github.com" in repo_url and token and token not in repo_url:
            repo_url = repo_url.replace("https://", f"https://{token}@")

        try:
            sb.commands.run(f"test -d {repo_path}")
        except CommandExitException:
            sb.commands.run(f"git clone {shlex.quote(repo_url)} {repo_path}")

    return sb, repo_path


def _setup_git_identity(sb: Sandbox, repo_path: str) -> None:
    """Configures a generic Git identity to avoid 'Your Name' attribution noise."""
    try:
        sb.commands.run('git config --global user.email "aes@system.ai"', cwd=repo_path)
        sb.commands.run(
            'git config --global user.name "Agentic Engineering System (AES)"',
            cwd=repo_path,
        )
        logger.info("🆔 Git identity configured: AES <aes@system.ai>")
    except CommandExitException as e:
        logger.warning("⚠️ Failed to setup Git identity (Git command failed): %s", e)
    except Exception as e:
        logger.warning("⚠️ Failed to setup Git identity (Unexpected error): %s", e)


def clean_and_truncate_logs(text: str, max_lines: int = 1500) -> str:
    """
    Strips ANSI escape sequences and truncates text to keep only the last N lines.
    Useful for preventing LLM context overflow from large logs (e.g., npm install).
    """
    if not text:
        return ""

    # Strip ANSI escape sequences (progress bars, colors, etc.)
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    cleaned = ansi_escape.sub("", text)

    # Truncate to last N lines
    lines = cleaned.splitlines()
    if len(lines) > max_lines:
        logger.info("✂️ Truncating log from %d to %d lines.", len(lines), max_lines)
        return "\n".join(["[... (Log Truncated) ...]", *lines[-max_lines:]])
    return cleaned


def _print_stream(output) -> None:
    """
    Pipes sandbox stdout/stderr through the system logger so it appears in the UI stream.
    We strip trailing whitespace to maintain clean logs in the console.
    """
    content = ""
    if isinstance(output, str):
        content = output
    else:
        content = getattr(output, "stdout", getattr(output, "line", str(output)))

    if content.strip():
        logger.info(f" 📦 [Sandbox] {content.strip()}")


def _build_default_env() -> dict:
    """Builds a default environment dictionary with all system credentials."""
    return {
        "OPENAI_API_KEY": settings.OPENAI_API_KEY or "",
        "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY or "",
        "GITHUB_TOKEN": settings.GITHUB_TOKEN or "",
        "GH_TOKEN": settings.GITHUB_TOKEN or "",  # for gh CLI
        "GIT_TERMINAL_PROMPT": "0",  # Prevent git from hanging on auth prompts
        "PYTHONPATH": ".",
        "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID or "",
        "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY or "",
        "AWS_REGION": settings.AWS_REGION or "us-east-1",
        "AWS_DEFAULT_REGION": settings.AWS_REGION or "us-east-1",
    }


async def kill_sandbox(sandbox_id: Optional[str]) -> None:
    """Gracefully terminates a sandbox by ID, suppressing all errors."""
    if not sandbox_id:
        return
    try:
        e2b_api_key = settings.E2B_API_KEY
        sb = Sandbox.connect(sandbox_id, api_key=e2b_api_key)
        sb.kill()
        logger.info("🔴 Sandbox %s terminated.", sandbox_id)
    except Exception as e:
        logger.error("Failed to kill sandbox %s: %s", sandbox_id, e)


@observe()
async def run_command_in_e2b(
    command: str,
    repo_url: Optional[str] = None,
    sandbox_id: Optional[str] = None,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    region: Optional[str] = None,
    github_token: Optional[str] = None,
    openai_api_key: Optional[str] = None,
) -> dict:
    """
    Executes a generic shell command inside an E2B sandbox.
    Credentials (GITHUB_TOKEN, API keys) are injected by default.
    """
    try:
        sb, base_repo_path = await get_sandbox(
            repo_url, sandbox_id, github_token=github_token
        )
        repo_path = os.path.join(base_repo_path, cwd) if cwd else base_repo_path

        if cwd:
            sb.commands.run(f"mkdir -p {repo_path}")

        # Merge caller-provided env on top of defaults so credentials are always present
        default_env = _build_default_env()
        if region:
            default_env["AWS_REGION"] = region

        merged_env = {**default_env, **(env or {})}

        logger.info(
            "🐚 E2B: Executing '%s' in '%s' (sandbox: %s)...",
            command,
            repo_path,
            sb.sandbox_id,
        )

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(
                (httpcore.RemoteProtocolError, httpcore.ReadError)
            ),
            reraise=True,
        )
        def run_with_retry():
            return sb.commands.run(
                command,
                cwd=repo_path,
                envs=merged_env,
                timeout=0,
                on_stdout=_print_stream,
                on_stderr=_print_stream,
            )

        result = run_with_retry()

        return {
            "success": True,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "sandbox_id": sb.sandbox_id,
        }
    except Exception as e:
        logger.exception("❌ Error executing command in E2B: %s", e)
        return {"success": False, "error": str(e)}


@observe()
async def run_aider_in_e2b(
    repo_url: str,
    instructions: str,
    fnames: Optional[List[str]] = None,
    branch: Optional[str] = None,
    base_branch: Optional[str] = "main",
    model: Optional[str] = "gpt-4o-mini",
    sandbox_id: Optional[str] = None,
    run_only: bool = False,
    skip_push: bool = False,
    is_env_rework: bool = False,
    system_prompt: Optional[str] = None,
    region: Optional[str] = None,
    thinking: bool = False,
    thinking_budget: int = 32000,
    github_token: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    langfuse_prompt: Optional[Any] = None,
) -> dict:
    """
    Executes Aider inside an E2B sandbox to perform coding or verification tasks.
    """
    try:
        action = "Connecting to" if sandbox_id else "Creating"
        log_mode = " (Verification Mode)" if run_only else ""
        logger.info(
            "%s E2B sandbox %s (id: %s)...", action, log_mode, sandbox_id or "new"
        )

        sb, repo_path = await get_sandbox(
            repo_url, sandbox_id, github_token=github_token
        )

        # Setup Branch
        if branch:
            try:
                sb.commands.run(f"git checkout {shlex.quote(branch)}", cwd=repo_path)
            except CommandExitException:
                sb.commands.run(f"git checkout -b {shlex.quote(branch)}", cwd=repo_path)

        # Ensure Aider & Git Identity
        _setup_git_identity(sb, repo_path)
        try:
            sb.commands.run("aider --version")
        except CommandExitException:
            sb.commands.run("pip install aider-chat")

        # Prepare instructions
        final_instructions = instructions
        if system_prompt:
            final_instructions = f"{system_prompt}\n\nTASK:\n{instructions}"

        if run_only:
            # Add strict sandbox guard if not already in system_prompt
            if "DO NOT MODIFY" not in final_instructions:
                final_instructions = (
                    "CRITICAL: DO NOT MODIFY, CREATE, OR DELETE ANY SOURCE CODE FILES. "
                    "YOUR SOLE TASK IS VERIFICATION.\n\n"
                    f"{final_instructions}"
                )

        # Run Aider
        aider_model = model or "gpt-4o-mini"
        aider_cmd = (
            f"aider --model {aider_model} --message {shlex.quote(final_instructions)} "
            "--yes --exit --no-attribute-author --no-attribute-committer "
            "--no-attribute-co-authored-by --no-auto-commits "
            "--no-restore-chat-history"
        )

        # Handle Thinking Mode (Claude 3.7 / Bedrock)
        if thinking:
            settings_yaml = f"""- name: {aider_model}
  edit_format: diff
  use_temperature: false
  extra_params:
    max_tokens: {max(thinking_budget + 32000, 64000)}
    thinking:
      type: enabled
      budget_tokens: {thinking_budget}
"""
            settings_path = f"{repo_path}/.aider.model.settings.yml"
            sb.files.write(settings_path, settings_yaml)
            logger.info(
                "🧠 Thinking mode enabled with budget: %d (settings: %s)",
                thinking_budget,
                settings_path,
            )

        env = _build_default_env()
        if region:
            env["AWS_REGION"] = region
        if github_token:
            env["GITHUB_TOKEN"] = github_token
            env["GH_TOKEN"] = github_token
        if openai_api_key:
            env["OPENAI_API_KEY"] = openai_api_key
        if aws_access_key_id:
            env["AWS_ACCESS_KEY_ID"] = aws_access_key_id
        if aws_secret_access_key:
            env["AWS_SECRET_ACCESS_KEY"] = aws_secret_access_key

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(
                (httpcore.RemoteProtocolError, httpcore.ReadError)
            ),
            reraise=True,
        )
        def run_aider_with_retry():
            return sb.commands.run(
                aider_cmd,
                cwd=repo_path,
                envs=env,
                timeout=0,
                on_stdout=_print_stream,
                on_stderr=_print_stream,
            )

        aider_res = run_aider_with_retry()

        # Step: Manual Commit (replaces Aider's auto-branching/committing)
        if not run_only:
            try:
                commit_msg = f"AES: {instructions[:50].strip()}..."
                sb.commands.run("git add .", cwd=repo_path)
                sb.commands.run(
                    f"git commit -m {shlex.quote(commit_msg)}", cwd=repo_path
                )
                logger.info("💾 Manual commit successful: %s", commit_msg)
            except CommandExitException:
                logger.info("ℹ️ Nothing to commit (no changes detected).")

        # Push logic (if not run_only and skip_push is false)
        commit_sha = "unknown"
        if not run_only and not skip_push:
            safe_branch = shlex.quote(branch) if branch else "main"
            try:
                sb.commands.run(f"git push origin {safe_branch}", cwd=repo_path)
            except CommandExitException as e:
                logger.warning("Push failed (perhaps nothing to push?): %s", e)

        try:
            sha_res = sb.commands.run("git rev-parse HEAD", cwd=repo_path)
            commit_sha = sha_res.stdout.strip()
        except Exception:
            pass

        return {
            "success": True,
            "commit_sha": commit_sha,
            "sandbox_id": sb.sandbox_id,
            "logs": clean_and_truncate_logs(aider_res.stdout),
        }
    except Exception as e:
        logger.exception("❌ Exception in E2B Aider task: %s", e)
        return {"success": False, "error": str(e)}
