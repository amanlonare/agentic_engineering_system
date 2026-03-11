import sys
import os
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.smart_chunker.engines.python_ast import PythonEngine
from src.smart_chunker.engines.markdown import MarkdownEngine
from src.smart_chunker.engines.notebook import NotebookEngine
from src.smart_chunker.base import SmartChunker

def run_all_tests():
    # Setup Chunker
    chunker = SmartChunker()
    chunker.register_engine("python", PythonEngine())
    chunker.register_engine("markdown", MarkdownEngine())
    chunker.register_engine("notebook", NotebookEngine())

    # 1. Test Python
    verify_python_chunking(chunker)
    
    # 2. Test Markdown
    verify_markdown_chunking(chunker)

    # 3. Test Notebook
    verify_notebook_chunking(chunker)

def verify_python_chunking(chunker):
    sample_code = """
class BaseHandler:
    def handle(self):
        pass

class AuthHandler(BaseHandler):
    def login(self, user, pwd):
        print(f"Login {user}")

def standalone_func(x):
    return x * 2
"""
    
    print("\n🚀 Testing Python Chunker...")
    chunks = chunker.chunk(sample_code, "test.py", chunk_format="python")
    
    for i, c in enumerate(chunks):
        print(f"\n--- Chunk {i} ({c.chunk_type}) ---")
        print(f"Symbol: {c.metadata.symbol_name}")
        print(f"Signature: {c.metadata.signature}")
        print(f"Inherits: {c.metadata.parent_symbol}")
        print(f"Deps: {c.metadata.dependencies}")
        print(f"Lines: {c.metadata.start_line}-{c.metadata.end_line}")

def verify_markdown_chunking(chunker):
    sample_md = """
# Project Alpha
Welcome to the project.

## Installation
Run `npm install`.

### Prerequisites
- Node.js
- NPM

## Usage
Import and call the main function.
"""
    print("\n🚀 Testing Markdown Chunker...")
    chunks = chunker.chunk(sample_md, "README.md", chunk_format="markdown")
    
    for i, c in enumerate(chunks):
        print(f"\n--- Chunk {i} ({c.chunk_type}) ---")
        print(f"Path: {c.metadata.signature}")
        content_preview = c.content[:40].replace('\n', ' ')
        print(f"Start: {content_preview}...")

def verify_notebook_chunking(chunker):
    sample_nb = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["def notebook_func():\n", "    return 'hello'"]
            }
        ]
    }
    print("\n🚀 Testing Notebook Chunker...")
    chunks = chunker.chunk(json.dumps(sample_nb), "test.ipynb", chunk_format="notebook")
    
    for i, c in enumerate(chunks):
        print(f"\n--- Chunk {i} ({c.chunk_type}) ---")
        print(f"Symbol: {c.metadata.symbol_name}")
        print(f"Index: {c.metadata.chunk_index}")
        print(f"Content: {c.content.strip()}")

if __name__ == "__main__":
    run_all_tests()
