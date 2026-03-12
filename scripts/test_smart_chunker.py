import sys
import os
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.smart_chunker.engines.code import CodeEngine
from src.smart_chunker.engines.markdown import MarkdownEngine
from src.smart_chunker.engines.notebook import NotebookEngine
from src.smart_chunker.engines.pdf import PdfEngine
from src.smart_chunker.base import SmartChunker

def run_all_tests():
    # Setup Chunker
    chunker = SmartChunker()
    chunker.register_engine("python", CodeEngine("python"))
    chunker.register_engine("markdown", MarkdownEngine())
    chunker.register_engine("notebook", NotebookEngine())
    chunker.register_engine("pdf", PdfEngine())

    # 1. Test Python
    verify_python_chunking(chunker)
    
    # 2. Test Markdown
    verify_markdown_chunking(chunker)

    # 3. Test Notebook
    verify_notebook_chunking(chunker)

    # 4. Test PDF
    verify_pdf_chunking(chunker)

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
        print(f"Content: {c.content.strip()[:50]}...")

def verify_pdf_chunking(chunker):
    print("\n🚀 Testing PDF Chunker...")
    path = "tests/data/sample.pdf"
    
    # We pass the path directly instead of raw text bytes
    chunks = chunker.chunk(path, "spec.pdf", chunk_format="pdf")
    
    for i, c in enumerate(chunks):
        print(f"\n--- Chunk {i} ({c.chunk_type}) ---")
        print(f"Signature: {c.metadata.signature}")
        print(f"Index: {c.metadata.chunk_index}")
        print(f"Pages: {c.metadata.start_line}-{c.metadata.end_line}")
        print(f"Content Preview: {c.content.strip()[:60]}...")

if __name__ == "__main__":
    run_all_tests()
