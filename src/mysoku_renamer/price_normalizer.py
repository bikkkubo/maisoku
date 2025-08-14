from __future__ import annotations
import re
from typing import Optional

# 応相談・価格未定パターン
_UNSPECIFIED_PATTERNS = [
    re.compile(r"応相談", re.IGNORECASE),
    re.compile(r"要問合?[せし]", re.IGNORECASE), 
    re.compile(r"価格未定", re.IGNORECASE),
    re.compile(r"要相談", re.IGNORECASE),
    re.compile(r"別途相談", re.IGNORECASE),
    re.compile(r"お問い合わせ", re.IGNORECASE),
]

# 価格抽出パターン（優先度順）
_PRICE_PATTERNS = [
    # 億円パターン
    re.compile(r"(\d+(?:\.\d+)?)\s*億\s*(?:円)?", re.IGNORECASE),
    # 万円パターン
    re.compile(r"([0-9,，]+)\s*万\s*(?:円)?", re.IGNORECASE),
    # 千万円パターン（4桁以上の万円）
    re.compile(r"([0-9,，]{4,})\s*万\s*(?:円)?", re.IGNORECASE),
    # 円パターン（4桁以上）
    re.compile(r"([0-9,，]{4,})\s*円", re.IGNORECASE),
    # 数字のみ（7桁以上を価格と判定）
    re.compile(r"([0-9,，]{7,})", re.IGNORECASE),
]


def normalize_number_string(s: str) -> str:
    """
    数字文字列を正規化（全角→半角、カンマ・通貨記号除去）
    
    Args:
        s: 数字文字列
        
    Returns:
        正規化された数字文字列
    """
    if not s:
        return ""
    
    # 全角数字を半角に変換
    s = s.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    # 全角・半角カンマを除去
    s = s.replace(",", "").replace("，", "")
    # 通貨記号を除去
    s = s.replace("¥", "").replace("￥", "")
    # 空白を除去
    s = s.replace(" ", "").replace("　", "")
    return s


def check_price_unspecified(text: str) -> bool:
    """
    価格が応相談・未定等かチェック
    
    Args:
        text: 入力テキスト
        
    Returns:
        応相談等の場合True
    """
    if not text:
        return False
        
    for pattern in _UNSPECIFIED_PATTERNS:
        if pattern.search(text):
            return True
    return False


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
    
    # 応相談・価格未定等の場合はNone
    if check_price_unspecified(text):
        return None
    
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
        金額種別をキーとした辞書、応相談等の場合はprice_unspecifiedフラグを含む
    """
    if not text:
        return {}
    
    amounts = {}
    
    # 応相談・価格未定チェック
    if check_price_unspecified(text):
        amounts['price_unspecified'] = True
        return amounts
    
    # 賃料関連パターンを強化
    rent_patterns = [
        # 基本パターン
        r"(?:(?:家賃|賃料|月額)\s*[:：]?\s*)(\d+[,\d]*)\s*(?:円|¥)?",
        r"(\d+[,\d]*)\s*(?:円|¥)\s*(?:／|\/)?\s*(?:月)?",
        r"(\d+(?:\.\d+)?)\s*万円",  # 万円表記の賃料
        # 詳細パターン
        r"賃料[:：]?\s*([0-9,，]+(?:\.[0-9]+)?[万円億]+)",
        r"家賃[:：]?\s*([0-9,，]+(?:\.[0-9]+)?[万円億]+)",
    ]
    
    # 売買価格関連パターンを強化  
    price_patterns = [
        # 億円パターン
        r"(\d+(?:\.\d+)?)\s*億(?:円)?",
        # 万円パターン
        r"(\d+[,\d]*)\s*万(?:円)?",
        # 詳細パターン
        r"(?:販売)?価格[:：]?\s*([0-9,，]+(?:\.[0-9]+)?[万円億]+)",
        r"売出[:価]?[:：]?\s*([0-9,，]+(?:\.[0-9]+)?[万円億]+)",
    ]
    
    # 賃料を検索
    for pattern in rent_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_text = match.group(1)
            # 万円表記の場合は万円として処理
            if "万円" in pattern:
                try:
                    num = float(normalize_number_string(amount_text))
                    amount = int(num * 10_000)
                    amounts['rent'] = amount
                    break
                except ValueError:
                    continue
            else:
                amount = parse_amount_jpy(amount_text)
                if amount:
                    amounts['rent'] = amount
                    break
    
    # 売買価格を検索
    for pattern in price_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_text = match.group(1)
            amount = parse_amount_jpy(amount_text)
            if amount:
                amounts['price'] = amount
                break
    
    return amounts