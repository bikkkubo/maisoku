from __future__ import annotations
import re
from pathlib import Path
from typing import Optional

from .property_cleaner import sanitize_filename
from .price_normalizer import format_price_sell, format_price_rent
from .info_parser import ParsedInfoRaw


def _format_amount_for_filename(amount: int, kind: str) -> str:
    """
    金額を命名用にフォーマットする
    
    Args:
        amount: 円単位の金額
        kind: 取引種別 ("sell" | "rent")
        
    Returns:
        フォーマット済み金額文字列
    """
    if kind == "sell":
        return format_price_sell(amount)
    elif kind == "rent":
        return format_price_rent(amount)
    else:
        return f"{amount:,}円"


def _truncate_filename(filename: str, max_bytes: int = 200) -> str:
    """
    ファイル名を適切な長さに切り詰める（UTF-8バイト数考慮）
    
    Args:
        filename: 入力ファイル名
        max_bytes: 最大バイト数
        
    Returns:
        切り詰められたファイル名
    """
    if not filename:
        return filename
    
    encoded = filename.encode('utf-8')
    if len(encoded) <= max_bytes:
        return filename
    
    # バイト単位で切り詰め、文字境界を保つ
    truncated = encoded[:max_bytes]
    try:
        # UTF-8のデコードを試行
        return truncated.decode('utf-8')
    except UnicodeDecodeError:
        # 文字境界で切れていない場合、安全な位置まで戻る
        for i in range(len(truncated) - 1, max(0, len(truncated) - 4), -1):
            try:
                return truncated[:i].decode('utf-8')
            except UnicodeDecodeError:
                continue
    
    # 最悪の場合は元のファイル名の前半部分を返す
    return filename[:max_bytes // 4]  # 安全マージン


def generate_filename(info: ParsedInfoRaw, original_path: Path) -> str:
    """
    物件情報から新しいファイル名を生成する
    
    Args:
        info: 解析済み物件情報
        original_path: 元のファイルパス
        
    Returns:
        新しいファイル名（拡張子含む）
    """
    # 元のファイル名から拡張子を取得
    original_stem = original_path.stem
    extension = original_path.suffix
    
    # 基本的なサニタイズ
    def safe_name(name: Optional[str]) -> str:
        if not name:
            return "名称未取得"
        sanitized = sanitize_filename(name.strip())
        return sanitized if sanitized else "名称未取得"
    
    # 命名規則に従ってファイル名を生成
    if info.kind == "sell" and info.name and info.amount:
        # 売買物件
        property_name = safe_name(info.name)
        amount_str = _format_amount_for_filename(info.amount, "sell")
        filename_stem = f"【売買】{property_name}_{amount_str}"
        
    elif info.kind == "rent" and info.name and info.amount:
        # 賃貸物件
        property_name = safe_name(info.name)
        amount_str = _format_amount_for_filename(info.amount, "rent")
        filename_stem = f"【賃貸】{property_name}_家賃{amount_str}"
        
    else:
        # その他（情報不足・不明）
        base_name = safe_name(info.name) if info.name else sanitize_filename(original_stem)
        
        if info.kind == "sell" and info.name and not info.amount:
            filename_stem = f"【売買】{safe_name(info.name)}_価格未取得"
        elif info.kind == "rent" and info.name and not info.amount:
            filename_stem = f"【賃貸】{safe_name(info.name)}_家賃未取得"
        elif info.name and not info.amount:
            filename_stem = f"【その他】{safe_name(info.name)}_取引種別未取得"
        else:
            filename_stem = f"【その他】{base_name}_未確定"
    
    # 最終的なサニタイズ
    filename_stem = sanitize_filename(filename_stem)
    
    # 長さ制限適用
    full_filename = filename_stem + extension
    full_filename = _truncate_filename(full_filename)
    
    return full_filename


def generate_collision_free_filename(target_filename: str, target_dir: Path) -> str:
    """
    ディレクトリ内でのファイル名衝突を回避する
    
    Args:
        target_filename: 希望するファイル名
        target_dir: 対象ディレクトリ
        
    Returns:
        衝突を回避したファイル名
    """
    if not target_dir.exists():
        return target_filename
    
    target_path = target_dir / target_filename
    if not target_path.exists():
        return target_filename
    
    # 拡張子とステムを分離
    target_path_obj = Path(target_filename)
    stem = target_path_obj.stem
    suffix = target_path_obj.suffix
    
    # 連番を付けて衝突回避
    for i in range(1, 1000):  # 最大999まで試行
        new_filename = f"{stem}-{i}{suffix}"
        new_path = target_dir / new_filename
        if not new_path.exists():
            return new_filename
    
    # 999まで試してもダメな場合はタイムスタンプを付与
    import time
    timestamp = int(time.time())
    return f"{stem}-{timestamp}{suffix}"


def validate_filename(filename: str) -> dict[str, bool]:
    """
    生成されたファイル名の妥当性を検証する
    
    Args:
        filename: 検証対象のファイル名
        
    Returns:
        検証結果の辞書
    """
    if not filename:
        return {
            'has_content': False,
            'has_extension': False,
            'safe_chars': False,
            'reasonable_length': False
        }
    
    # 基本的な内容があるか
    has_content = len(filename.strip()) > 0
    
    # 拡張子があるか
    has_extension = '.' in filename and len(Path(filename).suffix) > 0
    
    # 危険な文字が含まれていないか
    forbidden_chars = r'[\\/:*?"<>|]'
    safe_chars = not re.search(forbidden_chars, filename)
    
    # 妥当な長さか
    reasonable_length = 5 <= len(filename) <= 255
    
    return {
        'has_content': has_content,
        'has_extension': has_extension,
        'safe_chars': safe_chars,
        'reasonable_length': reasonable_length
    }


def extract_naming_info_from_filename(filename: str) -> dict[str, Optional[str]]:
    """
    ファイル名から命名情報を抽出する（逆解析）
    
    Args:
        filename: 解析対象のファイル名
        
    Returns:
        抽出された情報の辞書
    """
    if not filename:
        return {'kind': None, 'property_name': None, 'amount': None}
    
    # 拡張子を除去
    stem = Path(filename).stem
    
    # パターンマッチング
    patterns = [
        (r'【売買】(.+?)_(.+)', 'sell'),
        (r'【賃貸】(.+?)_家賃(.+)', 'rent'),
        (r'【その他】(.+?)_(.+)', 'other')
    ]
    
    for pattern, kind in patterns:
        match = re.search(pattern, stem)
        if match:
            if kind in ['sell', 'other']:
                return {
                    'kind': kind,
                    'property_name': match.group(1),
                    'amount': match.group(2) if len(match.groups()) > 1 else None
                }
            elif kind == 'rent':
                return {
                    'kind': kind,
                    'property_name': match.group(1),
                    'amount': match.group(2) if len(match.groups()) > 1 else None
                }
    
    return {'kind': None, 'property_name': None, 'amount': None}