from __future__ import annotations

from pathlib import Path
import tempfile
import pytest

from pypdf import PdfWriter

from mysoku_renamer.pdf_processor import analyze_pdf, extract_text_embedded, ExtractResult


def _make_blank_pdf(path: Path) -> None:
    """
    Create a minimal blank PDF (no text). pypdf can write empty pages.
    """
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)  # A4 size in points
    with path.open("wb") as f:
        writer.write(f)


def test_analyze_pdf_blank_returns_zero_length():
    """Test that blank PDFs are correctly identified with zero text length."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "blank.pdf"
        _make_blank_pdf(p)
        res = analyze_pdf(p)
        assert res.text_length == 0
        assert res.needs_ocr is True  # Should flag for OCR since no text
        assert "no_text_extracted" in res.note


def test_analyze_pdf_nonexistent_file():
    """Test that non-existent files raise appropriate error."""
    non_existent = Path("/tmp/does_not_exist.pdf")
    with pytest.raises(FileNotFoundError):
        analyze_pdf(non_existent)


def test_analyze_pdf_non_pdf_file():
    """Test that non-PDF files raise appropriate error."""
    with tempfile.TemporaryDirectory() as td:
        txt_file = Path(td) / "test.txt"
        txt_file.write_text("not a pdf")
        with pytest.raises(ValueError, match="Not a PDF file"):
            analyze_pdf(txt_file)


def test_analyze_pdf_ocr_threshold_logic():
    """Test OCR threshold logic with blank PDF."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "blank.pdf"
        _make_blank_pdf(p)
        
        # Test with different thresholds
        res_low = analyze_pdf(p, ocr_threshold=10)
        res_high = analyze_pdf(p, ocr_threshold=1000)
        
        # Both should flag OCR needed since text_length=0
        assert res_low.needs_ocr is True
        assert res_high.needs_ocr is True


def test_extract_text_embedded_blank_pdf():
    """Test direct text extraction from blank PDF."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "blank.pdf"
        _make_blank_pdf(p)
        text = extract_text_embedded(p)
        assert isinstance(text, str)
        assert len(text.strip()) == 0  # Should be empty or whitespace


def test_extract_text_embedded_nonexistent_file():
    """Test text extraction from non-existent file."""
    non_existent = Path("/tmp/does_not_exist.pdf")
    with pytest.raises(ValueError, match="Failed to open PDF"):
        extract_text_embedded(non_existent)


def test_extract_result_dataclass():
    """Test ExtractResult dataclass functionality."""
    result = ExtractResult(
        text="sample text",
        text_length=11,
        needs_ocr=False,
        note="test_note"
    )
    assert result.text == "sample text"
    assert result.text_length == 11
    assert result.needs_ocr is False
    assert result.note == "test_note"