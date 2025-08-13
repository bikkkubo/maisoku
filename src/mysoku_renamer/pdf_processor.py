from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pypdf import PdfReader


@dataclass
class ExtractResult:
    text: str
    text_length: int
    needs_ocr: bool
    note: str = ""


def extract_text_embedded(pdf_path: Path) -> str:
    """
    Extract text from a PDF using embedded text layer only.
    No OCR here. Raises exceptions up to caller for transparent handling.
    """
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        raise ValueError(f"Failed to open PDF: {e}") from e
    
    parts = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            parts.append(text or "")
        except Exception as e:
            # Robustness: skip a bad page but keep going
            parts.append("")
            # Could log page-level extraction failure if debug enabled
    
    return "\n".join(parts)


def analyze_pdf(pdf_path: Path, ocr_threshold: int = 200, allow_ocr: bool = False) -> ExtractResult:
    """
    Analyze a PDF: get embedded text and optionally perform OCR fallback.
    
    Process:
    1. Extract embedded text using pypdf
    2. If allow_ocr=True and text_length < ocr_threshold and needs_ocr=True:
       - Attempt OCR extraction
       - Combine embedded text with OCR text
       - Update result with OCR status
    3. Return ExtractResult with combined text and processing notes
    
    Args:
        pdf_path: Path to PDF file
        ocr_threshold: Text length below which OCR is flagged as needed
        allow_ocr: Enable OCR fallback when text is scarce (default: False)
        
    Returns:
        ExtractResult with text, length, OCR flag, and processing note
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    if not pdf_path.suffix.lower() == '.pdf':
        raise ValueError(f"Not a PDF file: {pdf_path}")
    
    try:
        # Step 1: Extract embedded text
        text = extract_text_embedded(pdf_path)
        length = len(text.strip())  # Use stripped length for better OCR threshold detection
        needs_ocr = length < ocr_threshold
        
        # Initial notes based on embedded text
        if length == 0:
            note = "no_text_extracted"
        elif needs_ocr:
            note = f"short_text_{length}chars"
        else:
            note = f"embedded_text_{length}chars"
        
        # Step 2: OCR fallback if conditions are met
        if allow_ocr and needs_ocr:
            logging.debug(f"OCR条件満了: text_length={length} < threshold={ocr_threshold}, OCR実行中...")
            
            try:
                from .ocr import try_ocr_extraction
                
                # OCR実行（embedded textをfallbackとして渡す）
                ocr_result = try_ocr_extraction(pdf_path, fallback_text=text.strip())
                
                if ocr_result.text != text.strip():  # OCRで新しいテキストが取得された
                    text = ocr_result.text
                    length = len(text)
                    needs_ocr = length < ocr_threshold  # OCR後の長さで再判定
                    note = ocr_result.note
                    logging.info(f"OCR処理完了: {pdf_path.name} -> {length}文字 ({note})")
                else:
                    # OCR失敗またはテキスト追加なし
                    note = ocr_result.note
                    logging.debug(f"OCR処理結果: {pdf_path.name} -> {note}")
                    
            except ImportError:
                note = "ocr_unavailable"
                logging.warning("OCR依存関係がインストールされていません: pip install \".[ocr]\"")
            except Exception as e:
                note = "ocr_failed"
                logging.error(f"OCR処理エラー ({pdf_path.name}): {e}")
        
        return ExtractResult(
            text=text,
            text_length=length,
            needs_ocr=needs_ocr,
            note=note
        )
        
    except Exception as e:
        # Return error result instead of re-raising to allow graceful handling
        logging.error(f"PDF解析エラー ({pdf_path.name}): {e}")
        return ExtractResult(
            text="",
            text_length=0,
            needs_ocr=True,  # Assume OCR needed if extraction failed
            note=f"extraction_error_{type(e).__name__}"
        )