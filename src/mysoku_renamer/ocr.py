#!/usr/bin/env python3
"""
OCR機能モジュール（オプション）

目的:
- PDF埋め込みテキストが不足している場合のフォールバック
- ローカル実行のみ（外部送信なし）
- tesseract + pytesseract による日本語OCR

起動条件:
- --ocrフラグ指定 かつ
- text_length < 200文字 かつ  
- needs_ocr=True判定

依存:
- システム: tesseract-ocr + 日本語言語パック
- Python: pytesseract, Pillow
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# オプション依存のインポート（ランタイムで依存なしでもエラー回避）
try:
    import pytesseract
    from PIL import Image
    from pdf2image import convert_from_path
    TESSERACT_AVAILABLE = True
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    pytesseract = None
    Image = None
    convert_from_path = None
    TESSERACT_AVAILABLE = False
    PDF2IMAGE_AVAILABLE = False


@dataclass
class OcrResult:
    """OCR実行結果"""
    text: str
    note: str  # "ocr_ok" / "ocr_unavailable" / "ocr_failed" / "ocr_not_implemented_pdf2img"


def check_tesseract_availability() -> bool:
    """tesseract の利用可能性チェック"""
    if not TESSERACT_AVAILABLE:
        return False
    
    try:
        # tesseract バージョン確認で存在チェック
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _pdf_to_images(pdf_path: Path, dpi: int = 300, pages: int = 0) -> List["Image.Image"]:
    """
    PDF→画像変換
    
    Args:
        pdf_path: PDF ファイルパス
        dpi: 変換解像度
        pages: 先頭Nページのみ変換（0=全ページ）
        
    Returns:
        画像オブジェクトのリスト
        
    Raises:
        RuntimeError: pdf2image/Pillow が利用不可、またはPDF変換に失敗
    """
    if not PDF2IMAGE_AVAILABLE:
        raise RuntimeError("pdf2image is not available")
    
    if Image is None:
        raise RuntimeError("Pillow is not available")
    
    try:
        images = convert_from_path(str(pdf_path), dpi=dpi)
        
        # ページ数制限の適用
        if pages > 0 and len(images) > pages:
            images = images[:pages]
            logging.debug(f"PDF→画像変換成功: {len(images)}ページ（先頭{pages}ページのみ）、DPI={dpi}")
        else:
            logging.debug(f"PDF→画像変換成功: {len(images)}ページ、DPI={dpi}")
        
        return images
    except Exception as e:
        logging.error(f"PDF→画像変換エラー: {e}")
        raise RuntimeError(f"PDF→画像変換に失敗しました: {e}") from e


def run_ocr_on_images(images: List["Image.Image"], lang: str = "jpn+jpn_vert") -> OcrResult:
    """
    画像リストに対してOCR実行
    
    Args:
        images: PIL.Image オブジェクトのリスト
        lang: tesseract 言語設定（日本語横書き+縦書き）
        
    Returns:
        OcrResult: OCR結果とステータス
    """
    if pytesseract is None:
        logging.warning("pytesseract が利用できません。pip install \".[ocr]\" でインストールしてください。")
        return OcrResult(text="", note="ocr_unavailable")
    
    if not check_tesseract_availability():
        logging.warning("tesseract が利用できません。システムレベルでのインストールが必要です。")
        return OcrResult(text="", note="ocr_unavailable")
    
    try:
        extracted_texts = []
        
        for i, image in enumerate(images):
            logging.debug(f"OCR実行中 [{i+1}/{len(images)}]: 画像サイズ {image.size}")
            
            # tesseract でテキスト抽出
            text = pytesseract.image_to_string(image, lang=lang, config="--psm 6")
            
            if text and text.strip():
                extracted_texts.append(text.strip())
                logging.debug(f"OCRテキスト抽出: {len(text.strip())}文字")
            else:
                logging.debug(f"OCRテキスト抽出: 文字なし")
        
        # 全ページのテキストを結合
        combined_text = "\n".join(extracted_texts)
        
        if combined_text:
            logging.info(f"OCR成功: {len(combined_text)}文字抽出（{len(images)}ページ）")
            return OcrResult(text=combined_text, note="ocr_ok")
        else:
            logging.warning("OCR実行完了したが、テキストが抽出されませんでした")
            return OcrResult(text="", note="ocr_failed")
            
    except Exception as e:
        logging.error(f"OCR実行エラー: {e}")
        return OcrResult(text="", note="ocr_failed")


def try_ocr_extraction(pdf_path: Path, fallback_text: str = "", ocr_config: Optional[dict] = None) -> OcrResult:
    """
    PDFファイルに対してOCR抽出を試行
    
    Args:
        pdf_path: 対象PDFファイル
        fallback_text: OCR失敗時のフォールバックテキスト
        ocr_config: OCR設定辞書（dpi, pages, lang等）
        
    Returns:
        OcrResult: OCR結果（失敗時はfallback_textを含む）
    """
    if not TESSERACT_AVAILABLE:
        return OcrResult(text=fallback_text, note="ocr_unavailable")
    
    if not check_tesseract_availability():
        return OcrResult(text=fallback_text, note="ocr_unavailable")
    
    try:
        # OCR設定の取得
        config = ocr_config or {}
        dpi = config.get('dpi', 300)
        pages = config.get('pages', 0)
        lang = config.get('lang', 'jpn+jpn_vert')
        
        # PDF→画像変換を試行
        logging.debug(f"PDF→画像変換開始: {pdf_path}")
        images = _pdf_to_images(pdf_path, dpi=dpi, pages=pages)
        
        # OCR実行
        ocr_result = run_ocr_on_images(images, lang=lang)
        
        # OCR結果とfallback_textを結合
        if ocr_result.text and ocr_result.note == "ocr_ok":
            combined_text = (fallback_text + "\n" + ocr_result.text).strip()
            return OcrResult(text=combined_text, note="ocr_ok")
        else:
            # OCR失敗時はfallback_textのみ
            return OcrResult(text=fallback_text, note=ocr_result.note)
            
    except RuntimeError as e:
        logging.error(f"PDF→画像変換失敗: {e}")
        return OcrResult(text=fallback_text, note="ocr_failed")
    except Exception as e:
        logging.error(f"OCR抽出エラー: {e}")
        return OcrResult(text=fallback_text, note="ocr_failed")


def get_ocr_status_summary() -> dict:
    """OCR機能の利用可能状況を取得"""
    return {
        "tesseract_available": TESSERACT_AVAILABLE and check_tesseract_availability(),
        "pytesseract_installed": pytesseract is not None,
        "pillow_installed": Image is not None,
        "pdf2img_available": PDF2IMAGE_AVAILABLE
    }


if __name__ == "__main__":
    # OCR機能の診断
    import json
    
    logging.basicConfig(level=logging.INFO)
    
    print("OCR機能診断:")
    status = get_ocr_status_summary()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    
    if status["tesseract_available"] and status["pdf2img_available"]:
        print("✅ OCR機能は利用可能です")
    else:
        print("❌ OCR機能は利用できません")
        print("システムレベル要件:")
        print("  - macOS: brew install poppler tesseract tesseract-lang")
        print("  - Ubuntu: sudo apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-jpn tesseract-ocr-jpn-vert")
        print("Python要件:")
        print("  - pip install \".[ocr]\"")