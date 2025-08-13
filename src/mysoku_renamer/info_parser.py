from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from .property_cleaner import clean_name, extract_name_candidates
from .price_normalizer import parse_amount_jpy, extract_multiple_amounts

# 取引種別判定キーワード
_SELL_HINTS = [
    "販売価格", "売出価格", "価格", "売買", "売出", "購入", "分譲", "売却", "販売"
]
_RENT_HINTS = [
    "賃料", "家賃", "月額", "管理費", "敷金", "礼金", "賃貸", "貸", "テナント"
]

# 物件名検出パターン
_NAME_PATTERNS = [
    re.compile(r"物件名[:：]\s*([^\n\r]+)", re.IGNORECASE),
    re.compile(r"建物名[:：]\s*([^\n\r]+)", re.IGNORECASE),
    re.compile(r"マンション名[:：]\s*([^\n\r]+)", re.IGNORECASE),
    re.compile(r"アパート名[:：]\s*([^\n\r]+)", re.IGNORECASE),
]


@dataclass
class ParsedInfoRaw:
    kind: str               # "sell" | "rent" | "unknown"
    name: Optional[str]
    amount: Optional[int]   # 円単位の整数


def detect_kind(text: str) -> str:
    """
    テキストから取引種別を判定する
    
    Args:
        text: 分析対象テキスト
        
    Returns:
        "sell" | "rent" | "unknown"
    """
    if not text:
        return "unknown"
    
    # テキストを正規化（大文字小文字統一）
    normalized_text = text.lower()
    
    # キーワードの出現回数をカウント
    sell_score = sum(1 for hint in _SELL_HINTS if hint.lower() in normalized_text)
    rent_score = sum(1 for hint in _RENT_HINTS if hint.lower() in normalized_text)
    
    # 特定パターンの強い指標
    strong_sell_patterns = [
        r"売買|分譲|購入|販売価格",
        r"\d+(?:万|億)円.*売",
    ]
    strong_rent_patterns = [
        r"賃貸|テナント|月額",
        r"家賃.*\d+(?:万|,\d+)?円",
        r"敷金|礼金|管理費",
    ]
    
    # 強いパターンによる判定
    for pattern in strong_sell_patterns:
        if re.search(pattern, normalized_text):
            sell_score += 3
    
    for pattern in strong_rent_patterns:
        if re.search(pattern, normalized_text):
            rent_score += 3
    
    # スコアに基づく判定
    if rent_score > sell_score:
        return "rent"
    elif sell_score > rent_score:
        return "sell"
    else:
        return "unknown"


def extract_name(text: str) -> Optional[str]:
    """
    テキストから物件名を抽出する
    
    Args:
        text: 入力テキスト
        
    Returns:
        抽出された物件名、見つからない場合はNone
    """
    if not text:
        return None
    
    # 1. 明示的な物件名フィールドを検索
    for pattern in _NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            name = clean_name(match.group(1))
            if name:
                return name
    
    # 2. 候補行からの抽出
    candidates = extract_name_candidates(text)
    
    # 各候補をクリーニングして最初に有効なものを返す
    for candidate in candidates:
        cleaned = clean_name(candidate)
        if cleaned:
            return cleaned
    
    return None


def extract_amount(text: str, transaction_kind: str = "unknown") -> Optional[int]:
    """
    テキストから金額を抽出する
    
    Args:
        text: 入力テキスト
        transaction_kind: 取引種別（"sell"|"rent"|"unknown"）
        
    Returns:
        抽出された金額（円単位）、見つからない場合はNone
    """
    if not text:
        return None
    
    # 複数の金額を抽出
    amounts = extract_multiple_amounts(text)
    
    # 取引種別に応じて優先順位を決定
    if transaction_kind == "rent":
        # 賃貸の場合は賃料を優先
        if 'rent' in amounts:
            return amounts['rent']
        elif 'price' in amounts:
            return amounts['price']
    elif transaction_kind == "sell":
        # 売買の場合は価格を優先
        if 'price' in amounts:
            return amounts['price']
        elif 'rent' in amounts:
            return amounts['rent']
    
    # 一般的な金額抽出
    amount = parse_amount_jpy(text)
    if amount:
        return amount
    
    # 複数金額から最大値を選択（売買価格の可能性が高い）
    if amounts:
        return max(amounts.values())
    
    return None


def parse_info(text: str) -> ParsedInfoRaw:
    """
    テキストから物件情報を解析・抽出する
    
    Args:
        text: 分析対象テキスト
        
    Returns:
        解析結果（ParsedInfoRaw）
    """
    if not text:
        return ParsedInfoRaw(kind="unknown", name=None, amount=None)
    
    # 各要素を抽出
    kind = detect_kind(text)
    name = extract_name(text)
    amount = extract_amount(text, kind)
    
    return ParsedInfoRaw(kind=kind, name=name, amount=amount)


def validate_parsed_info(info: ParsedInfoRaw) -> dict[str, bool]:
    """
    解析結果の妥当性をチェックする
    
    Args:
        info: 解析結果
        
    Returns:
        検証結果の辞書
    """
    validation = {
        'has_name': info.name is not None and len(info.name.strip()) > 0,
        'has_amount': info.amount is not None and info.amount > 0,
        'kind_determined': info.kind in ["sell", "rent"],
        'amount_reasonable': False
    }
    
    if info.amount:
        # 金額の妥当性チェック
        if info.kind == "sell":
            # 売買：1000万円〜100億円程度
            validation['amount_reasonable'] = 10_000_000 <= info.amount <= 10_000_000_000
        elif info.kind == "rent":
            # 賃貸：5万円〜100万円程度
            validation['amount_reasonable'] = 50_000 <= info.amount <= 1_000_000
        else:
            # 種別不明の場合は広範囲で許可
            validation['amount_reasonable'] = 10_000 <= info.amount <= 10_000_000_000
    
    return validation