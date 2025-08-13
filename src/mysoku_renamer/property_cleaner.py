from __future__ import annotations
import re
from typing import Optional

# ファイル名に使用できない文字
_FORBIDDEN = r'[\\/:*?"<>|]'
# 連続する空白
_SPACE = re.compile(r"\s+")
# 部屋番号・階数パターン（より包括的）
_ROOM = re.compile(r"(?:\d{1,4}\s*[号]|\d{1,3}\s*F|\d{1,3}\s*階|#\s*\d{1,4}|-\d{1,4}|\d{1,4}\s*室)")
# ノイズ語（拡張版）
_NOISE_TOKENS = [
    "掲載用", "チラシ", "新着", "価格改定", "更新日", "No.", "Ｎｏ．", "物件No", 
    "NEW", "更新", "改定", "値下げ", "成約", "商談中", "図面", "間取り"
]
# 括弧内のノイズパターン
_BRACKET_NOISE = re.compile(r"[（(](?:掲載用|新着|価格改定|更新日|NEW|更新|改定|値下げ)[)）]")


def sanitize_filename(s: str) -> str:
    """
    ファイル名として安全な文字列に変換する
    
    Args:
        s: 入力文字列
        
    Returns:
        サニタイズ済み文字列
    """
    if not s:
        return ""
    
    # 禁止文字を・に置換
    s = re.sub(_FORBIDDEN, "・", s)
    # 全角スペースを半角に統一
    s = s.replace("\u3000", " ")
    # 連続空白を単一空白に
    s = _SPACE.sub(" ", s).strip()
    return s


def clean_name(raw: str) -> Optional[str]:
    """
    物件名からノイズ語を除去し、正規化する
    
    Args:
        raw: 生の物件名文字列
        
    Returns:
        クリーニング済み物件名。極端に短い場合はNone
    """
    if not raw or not raw.strip():
        return None
    
    s = raw.strip()
    
    # 括弧内のノイズを除去
    s = _BRACKET_NOISE.sub(" ", s)
    
    # 部屋番号・階数を除去
    s = _ROOM.sub(" ", s)
    
    # ノイズ語を除去
    for token in _NOISE_TOKENS:
        # 大文字・小文字を区別せず除去
        s = re.sub(re.escape(token), " ", s, flags=re.IGNORECASE)
    
    # ファイル名として安全に
    s = sanitize_filename(s)
    
    # 極端に短い場合は無効とする
    if len(s) < 2:
        return None
        
    # 数字のみの場合も無効とする（部屋番号の可能性）
    if s.isdigit():
        return None
        
    return s


def extract_name_candidates(text: str, max_candidates: int = 10) -> list[str]:
    """
    テキストから物件名候補を抽出する
    
    Args:
        text: 入力テキスト
        max_candidates: 最大候補数
        
    Returns:
        物件名候補のリスト（スコア順）
    """
    if not text:
        return []
    
    lines = [line.strip() for line in text.splitlines()[:50]]  # 先頭50行に限定
    lines = [line for line in lines if len(line) >= 3]  # 短すぎる行は除外
    
    def calculate_score(line: str) -> float:
        """行の物件名らしさをスコア化"""
        if not line:
            return -1
        
        # 記号の多さでペナルティ
        symbol_count = sum(c in "[]（）()/*-—_:;#|<>※→←↑↓★☆●○■□▲△▼▽" for c in line)
        symbol_penalty = symbol_count / max(1, len(line))
        
        # 数字の多さでペナルティ（住所・電話番号等を除外）
        digit_count = sum(c.isdigit() for c in line)
        digit_penalty = digit_count / max(1, len(line)) if digit_count > len(line) * 0.5 else 0
        
        # 長さボーナス（適度な長さが望ましい）
        length_bonus = min(len(line) / 20, 1) if 3 <= len(line) <= 30 else 0
        
        # 日本語文字ボーナス
        japanese_chars = sum(1 for c in line if '\u3040' <= c <= '\u309F' or '\u30A0' <= c <= '\u30FF' or '\u4E00' <= c <= '\u9FAF')
        japanese_bonus = japanese_chars / max(1, len(line))
        
        return japanese_bonus + length_bonus - symbol_penalty - digit_penalty
    
    # スコア順でソート
    candidates = sorted(lines, key=calculate_score, reverse=True)
    return candidates[:max_candidates]