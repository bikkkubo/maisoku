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


def analyze_pdf(pdf_path: Path, ocr_threshold: int = 200, allow_ocr: bool = False, ocr_config: Optional[dict] = None, openai_config: Optional[dict] = None) -> ExtractResult:
    """
    Analyze a PDF: get embedded text and optionally perform OCR/OpenAI fallback.
    
    Process:
    1. Extract embedded text using pypdf
    2. If allow_ocr=True and text_length < ocr_threshold and needs_ocr=True:
       - Attempt OCR extraction
       - Combine embedded text with OCR text
       - Update result with OCR status
    3. If OpenAI enabled and conditions met:
       - Call OpenAI for text/vision extraction
       - Supplement/replace information
       - Update result with AI status
    4. Return ExtractResult with combined text and processing notes
    
    Args:
        pdf_path: Path to PDF file
        ocr_threshold: Text length below which OCR is flagged as needed
        allow_ocr: Enable OCR fallback when text is scarce (default: False)
        ocr_config: OCR configuration dictionary (default: None)
        openai_config: OpenAI configuration dictionary (default: None)
        
    Returns:
        ExtractResult with text, length, OCR flag, and processing note
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    if not pdf_path.suffix.lower() == '.pdf':
        raise ValueError(f"Not a PDF file: {pdf_path}")
    
    try:
        # OCR設定のデフォルト値と取得
        config = ocr_config or {}
        actual_threshold = config.get('threshold', ocr_threshold)
        
        # OpenAI設定の取得
        ai_config = openai_config or {}
        ai_enabled = ai_config.get('enabled', False)
        
        # Step 1: Extract embedded text
        text = extract_text_embedded(pdf_path)
        length = len(text.strip())  # Use stripped length for better OCR threshold detection
        needs_ocr = length < actual_threshold
        
        # Initial notes based on embedded text
        if length == 0:
            note = "no_text_extracted"
        elif needs_ocr:
            note = f"short_text_{length}chars"
        else:
            note = f"embedded_text_{length}chars"
        
        # Step 2: OCR fallback if conditions are met
        if allow_ocr and needs_ocr:
            logging.debug(f"OCR条件満了: text_length={length} < threshold={actual_threshold}, OCR実行中...")
            
            try:
                from .ocr import try_ocr_extraction
                
                # OCR実行（embedded textをfallbackとして渡す）
                ocr_result = try_ocr_extraction(pdf_path, fallback_text=text.strip(), ocr_config=config)
                
                if ocr_result.text != text.strip():  # OCRで新しいテキストが取得された
                    text = ocr_result.text
                    length = len(text)
                    needs_ocr = length < actual_threshold  # OCR後の長さで再判定
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
        
        # Step 3: OpenAI fallback if conditions are met
        if ai_enabled:
            try:
                # 既存データから情報解析（判定用）
                from .info_parser import parse_info
                current_info = parse_info(text)
                
                # OpenAI呼び出し条件の判定
                should_call_ai = False
                ai_when = ai_config.get('when', 'missing')
                
                if ai_when == 'always':
                    should_call_ai = True
                elif ai_when == 'missing':
                    # kind/name/amount のいずれかが欠損している場合
                    if (current_info.kind == 'unknown' or 
                        current_info.name is None or 
                        current_info.amount is None):
                        should_call_ai = True
                
                if should_call_ai:
                    logging.debug(f"OpenAI呼び出し条件満了: when={ai_when}, PDF={pdf_path.name}")
                    
                    from .openai_infer import OpenAIExtractor
                    
                    extractor = OpenAIExtractor(model=ai_config.get('model', 'gpt-4o-mini'))
                    
                    if ai_config.get('vision', False):
                        # Vision API使用
                        ai_result = extractor.extract_from_pdf(
                            pdf_path,
                            dpi=ai_config.get('dpi', 400),
                            pages=ai_config.get('pages', 1)
                        )
                        ai_note_suffix = "vision"
                    else:
                        # Text API使用
                        text_result = extractor.extract_from_text(text)
                        ai_result = type('AiResult', (), {
                            'kind': text_result.get('kind', 'unknown'),
                            'name': text_result.get('name') or None,
                            'amount': text_result.get('amount'),
                            'notes': 'openai_text_ok' if text_result.get('kind') != 'unknown' else 'openai_text_failed'
                        })()
                        ai_note_suffix = "text"
                    
                    # OpenAI結果で情報を補完/置換
                    if ai_result.notes.startswith('openai_'):
                        # OpenAI成功時の情報統合
                        if ai_result.kind and ai_result.kind != 'unknown':
                            current_info.kind = ai_result.kind
                        if ai_result.name:
                            current_info.name = ai_result.name
                        if ai_result.amount is not None:
                            current_info.amount = ai_result.amount
                        
                        if 'ok' in ai_result.notes:
                            note = f"{note},ai_ok:{ai_note_suffix}"
                            logging.info(f"OpenAI処理完了: {pdf_path.name} -> {ai_note_suffix} ({ai_result.notes})")
                        else:
                            note = f"{note},ai_failed:{ai_note_suffix}"
                            logging.warning(f"OpenAI処理失敗: {pdf_path.name} -> {ai_result.notes}")
                    else:
                        note = f"{note},ai_failed:{ai_note_suffix}"
                        logging.warning(f"OpenAI処理失敗: {pdf_path.name} -> {ai_result.notes}")
                else:
                    logging.debug(f"OpenAI呼び出しスキップ: when={ai_when}, 条件不満足")
                    
            except ImportError:
                note = f"{note},ai_unavailable"
                logging.warning("OpenAI依存関係がインストールされていません: pip install \".[openai_ocr]\"")
            except Exception as e:
                note = f"{note},ai_failed:error"
                logging.error(f"OpenAI処理エラー ({pdf_path.name}): {e}")
        
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