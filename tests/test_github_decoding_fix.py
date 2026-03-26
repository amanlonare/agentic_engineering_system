import base64
import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from src.core.resource_manager import ResourceManager


class TestGithubDecoding(unittest.IsolatedAsyncioTestCase):
    async def test_resource_manager_read_mcp_github_decoding(self):
        # 1. Setup ResourceManager with mocks
        mock_mcp_manager = MagicMock()
        mock_session = AsyncMock()
        mock_mcp_manager.sessions = {"github": mock_session}

        # 2. Mock MCP session's call_tool result
        original_code = "import React from 'react';\nexport default function App() { return <div>Success</div>; }"
        encoded_code = base64.b64encode(original_code.encode("utf-8")).decode("utf-8")

        # This mocks the JSON response that GitHub MCP server returns
        mock_json_response = json.dumps(
            {"name": "App.tsx", "content": encoded_code, "encoding": "base64"}
        )

        # LangChain/MCP Response format
        class MockBlock:
            def __init__(self, text):
                self.text = text

        mock_result = MagicMock()
        mock_result.content = [MockBlock(mock_json_response)]

        mock_session.call_tool.return_value = mock_result

        rm = ResourceManager(mcp_manager=mock_mcp_manager)

        # 3. Call _read_mcp with a GitHub URI
        # The clean_uri will get 'github/owner/repo/path'
        uri = "mcp://github/user/portfolio/src/App.tsx"
        result = await rm._read_mcp(uri)

        # 4. Verify decoding
        self.assertEqual(result, original_code)
        self.assertNotIn("encoding", result)
        self.assertNotIn("content", result)
        print(
            "✅ Unit Test SUCCESS: ResourceManager correctly unwrapped and decoded GitHub MCP content."
        )

    async def test_non_github_mcp_raw_pass_through(self):
        # Ensure it doesn't break other servers like gdrive
        mock_mcp_manager = MagicMock()
        mock_session = AsyncMock()
        mock_mcp_manager.sessions = {"gdrive": mock_session}

        plain_text = "This is a plain text file from GDrive"

        class MockBlock:
            def __init__(self, text):
                self.text = text

        mock_result = MagicMock()
        mock_result.content = [MockBlock(plain_text)]
        mock_session.call_tool.return_value = mock_result

        rm = ResourceManager(mcp_manager=mock_mcp_manager)

        uri = "mcp://gdrive/some/file.txt"
        result = await rm._read_mcp(uri)

        self.assertEqual(result, plain_text)
        print("✅ Unit Test SUCCESS: GDrive raw pass-through is preserved.")


if __name__ == "__main__":
    unittest.main()
