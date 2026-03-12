import pytest

from src.smart_chunker.base import SmartChunker
from src.smart_chunker.engines.code import CodeEngine
from src.smart_chunker.engines.gdoc import GDocEngine
from src.smart_chunker.engines.gsheet import GSheetEngine
from src.smart_chunker.engines.markdown import MarkdownEngine
from src.smart_chunker.engines.notebook import NotebookEngine
from src.smart_chunker.engines.pdf import PdfEngine


@pytest.fixture
def chunker():
    c = SmartChunker()
    c.register_engine("python", CodeEngine("python"))
    c.register_engine("markdown", MarkdownEngine())
    c.register_engine("notebook", NotebookEngine())
    c.register_engine("pdf", PdfEngine())
    c.register_engine("gdoc", GDocEngine())
    c.register_engine("gsheet", GSheetEngine())
    return c


def test_python_file(chunker):
    path = "tests/data/sample.py"
    with open(path, "r") as f:
        content = f.read()

    chunks = chunker.chunk(content, path, chunk_format="python")
    assert len(chunks) >= 3  # Calculator class + 2 methods + power func
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


def test_pdf_with_toc(chunker):
    path = "tests/data/pdf_with_toc.pdf"
    chunks = chunker.chunk(path, "toc.pdf", chunk_format="pdf")

    # These tests assume the test PDFs were created by our generator earlier
    assert len(chunks) == 3
    assert chunks[0].metadata.symbol_name == "Introduction"
    assert chunks[1].metadata.symbol_name == "Chapter 1"
    assert chunks[2].metadata.signature == "Chapter 1 -> Section 1.1"


def test_pdf_with_heuristics(chunker):
    path = "tests/data/pdf_with_fonts.pdf"
    chunks = chunker.chunk(path, "fonts.pdf", chunk_format="pdf")

    assert len(chunks) >= 2
    symbols = [c.metadata.symbol_name for c in chunks]
    assert "Heading 1" in symbols
    assert chunks[0].metadata.chunk_index.startswith("h_")


def test_pdf_basic_fallback(chunker):
    path = "tests/data/pdf_basic.pdf"
    chunks = chunker.chunk(path, "basic.pdf", chunk_format="pdf")

    assert len(chunks) == 2
    assert "Page 1 Content" in chunks[0].content
    assert chunks[0].metadata.symbol_name == "Page 1"


@pytest.fixture
def gdoc_json():
    return {
        "title": "Test Doc",
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [{"textRun": {"content": "Header 1\n"}}],
                        "paragraphStyle": {"namedStyleType": "HEADING_1"},
                    }
                },
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": "Some text content here.\n"}}
                        ],
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                    }
                },
            ]
        },
    }


def test_gdoc_chunking(chunker, gdoc_json):
    chunks = chunker.chunk(gdoc_json, "test.json", "gdoc")
    assert len(chunks) == 1
    assert chunks[0].metadata.symbol_name == "Header 1"
    assert "Some text content here" in chunks[0].content


def test_gdoc_japanese_splitting(chunker):
    # Test splitting with Japanese full-width periods
    long_japanese_text = "これはテストです。" * 500  # ~4500 chars
    gdoc_json_ja = {
        "title": "Japanese Doc",
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [{"textRun": {"content": "日本語\n"}}],
                        "paragraphStyle": {"namedStyleType": "HEADING_1"},
                    }
                },
                {
                    "paragraph": {
                        "elements": [{"textRun": {"content": long_japanese_text}}],
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                    }
                },
            ]
        },
    }

    chunks = chunker.chunk(gdoc_json_ja, "test_ja.json", "gdoc")
    assert len(chunks) > 1
    # Check that splitting occurred at a logical point
    assert chunks[0].content.endswith("。")
    assert chunks[0].metadata.chunk_index == "gdoc_0.0"


def test_missing_engine(chunker):
    with pytest.raises(ValueError, match="No engine registered"):
        chunker.chunk("content", "test.js", chunk_format="js")


@pytest.fixture
def gsheet_json():
    return {
        "sheets": [
            {
                "properties": {"title": "Users"},
                "data": [
                    {
                        "rowData": [
                            {
                                "values": [
                                    {
                                        "formattedValue": "ID",
                                        "effectiveFormat": {
                                            "textFormat": {"bold": True}
                                        },
                                    },
                                    {
                                        "formattedValue": "Name",
                                        "effectiveFormat": {
                                            "textFormat": {"bold": True}
                                        },
                                    },
                                ]
                            },
                            {
                                "values": [
                                    {"formattedValue": "1"},
                                    {"formattedValue": "Alice"},
                                ]
                            },
                            {
                                "values": [
                                    {"formattedValue": "2"},
                                    {"formattedValue": "Bob"},
                                ]
                            },
                        ]
                    }
                ],
            }
        ]
    }


def test_gsheet_chunking(chunker, gsheet_json):
    chunks = chunker.chunk(gsheet_json, "test_sheet.json", "gsheet")
    assert len(chunks) == 1
    content = chunks[0].content

    # Check header detection and injection
    assert "ID: 1" in content
    assert "Name: Alice" in content
    assert "ID: 2" in content
    assert "Name: Bob" in content

    # Check metadata
    assert chunks[0].metadata.symbol_name == "Users"
    assert "Rows 1-3" in chunks[0].metadata.signature
