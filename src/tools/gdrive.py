import logging
from typing import List, Optional

from langchain_core.tools import tool

from src.utils.logger import configure_logging

logger = configure_logging()

# Reuse global resource manager
from src.tools.codebase_tools import resource_manager

@tool
async def search_gdrive(query: str) -> str:
    """Searches for files in Google Drive."""
    logger.info(f"📑 Searching Google Drive for: '{query}'")
    
    session = resource_manager.mcp_manager.sessions.get("gdrive")
    if not session:
        return "Error: Google Drive MCP server not connected."
    
    try:
        result = await session.call_tool("search_files", {"query": query})
        return str(result)
    except Exception as e:
        return f"Error searching GDrive: {str(e)}"

@tool
async def list_gdrive_folder(folder_id: str) -> str:
    """Lists files in a specific Google Drive folder."""
    logger.info(f"📑 Listing GDrive folder: {folder_id}")
    
    # Note: the gdrive mcp server tool might be called 'list_folder' or 'list_files_in_folder'
    # Defaulting to common tool name.
    session = resource_manager.mcp_manager.sessions.get("gdrive")
    if not session:
        return "Error: Google Drive MCP server not connected."
    
    try:
        result = await session.call_tool("list_files", {"q": f"'{folder_id}' in parents"})
        return str(result)
    except Exception as e:
        return f"Error listing GDrive folder: {str(e)}"
