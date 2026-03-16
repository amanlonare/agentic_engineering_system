import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPClientManager:
    """
    A unified manager for connecting to and interacting with multiple MCP servers.
    Supports both Stdio and SSE transports.
    """

    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stacks = {}  # To manage context managers for stdio/sse clients
        self._tools_cache: Dict[str, List[BaseTool]] = {}

    async def connect_sse(
        self, name: str, url: str, headers: Optional[Dict[str, str]] = None
    ):
        """Connect to a remote MCP server via SSE."""
        logger.info(f"Connecting to SSE MCP server '{name}' at {url}")
        try:
            # We use an ExitStack logically, but for simplicity in this manager we'll start the context
            from contextlib import AsyncExitStack

            stack = AsyncExitStack()
            self.exit_stacks[name] = stack

            read, write = await stack.enter_async_context(
                sse_client(url, headers=headers)
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.sessions[name] = session
            logger.info(f"Successfully initialized SSE session for '{name}'")
        except Exception as e:
            logger.error(f"Failed to connect to SSE MCP server '{name}': {e}")
            raise

    async def connect_stdio(
        self,
        name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
    ):
        """Connect to a local MCP server via Stdio."""
        from src.core.config import settings

        # Prepare environment: Start with current process env
        full_env = os.environ.copy()

        # Update with provided env if any
        if env:
            full_env.update(env)

        if settings.GITHUB_TOKEN:
            full_env["GITHUB_TOKEN"] = settings.GITHUB_TOKEN
            # Some MCP servers use GITHUB_PERSONAL_ACCESS_TOKEN
            full_env["GITHUB_PERSONAL_ACCESS_TOKEN"] = settings.GITHUB_TOKEN

        if name == "gdrive" and settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH:
            key_path = Path(settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH)
            if not key_path.is_absolute():
                key_path = Path.cwd().joinpath(key_path)
            full_env["GOOGLE_APPLICATION_CREDENTIALS"] = str(key_path)
            full_env["GOOGLE_SERVICE_ACCOUNT_PATH"] = str(key_path)
            full_env["SERVICE_ACCOUNT_PATH"] = str(key_path)
            logger.info(f"Injected Google credentials from {key_path}")

        logger.info(
            f"Connecting to Stdio MCP server '{name}' with command: {command} {' '.join(args)}"
        )
        try:
            from contextlib import AsyncExitStack

            stack = AsyncExitStack()
            self.exit_stacks[name] = stack

            server_params = StdioServerParameters(
                command=command, args=args, env=full_env
            )
            read, write = await stack.enter_async_context(stdio_client(server_params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.sessions[name] = session
            logger.info(f"Successfully initialized Stdio session for '{name}'")
        except Exception as e:
            logger.error(f"Failed to connect to Stdio MCP server '{name}': {e}")
            raise

    async def get_langchain_tools(
        self, server_name: Optional[str] = None
    ) -> List[BaseTool]:
        """
        Fetch tools from one or all connected servers and wrap them as LangChain tools.
        """
        if server_name:
            return await self._fetch_server_tools(server_name)

        all_tools = []
        for name in self.sessions:
            all_tools.extend(await self._fetch_server_tools(name))
        return all_tools

    async def _fetch_server_tools(self, name: str) -> List[BaseTool]:
        if name in self._tools_cache:
            return self._tools_cache[name]

        session = self.sessions.get(name)
        if not session:
            return []

        try:
            mcp_tools = await session.list_tools()
            lc_tools = []

            for mcp_tool in mcp_tools.tools:
                # Wrap MCP tool into a LangChain tool
                # Note: This is a simplified wrapper. Real production logic might need
                # more robust schema conversion.
                lc_tool = self._make_langchain_tool(name, mcp_tool, session)
                lc_tools.append(lc_tool)

            self._tools_cache[name] = lc_tools
            return lc_tools
        except Exception as e:
            logger.error(f"Error fetching tools from server '{name}': {e}")
            return []

    def _make_langchain_tool(
        self, server_name: str, mcp_tool: Any, session: ClientSession
    ) -> BaseTool:
        """Helper to create a LangChain tool from an MCP tool definition."""

        async def call_mcp_tool(**kwargs):
            result = await session.call_tool(mcp_tool.name, kwargs)
            return result.content

        # Extract docstring/description
        description = mcp_tool.description or f"Tool {mcp_tool.name} from {server_name}"

        # We use StructuredTool.from_function for better kwarg handling
        from langchain_core.tools import StructuredTool

        return StructuredTool.from_function(
            name=f"{server_name}_{mcp_tool.name}",
            coroutine=call_mcp_tool,
            description=description,
        )

    async def disconnect_all(self):
        """Close all active sessions."""
        for name, stack in self.exit_stacks.items():
            logger.info(f"Disconnecting MCP server '{name}'")
            await stack.aclose()
        self.sessions = {}
        self.exit_stacks = {}
        self._tools_cache = {}
