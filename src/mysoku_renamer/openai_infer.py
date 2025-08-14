#!/usr/bin/env python3
"""
OpenAI連携による物件情報抽出モジュール

目的:
- OpenAI Vision APIを使用した高精度PDF情報抽出
- テキスト情報からのJSONレスポンス構造化
- 既存OCRの代替・補完機能

依存:
- システム: poppler-utils (pdf2image用)
- Python: openai, pdf2image, Pillow
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any
from io import BytesIO

# オプション依存のインポート
try:
    from openai import OpenAI
    from PIL import Image
    from pdf2image import convert_from_path
    OPENAI_AVAILABLE = True
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    OpenAI = None
    Image = None
    convert_from_path = None
    OPENAI_AVAILABLE = False
    PDF2IMAGE_AVAILABLE = False


@dataclass
class AiResult:
    """OpenAI抽出結果"""
    kind: str           # "sell" | "rent" | "unknown"
    name: Optional[str] # 物件名（不明は None）
    amount: Optional[int] # 円の整数（不明/応相談は None）
    notes: str          # 処理ステータス
    raw_json: str       # 生JSONレスポンス
    text_length: int    # 入力テキスト長


class OpenAIExtractor:
    """OpenAI APIを使用した物件情報抽出クラス"""
    
    def __init__(self, model: str = "gpt-4o-mini"):
        """
        初期化とAPI キー存在チェック
        
        Args:
            model: 使用するOpenAIモデル
            
        Raises:
            RuntimeError: API キーが設定されていない場合
        """
        if not OPENAI_AVAILABLE:
            raise RuntimeError("OpenAI SDK not available. Install with: pip install 'openai>=1.40.0'")
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable is required")
        
        self.model = model
        self.client = OpenAI(api_key=api_key)
        logging.debug(f"OpenAI client initialized with model: {model}")
    
    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        テキストから物件情報をJSON形式で抽出
        
        Args:
            text: 抽出対象テキスト
            
        Returns:
            構造化された物件情報辞書
        """
        if not text or not text.strip():
            return {"kind": "unknown", "name": "", "amount": None}
        
        prompt = """以下の不動産物件情報から、JSON形式で情報を抽出してください。

出力形式（厳格に従ってください）:
{
  "kind": "sell" | "rent" | "unknown",
  "name": "物件名（部屋番号除く、不明時は空文字）",
  "amount": 円の整数値（億円・万円は円換算、不明・応相談時はnull）
}

判定ルール:
- kind: 販売価格/売買/分譲→"sell", 賃料/家賃→"rent", 判定不能→"unknown"
- name: 物件名のみ（号室、階数、括弧内注釈は除去）
- amount: 1.2億円→120000000, 18万円→180000, 応相談/未定→null

入力テキスト:
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたは不動産物件情報の抽出専門AIです。指定されたJSON形式で正確に回答してください。"},
                    {"role": "user", "content": prompt + text}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=500
            )
            
            raw_json = response.choices[0].message.content
            logging.debug(f"OpenAI raw response: {raw_json}")
            
            # JSONパース
            result = json.loads(raw_json)
            
            # 価格の正規化
            if result.get("amount") and isinstance(result["amount"], str):
                result["amount"] = self._normalize_price_to_yen(result["amount"])
            
            return result
            
        except Exception as e:
            logging.error(f"OpenAI text extraction failed: {e}")
            return {"kind": "unknown", "name": "", "amount": None}
    
    def extract_from_pdf(self, pdf_path: Path, dpi: int = 400, pages: int = 1) -> AiResult:
        """
        PDFページ画像からVision APIで物件情報を抽出
        
        Args:
            pdf_path: PDF ファイルパス
            dpi: 画像変換解像度
            pages: 先頭N ページ（0=全ページ）
            
        Returns:
            AiResult: 抽出結果
        """
        if not PDF2IMAGE_AVAILABLE:
            return AiResult(
                kind="unknown", name=None, amount=None,
                notes="pdf2image_unavailable", raw_json="", text_length=0
            )
        
        try:
            # PDF→画像変換
            images = convert_from_path(str(pdf_path), dpi=dpi)
            
            if pages > 0:
                images = images[:pages]
            
            if not images:
                return AiResult(
                    kind="unknown", name=None, amount=None,
                    notes="no_pages_converted", raw_json="", text_length=0
                )
            
            # 最初のページを使用（複数ページ対応は将来拡張）
            first_image = images[0]
            
            # PNG形式でbase64エンコード
            buffer = BytesIO()
            first_image.save(buffer, format="PNG")
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Vision API呼び出し
            prompt = """この不動産マイソク画像から物件情報を抽出し、JSON形式で回答してください。

