import math
import re
from typing import List, Optional

FORBIDDEN = r'[\\/:*?"<>|]'

def sanitize_text(s: str) -> str:
    # Normalize spaces and forbid characters
    s = s.replace('\t',' ').replace('\r',' ').replace('\n',' ').strip()
    # Collapse spaces
    s = re.sub(r'\s+', ' ', s)
    # Replace forbidden with underscore
    s = re.sub(FORBIDDEN, '_', s)
    return s

def yen_to_sale_label(yen: int) -> str:
    # 1億未満→X,XXX万円 表記。1億以上→N億X,XXX万円（万円単位四捨五入）
    man = round(yen / 10_000)  # 万円単位丸め
    if yen < 100_000_000:
        return f"{man:,}万円"
    oku = man // 10_000  # 1億=10000万円
    rest_man = man - oku * 10_000
    return f"{oku}億{rest_man:,}万円"

def format_rent_yen(yen: int) -> str:
    return f"{yen:,}円"

def build_filename_rent_single(property_name: str, room_label: Optional[str], yen: int) -> str:
    pname = sanitize_text(property_name or '物件名不明')
    rlabel = sanitize_text(room_label) if room_label else None
    price = format_rent_yen(yen)
    if rlabel:
        return f"【賃貸】{pname}_{rlabel}_{price}.pdf"
    return f"【賃貸】{pname}_{price}.pdf"

def build_filename_rent_range(property_name: str, min_yen: int, max_yen: int) -> str:
    pname = sanitize_text(property_name or '物件名不明')
    return f"【賃貸】{pname}_{format_rent_yen(min_yen)}〜{format_rent_yen(max_yen)}.pdf"

def build_filename_sale(property_name: str, room_label: Optional[str], area_sqm: Optional[float], yen: int) -> str:
    pname = sanitize_text(property_name or '物件名不明')
    rlabel = sanitize_text(room_label) if room_label else None
    area = None
    if isinstance(area_sqm, (int, float)):
        area = f"{area_sqm:.2f}㎡"
    price = yen_to_sale_label(yen)
    if rlabel and area:
        return f"【売買】{pname}_{rlabel}_{area}_{price}.pdf"
    if rlabel:
        return f"【売買】{pname}_{rlabel}_{price}.pdf"
    if area:
        return f"【売買】{pname}_{area}_{price}.pdf"
    return f"【売買】{pname}_{price}.pdf"
