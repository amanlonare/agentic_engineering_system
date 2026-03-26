import logging
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from e2b import Sandbox
from src.core.config_manager import app_config
from src.core.mcp_client import MCPClientManager

logger = logging.getLogger(__name__)

# Re-use Sandbox logic from tools or define here for resilience
async def _get_sb(sandbox_id: str) -> Sandbox:
    from src.core.config import settings
    return Sandbox.connect(sandbox_id, api_key=settings.E2B_API_KEY)


class ResourceManager:
    """
    Unified manager for resolving and interacting with resources (Local, GitHub, Google Drive).
    Abstracts the 'where' and 'how' of resource access.
    """

    def __init__(self, mcp_manager: Optional[MCPClientManager] = None):
        self.mcp_manager = mcp_manager or MCPClientManager()
        self.temp_dirs: List[str] = []
        self.PROTOCOL_PREFIX = app_config.system.protocol_prefix

    def clean_uri(self, uri: str) -> str:
        """Removes the protocol prefix from a URI."""
        return uri.replace(self.PROTOCOL_PREFIX, "")

    async def resolve_resource_path(
        self, repo_name: str, relative_path: str = ""
    ) -> str:
        """
        Resolves a symbolic repo name and relative path to a usable local path or MCP URI.
        """
        # If the repo name exists as a directory locally (e.g. in current dir), use it.
        local_path = Path(repo_name) / relative_path
        if local_path.exists():
            return str(local_path)

        # Check if we need to resolve owner/repo from GraphStore
        if (
            repo_name
            and repo_name != "Other Sources"
            and not repo_name.startswith("[")
        ):
            # If it already contains a slash, try exact match first. If no slash, do an ENDS WITH match.
            try:
                from src.core.graph_store import GraphStore

                gs = GraphStore()
                results = None
                
                if "/" in repo_name:
                    results = gs.execute_query(
                        "MATCH (r:Repository {name: $name}) RETURN r.remote_url",
                        {"name": repo_name},
                    )
                
                if not results:
                    results = gs.execute_query(
                        "MATCH (r:Repository) WHERE r.name ENDS WITH $name RETURN r.remote_url LIMIT 1",
                        {"name": repo_name if repo_name.startswith("/") else f"/{repo_name}"},
                    )
                    
                if results and results[0] and results[0][0]:
                    from urllib.parse import urlparse

                    remote_url = results[0][0]
                    parsed = urlparse(remote_url)
                    parts = parsed.path.strip("/").split("/")
                    if len(parts) >= 2:
                        identified_name = f"{parts[0]}/{parts[1]}"
                        if identified_name.endswith(".git"):
                            identified_name = identified_name[:-4]
                        logger.debug(
                            "Resolved symbolic repo '%s' to '%s'",
                            repo_name,
                            identified_name,
                        )
                        repo_name = identified_name
            except Exception as e:
                logger.warning(
                    "GraphStore resolution failed for '%s': %s", repo_name, e
                )

        # Ensure we don't end up with trailing slashes if relative_path is empty
        relative_path = relative_path.strip("/")
        base_uri = f"{self.PROTOCOL_PREFIX}github/{repo_name}"
        return f"{base_uri}/{relative_path}" if relative_path else base_uri

    async def read_resource(self, uri: str, branch: Optional[str] = None, sandbox_id: Optional[str] = None) -> str:
        """Reads content from a resource URI (local file, MCP, or E2B Sandbox)."""
        if sandbox_id:
            try:
                sb = await _get_sb(sandbox_id)
                # Translate URI or path to sandbox path
                # Standard sandbox path: /home/user/repo/[rel_path]
                clean_path = uri.split("/")[-1] if uri.startswith(self.PROTOCOL_PREFIX) else uri
                sandbox_path = f"/home/user/repo/{clean_path}" if not clean_path.startswith("/") else clean_path
                logger.info("📦 Sandbox Tool: Reading file from E2B: %s", sandbox_path)
                return sb.files.read(sandbox_path)
            except Exception as e:
                logger.warning("Sandbox read failed, falling back: %s", e)

        if uri.startswith(self.PROTOCOL_PREFIX):
            try:
                return await self._read_mcp(uri, branch=branch)
            except ConnectionError:
                logger.info(
                    "MCP disconnected. Falling back to ephemeral clone for reading: %s",
                    uri,
                )
                local_path = await self.ensure_local_context(uri, branch=branch)
                parts = self.clean_uri(uri).split("/", 2)
                if len(parts) > 2:
                    rel_path = parts[2]
                    target_file = Path(local_path) / rel_path
                    if target_file.exists():
                        return target_file.read_text(encoding="utf-8")
                raise FileNotFoundError(f"Resource not found in ephemeral clone: {uri}")

        # Local file fallback
        path = Path(uri)
        if path.exists():
            return path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Local resource not found: {uri}")

    async def write_resource(self, uri: str, content: str, branch: Optional[str] = None, sandbox_id: Optional[str] = None) -> bool:
        """Writes content to a resource URI (local file, MCP, or E2B Sandbox)."""
        if sandbox_id:
            try:
                sb = await _get_sb(sandbox_id)
                clean_path = uri.split("/")[-1] if uri.startswith(self.PROTOCOL_PREFIX) else uri
                sandbox_path = f"/home/user/repo/{clean_path}" if not clean_path.startswith("/") else clean_path
                logger.info("📦 Sandbox Tool: Writing file to E2B: %s", sandbox_path)
                sb.files.write(sandbox_path, content)
                return True
            except Exception as e:
                logger.warning("Sandbox write failed: %s", e)
                return False

        if uri.startswith(self.PROTOCOL_PREFIX):
            try:
                return await self._write_mcp(uri, content, branch=branch)
            except ConnectionError:
                logger.warning(
                    "MCP disconnected. Cannot write to remote resource: %s", uri
                )
                return False

        # Local file write
        path = Path(uri)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return True
        except Exception as e:
            logger.error("Failed to write to local resource %s: %s", uri, e)
            return False

    async def list_resource(self, uri: str, branch: Optional[str] = None, sandbox_id: Optional[str] = None) -> List[str]:
        """Lists contents of a resource URI (local dir, MCP, or E2B Sandbox)."""
        if sandbox_id:
            try:
                sb = await _get_sb(sandbox_id)
                clean_path = uri.split("/")[-1] if uri.startswith(self.PROTOCOL_PREFIX) else uri
                if clean_path == uri and uri not in ["", ".", "./"]: # Probably a full repo name
                    sandbox_path = "/home/user/repo"
                else:
                    sandbox_path = f"/home/user/repo/{clean_path}" if not clean_path.startswith("/") else clean_path
                
                logger.info("📦 Sandbox Tool: Listing directory in E2B: %s", sandbox_path)
                entries = sb.files.list(sandbox_path)
                return [e.name + ("/" if e.type == "dir" else "") for e in entries]
            except Exception as e:
                logger.warning("Sandbox list failed: %s", e)

        if uri.startswith(self.PROTOCOL_PREFIX):
            try:
                return await self._list_mcp(uri, branch=branch)
            except ConnectionError:
                logger.info(
                    "MCP disconnected. Falling back to ephemeral clone for listing: %s",
                    uri,
                )
                local_path = await self.ensure_local_context(uri, branch=branch)
                parts = self.clean_uri(uri).split("/", 2)
                target_dir = Path(local_path)
                if len(parts) > 2:
                    target_dir = target_dir / parts[2]

                if target_dir.exists() and target_dir.is_dir():
                    return [
                        str(p.relative_to(local_path)) for p in target_dir.iterdir()
                    ]
                return []

        # Local directory fallback
        path = Path(uri)
        if path.exists() and path.is_dir():
            return [str(p.name) for p in path.iterdir()]
        return []

    # ── MCP Proxy Methods ──────────────────────────────────────────────

    async def _ensure_mcp_connection(self, server: str):
        """Ensures the specified MCP server is connected."""
        if server in self.mcp_manager.sessions:
            return

        from src.core.config import settings

        if server == "github":
            cmd_str = str(settings.GITHUB_MCP_COMMAND)
            cmd_parts = cmd_str.split()
            logger.info("Auto-connecting to GitHub MCP: %s", cmd_str)
            await self.mcp_manager.connect_stdio("github", cmd_parts[0], cmd_parts[1:])
        elif server == "gdrive":
            cmd_str = str(settings.GOOGLE_DRIVE_MCP_COMMAND)
            cmd_parts = cmd_str.split()
            logger.info("Auto-connecting to Google Drive MCP: %s", cmd_str)
            await self.mcp_manager.connect_stdio("gdrive", cmd_parts[0], cmd_parts[1:])

    async def _read_mcp(self, uri: str, branch: Optional[str] = None) -> str:
        """Translates mcp:// URI to an MCP tool call."""
        # URI format: mcp://server/owner/repo/path
        uri_no_proto = self.clean_uri(uri)
        parts = uri_no_proto.split("/", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid MCP URI (missing server): {uri}")

        server = parts[0]
        remainder = parts[1]  # "owner/repo/path" or "owner/repo"

        await self._ensure_mcp_connection(server)

        logger.info("Proxying read to MCP server '%s' for '%s' (branch: %s)", server, remainder, branch)

        session = self.mcp_manager.sessions.get(server)
        if not session:
            raise ConnectionError(f"MCP server '{server}' not connected.")

        if server == "github":
            # remainder: owner/repo/path/to/file
            subparts = remainder.split("/", 2)
            if len(subparts) < 3:
                raise ValueError(f"Invalid GitHub MCP URI (missing path): {uri}")
            owner, repo_name, path = subparts

            args = {"owner": owner, "repo": repo_name, "path": path}
            if branch:
                args["branch"] = branch

            result = await session.call_tool(
                "get_file_contents", args
            )
            
            # The GitHub MCP tool 'get_file_contents' returns a JSON response in a text block
            # We need to parse that JSON and decode the base64 'content' field.
            import json
            import base64
            
            combined_text = "".join(getattr(block, "text") for block in result.content if hasattr(block, "text"))
            
            try:
                data = json.loads(combined_text)
                if isinstance(data, dict) and "content" in data:
                    content_str = data["content"]
                    encoding = data.get("encoding", "")
                    
                    if encoding == "base64":
                        return base64.b64decode(content_str).decode("utf-8")
                    return content_str
            except (json.JSONDecodeError, Exception) as e:
                logger.debug("Failed to parse GitHub MCP response as JSON, returning raw text: %s", e)
                
            return combined_text

        elif server == "gdrive":
            result = await session.call_tool("read_file", {"path": remainder})
            text_blocks = []
            for block in result.content:
                if hasattr(block, "text"):
                    text_blocks.append(getattr(block, "text"))
            return "".join(text_blocks)

        return f"[Unsupported MCP Server: {server}]"

    async def _write_mcp(self, uri: str, content: str, branch: Optional[str] = None) -> bool:
        """Translates mcp:// URI to an MCP write tool call."""
        uri_no_proto = self.clean_uri(uri)
        parts = uri_no_proto.split("/", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid MCP URI: {uri}")

        server = parts[0]
        remainder = parts[1]

        await self._ensure_mcp_connection(server)

        logger.info("Proxying write to MCP: %s (branch: %s)", uri, branch)

        session = self.mcp_manager.sessions.get(server)
        if not session:
            raise ConnectionError(f"MCP server '{server}' not connected.")

        if server == "github":
            subparts = remainder.split("/", 2)
            if len(subparts) < 3:
                raise ValueError(f"Invalid GitHub MCP URI (missing path): {uri}")
            owner, repo_name, path = subparts

            target_branch = branch or app_config.system.default_branch
            if not target_branch or target_branch.lower() in ["main", "master", ""]:
                error_msg = f"Strict branching policy violation: Cannot write commit directly to '{target_branch}'. A separate feature branch must be crated and used."
                logger.error(error_msg)
                raise ValueError(error_msg)

            try:
                await session.call_tool(
                    "create_or_update_file",
                    {
                        "owner": owner,
                        "repo": repo_name,
                        "path": path,
                        "content": content,
                        "message": "Update via Agentic Engineering System",
                        "branch": target_branch,
                    },
                )
            except Exception as e:
                error_str = str(e)
                if "Branch" in error_str and "not found" in error_str:
                    raise ValueError(
                        f"ERROR: Branch '{target_branch}' does not exist on remote. "
                        f"You MUST call 'create_branch' before writing or patching files on a new branch."
                    )
                raise e
            return True

        return False

    async def _list_mcp(self, uri: str, branch: Optional[str] = None) -> List[str]:
        """Translates mcp:// URI to an MCP list tool call."""
        uri_no_proto = self.clean_uri(uri)
        parts = uri_no_proto.split("/", 1)
        if len(parts) < 2:
            return []

        server = parts[0]
        remainder = parts[1]

        await self._ensure_mcp_connection(server)

        logger.info("Proxying list to MCP: %s", uri)

        session = self.mcp_manager.sessions.get(server)
        if not session:
            raise ConnectionError(f"MCP server '{server}' not connected.")

        if server == "github":
            subparts = remainder.split("/", 2)
            owner = subparts[0]
            repo_name = subparts[1] if len(subparts) > 1 else ""
            path = subparts[2] if len(subparts) > 2 else ""

            # Normalize trailing slashes to prevent MCP errors
            path = path.rstrip("/")

            if not repo_name:
                return []

            logger.debug(
                "MCP GitHub list_directory: owner=%s, repo=%s, path=%s",
                owner,
                repo_name,
                path,
            )

            result = await session.call_tool(
                "get_file_contents", {"owner": owner, "repo": repo_name, "path": path}
            )

            names = []
            import json

            for block in result.content:
                if hasattr(block, "text"):
                    text_val = getattr(block, "text")
                    try:
                        # GitHub API returns a JSON array of objects for directories
                        parsed = json.loads(text_val)
                        if isinstance(parsed, list):
                            for item in parsed:
                                if isinstance(item, dict) and "name" in item:
                                    n = item["name"]
                                    if item.get("type") == "dir":
                                        n += "/"
                                    names.append(n)
                        elif isinstance(parsed, dict) and "name" in parsed:
                            names.append(parsed["name"])
                        else:
                            names.append(text_val)
                    except json.JSONDecodeError:
                        names.append(text_val)
            return names

        return []

    async def ensure_local_context(self, uri: str, branch: Optional[str] = None) -> str:
        """
        Ensures a remote repo is available locally (via clone) and returns local path.
        """
        # Parse URI: mcp://server/owner/repo/path
        uri_clean = self.clean_uri(uri)
        parts = uri_clean.split("/", 3)
        if len(parts) < 3:
            raise ValueError(f"Invalid URI for local context: {uri}")

        server, owner, repo = parts[0], parts[1], parts[2]

        if server == "github":
            repo_full_name = f"{owner}/{repo}"
            local_path = Path.cwd() / "temp_repos" / f"{owner}_{repo}"

            if not local_path.exists():
                repo_url = f"https://github.com/{repo_full_name}.git"
                logger.info("Cloning %s to %s...", repo_url, local_path)
                local_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    subprocess.run(
                        ["git", "clone", "--depth", "1", repo_url, str(local_path)],
                        check=True,
                        capture_output=True,
                    )
                    self.temp_dirs.append(str(local_path))
                except subprocess.CalledProcessError as e:
                    logger.error(
                        "Failed to clone repository: %s", e.stderr.decode().strip()
                    )
                    raise

            return str(local_path)

        raise ValueError(f"Unsupported server for local context: {server}")

    async def cleanup(self):
        """Removes temporary cloned repositories."""
        for d in self.temp_dirs:
            if Path(d).exists():
                logger.info("Cleaning up temp repo: %s", d)
                try:
                    shutil.rmtree(d)
                except Exception as e:
                    logger.warning("Failed to cleanup %s: %s", d, e)
        self.temp_dirs = []
        await self.mcp_manager.disconnect_all()
