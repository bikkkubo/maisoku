from __future__ import annotations
import re
from typing import Optional

# 価格抽出パターン（優先度順）
_PRICE_PATTERNS = [
    # 億円パターン
    re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*億\s*円?", re.IGNORECASE),
    # 万円パターン
    re.compile(r"([0-9,，]+)\s*万\s*円?", re.IGNORECASE),
    # 千万円パターン（4桁以上の万円）
    re.compile(r"([0-9,，]{4,})\s*万\s*円?", re.IGNORECASE),
    # 円パターン（4桁以上）
    re.compile(r"([0-9,，]{4,})\s*円", re.IGNORECASE),
    # 数字のみ（7桁以上を価格と判定）
    re.compile(r"([0-9,，]{7,})", re.IGNORECASE),
]


def normalize_number_string(s: str) -> str:
    """
    数字文字列を正規化（カンマ除去、全角→半角）
    
    Args:
        s: 数字文字列
        
    Returns:
        正規化された数字文字列
    """
    if not s:
        return ""
    
    # 全角数字を半角に変換
    s = s.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    # カンマ・全角カンマを除去
    s = s.replace(",", "").replace("，", "").replace(" ", "")
    return s


def parse_amount_jpy(text: str) -> Optional[int]:
    """
    テキストから日本円の金額を抽出・解析する
    
    Args:
        text: 入力テキスト
        
    Returns:
        円単位の整数値、抽出できない場合はNone
    """
    if not text:
        return None
    
    # テキストを正規化
    normalized_text = normalize_number_string(text)
    
    # 億円パターンを最優先で検索
    for pattern in _PRICE_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            try:
                number_str = normalize_number_string(matches[0])
                
                if "億" in pattern.pattern:
                    # 億円の場合
                    yen = float(number_str) * 100_000_000
                    return int(round(yen))
                elif "万" in pattern.pattern:
                    # 万円の場合
                    return int(number_str) * 10_000
                elif "円" in pattern.pattern:
                    # 円の場合
                    return int(number_str)
                else:
                    # 数字のみの場合、桁数で判定
                    num = int(number_str)
                    if num >= 1_000_000:  # 100万以上は円として扱う
                        return num
                        
            except (ValueError, OverflowError):
                continue
    
    return None


def format_price_sell(yen: int) -> str:
    """
    売買価格を表示用にフォーマットする
    
    Args:
        yen: 円単位の価格
        
    Returns:
        フォーマット済み価格文字列
    """
    if yen < 0:
        return "0円"
    
    if yen >= 100_000_000:
        # 1億円以上：N.X億円（小数1桁）
        oku = round(yen / 100_000_000, 1)
        if oku == int(oku):
            return f"{int(oku)}億円"
        else:
            return f"{oku:.1f}億円"
    else:
        # 1億円未満：N,NNN万円
        man = yen // 10_000
        return f"{man:,}万円"


def format_price_rent(yen: int) -> str:
    """
    賃貸価格を表示用にフォーマットする
    
    Args:
        yen: 円単位の価格
        
    Returns:
        フォーマット済み価格文字列
    """
    if yen < 0:
        return "0円"
    
    return f"{yen:,}円"


def extract_multiple_amounts(text: str) -> dict[str, Optional[int]]:
    """
    テキストから複数の金額情報を抽出する
    
    Args:
        text: 入力テキスト
        
    Returns:
        金額種別をキーとした辞書
    """
    if not text:
        return {}
    
    amounts = {}
    
    # 賃料関連
    rent_patterns = [
        r"賃料[:：]?\s*([0-9,，]+(?:\.[0-9]+)?[万円億]+)",
        r"家賃[:：]?\s*([0-9,，]+(?:\.[0-9]+)?[万円億]+)",
    ]
    
    # 売買価格関連
    price_patterns = [
        r"(?:販売)?価格[:：]?\s*([0-9,，]+(?:\.[0-9]+)?[万円億]+)",
        r"売出[:価]?[:：]?\s*([0-9,，]+(?:\.[0-9]+)?[万円億]+)",
    ]
    
    # 賃料を検索
    for pattern in rent_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount = parse_amount_jpy(match.group(1))
            if amount:
                amounts['rent'] = amount
                break
    
    # 売買価格を検索
    for pattern in price_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount = parse_amount_jpy(match.group(1))
            if amount:
                amounts['price'] = amount
                break
    
    return amounts