import pytest

from src.smart_chunker.base import SmartChunker
from src.smart_chunker.engines.markdown import MarkdownEngine
from src.smart_chunker.engines.notebook import NotebookEngine
from src.smart_chunker.engines.python_ast import PythonEngine


@pytest.fixture
def chunker():
    c = SmartChunker()
    c.register_engine("python", PythonEngine())
    c.register_engine("markdown", MarkdownEngine())
    c.register_engine("notebook", NotebookEngine())
    return c


def test_python_file(chunker):
    path = "tests/data/sample.py"
    with open(path, "r") as f:
        content = f.read()

    chunks = chunker.chunk(content, path, chunk_format="python")
    assert (
        len(chunks) >= 3
    )  # Calculator class + 2 methods + power func (some might be nested)
    # Actually our current logic returns atomic chunks, so:
    # Calculator class, add method, subtract method, power func = 4
    assert any(c.metadata.symbol_name == "Calculator" for c in chunks)
    assert any(c.metadata.symbol_name == "add" for c in chunks)


def test_markdown_file(chunker):
    path = "tests/data/sample.md"
    with open(path, "r") as f:
        content = f.read()

    chunks = chunker.chunk(content, path, chunk_format="markdown")
    assert len(chunks) == 4  # Intro, Section 1, 1.1, Section 2
    assert "Section 1" in chunks[1].metadata.signature


def test_notebook_file(chunker):
    path = "tests/data/sample.ipynb"
    with open(path, "r") as f:
        content = f.read()

    chunks = chunker.chunk(content, path, chunk_format="notebook")
    assert len(chunks) == 1
    assert chunks[0].metadata.symbol_name == "cell_func"
    assert "0.0" in chunks[0].metadata.chunk_index


def test_missing_engine(chunker):
    with pytest.raises(ValueError, match="No engine registered"):
        chunker.chunk("content", "test.js", chunk_format="js")