出力形式:
{
  "kind": "sell" | "rent" | "unknown",
  "name": "物件名（部屋番号・階数除く）",
  "amount": 円の整数値（億万円は円換算、不明時はnull）
}

判定基準:
- 販売価格/売買/分譲 → "sell"
- 賃料/家賃/月額 → "rent"  
- 判定不能 → "unknown"
- 応相談/要問合せ/価格未定 → amount: null"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=500
            )
            
            raw_json = response.choices[0].message.content
            result_dict = json.loads(self._clean_json_response(raw_json))
            
            # 価格正規化
            amount = result_dict.get("amount")
            if amount and isinstance(amount, str):
                amount = self._normalize_price_to_yen(amount)
            
            return AiResult(
                kind=result_dict.get("kind", "unknown"),
                name=result_dict.get("name") or None,
                amount=amount,
                notes="openai_vision_ok",
                raw_json=raw_json,
                text_length=len(raw_json)
            )
            
        except Exception as e:
            logging.error(f"OpenAI Vision extraction failed: {e}")
            return AiResult(
                kind="unknown", name=None, amount=None,
                notes=f"openai_vision_failed_{type(e).__name__}",
                raw_json="", text_length=0
            )
    
    def _normalize_price_to_yen(self, price_str: str) -> Optional[int]:
        """
        価格文字列を円の整数に正規化
        
        Args:
            price_str: 価格文字列（"1.2億円", "18万円"等）
            
        Returns:
            円の整数値、変換不可時はNone
        """
        if not price_str:
            return None
        
        # 全角→半角変換
        price_str = price_str.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        # カンマ・通貨記号・空白除去
        price_str = re.sub(r'[,，¥￥\s　]', '', price_str)
        
        try:
            # 億円パターン
            oku_match = re.search(r'(\d+(?:\.\d+)?)億', price_str)
            if oku_match:
                return int(float(oku_match.group(1)) * 100_000_000)
            
            # 万円パターン
            man_match = re.search(r'(\d+(?:\.\d+)?)万', price_str)
            if man_match:
                return int(float(man_match.group(1)) * 10_000)
            
            # 円パターン
            yen_match = re.search(r'(\d+)円?', price_str)
            if yen_match:
                return int(yen_match.group(1))
            
            # 数字のみ（7桁以上は円とみなす）
            num_match = re.search(r'(\d{7,})', price_str)
            if num_match:
                return int(num_match.group(1))
                
        except (ValueError, OverflowError):
            pass
        
        return None
    
    def _clean_json_response(self, response: str) -> str:
        """
        JSONレスポンスから```json```マークダウンを除去
        
        Args:
            response: 生レスポンス文字列
            
        Returns:
            クリーンなJSON文字列
        """
        if not response:
            return "{}"
        
        # ```json ... ``` パターンを除去
        cleaned = re.sub(r'```json\s*\n?', '', response)
        cleaned = re.sub(r'\n?\s*```', '', cleaned)
        
        return cleaned.strip()


def check_openai_availability() -> dict:
    """OpenAI機能の利用可能状況を取得"""
    api_key_set = bool(os.getenv("OPENAI_API_KEY"))
    
    return {
        "openai_installed": OPENAI_AVAILABLE,
        "pdf2image_available": PDF2IMAGE_AVAILABLE,
        "api_key_set": api_key_set,
        "ready": OPENAI_AVAILABLE and PDF2IMAGE_AVAILABLE and api_key_set
    }


if __name__ == "__main__":
    # OpenAI機能の診断
    import json as json_module
    
    logging.basicConfig(level=logging.INFO)
    
    print("OpenAI機能診断:")
    status = check_openai_availability()
    print(json_module.dumps(status, indent=2, ensure_ascii=False))
    
    if status["ready"]:
        print("✅ OpenAI機能は利用可能です")
    else:
        print("❌ OpenAI機能は利用できません")
        if not status["openai_installed"]:
            print("  - pip install 'openai>=1.40.0' が必要")
        if not status["pdf2image_available"]:
            print("  - pip install 'pdf2image>=1.17.0' が必要")
        if not status["api_key_set"]:
            print("  - OPENAI_API_KEY 環境変数の設定が必要")