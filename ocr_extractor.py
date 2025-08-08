import os
import io
import re
from typing import List, Tuple, Optional
from pdf2image import convert_from_path
from PIL import Image
import pytesseract

KANJI_NUM = str.maketrans("０１２３４５６７８９．，", "0123456789.,")

RENT_TOKENS = ["賃料", "月額", "家賃"]
SALE_TOKENS = ["価格", "販売価格", "総額"]
TAX_IN_TOKENS = ["税込", "内税"]
TAX_EX_TOKENS = ["税別", "外税"]

def _extract_text_from_pdf(pdf_path: str, dpi: int = 300) -> str:
    # Convert each page to image, OCR with tesseract jpn + jpn_vert
    pages = convert_from_path(pdf_path, dpi=dpi)
    texts = []
    for img in pages:
        # Try horizontal first
        txt1 = pytesseract.image_to_string(img, lang='jpn')
        # Vertical often appears in ad flyers
        txt2 = pytesseract.image_to_string(img, lang='jpn_vert')
        texts.append(txt1 + "\n" + txt2)
    text = "\n".join(texts)
    # normalize full-width numbers and punctuation
    text = text.translate(KANJI_NUM)
    return text

def _extract_text_from_image_path(img_path: str) -> str:
    img = Image.open(img_path)
    txt1 = pytesseract.image_to_string(img, lang='jpn')
    txt2 = pytesseract.image_to_string(img, lang='jpn_vert')
    text = (txt1 + "\n" + txt2).translate(KANJI_NUM)
    return text

def _find_tokens_count(text: str, tokens: List[str]) -> int:
    n = 0
    for t in tokens:
        n += len(re.findall(re.escape(t), text))
    return n

def _find_prices_yen(text: str, label_tokens: List[str]) -> List[Tuple[int, int, int]]:
    # Returns list of (yen_value, start_idx, end_idx)
    results = []
    # pattern: <label> ... <number> (円|万円)
    pattern = re.compile(rf'({"|".join([re.escape(t) for t in label_tokens])}).{{0,30}}?(\d[\d,]*\.?\d?)\s*(万?円)')
    for m in pattern.finditer(text):
        num_str = m.group(2).replace(",", "")
        unit = m.group(3)
        try:
            if "万円" in unit:
                val = float(num_str) * 10_000
            else:
                val = float(num_str)
            results.append((int(round(val)), m.start(2), m.end(3)))
        except Exception:
            continue
    return results

def _is_tax_ex(text: str, span: Tuple[int, int]) -> Optional[str]:
    # Look around the price span for 税別/税込 hints
    window = 30
    s = max(0, span[0]-window)
    e = min(len(text), span[1]+window)
    around = text[s:e]
    if any(t in around for t in TAX_EX_TOKENS):
        return "税別"
    if any(t in around for t in TAX_IN_TOKENS):
        return "税込"
    return None

def _adjust_tax(yen: int, tax_hint: Optional[str]) -> int:
    if tax_hint == "税別":
        return int(round(yen * 1.10))
    return yen

def detect_room_label(text: str) -> Optional[str]:
    # Common patterns: 101, 1001, 1F, 2F, B1F, PH
    m = re.search(r'(?:号室|部屋|所在階)\s*[:：]?\s*([BP]?\d{1,3}F|PH|\d{1,3}[A-Za-z]?)', text)
    if m:
        return m.group(1)
    # fallback: naked pattern
    m2 = re.search(r'([BP]?\d{1,3}F|PH|\d{1,3}[A-Za-z]?)\s*(?:室)?', text)
    if m2:
        return m2.group(1)
    return None

def detect_property_name(text: str) -> Optional[str]:
    # Try explicit labels
    m = re.search(r'(?:物件名|建物名|名称)[:：\s]*([^\n]+)', text)
    if m:
        return m.group(1).strip()
    # fallback: first non-empty line that is relatively short
    for line in text.splitlines():
        line = line.strip()
        if 1 <= len(line) <= 30 and not any(tok in line for tok in ["賃料", "価格", "管理費", "敷金", "礼金", "面積", "所在地"]):
            return line
    return None

def detect_area_sqm(text: str) -> Optional[float]:
    m = re.search(r'(?:専有|建物|土地)面積[^\d]*(\d{1,3}(?:\.\d{1,2})?)\s*㎡', text)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None

def extract_from_pdf(pdf_path: str):
    text = _extract_text_from_pdf(pdf_path)
    # Classify
    rent_hits = _find_tokens_count(text, RENT_TOKENS)
    sale_hits = _find_tokens_count(text, SALE_TOKENS)
    detected_type = "rent" if rent_hits >= sale_hits else "sale" if sale_hits > 0 else "unknown"

    # Fields
    pname = detect_property_name(text)
    room = detect_room_label(text)
    area = detect_area_sqm(text)

    # Prices
    rents = _find_prices_yen(text, RENT_TOKENS)
    sales = _find_prices_yen(text, SALE_TOKENS)

    rent_values = []
    tax_mode_hint = "不明"
    if rents:
        for (yen, s, e) in rents:
            hint = _is_tax_ex(text, (s, e))
            yen_adj = _adjust_tax(yen, hint)
            rent_values.append(yen_adj)
            if hint == "税込":
                tax_mode_hint = "税込"
            elif hint == "税別":
                tax_mode_hint = "税別"
    sale_price = None
    if sales:
        # take first sale price as canonical
        (yen, s, e) = sales[0]
        hint = _is_tax_ex(text, (s, e))
        sale_price = _adjust_tax(yen, hint)
        if hint == "税込":
            tax_mode_hint = "税込"
        elif hint == "税別":
            tax_mode_hint = "税別"

    return {
        "text": text,
        "detected_type": detected_type,
        "property_name": pname,
        "room_label": room,
        "area_sqm": area,
        "rent_values_yen": sorted(set(rent_values)) if rent_values else None,
        "sale_price_yen": sale_price,
        "tax_mode": tax_mode_hint,
    }

def extract_from_path(file_path: str):
    lower = file_path.lower()
    if lower.endswith(".pdf"):
        text = _extract_text_from_pdf(file_path)
    elif lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
        text = _extract_text_from_image_path(file_path)
    else:
        # fallback: try image first then pdf
        try:
            text = _extract_text_from_image_path(file_path)
        except Exception:
            text = _extract_text_from_pdf(file_path)

    # Classify
    rent_hits = _find_tokens_count(text, RENT_TOKENS)
    sale_hits = _find_tokens_count(text, SALE_TOKENS)
    detected_type = "rent" if rent_hits >= sale_hits else "sale" if sale_hits > 0 else "unknown"

    # Fields
    pname = detect_property_name(text)
    room = detect_room_label(text)
    area = detect_area_sqm(text)

    # Prices
    rents = _find_prices_yen(text, RENT_TOKENS)
    sales = _find_prices_yen(text, SALE_TOKENS)

    rent_values = []
    tax_mode_hint = "不明"
    if rents:
        for (yen, s, e) in rents:
            hint = _is_tax_ex(text, (s, e))
            yen_adj = _adjust_tax(yen, hint)
            rent_values.append(yen_adj)
            if hint == "税込":
                tax_mode_hint = "税込"
            elif hint == "税別":
                tax_mode_hint = "税別"
    sale_price = None
    if sales:
        # take first sale price as canonical
        (yen, s, e) = sales[0]
        hint = _is_tax_ex(text, (s, e))
        sale_price = _adjust_tax(yen, hint)
        if hint == "税込":
            tax_mode_hint = "税込"
        elif hint == "税別":
            tax_mode_hint = "税別"

    return {
        "text": text,
        "detected_type": detected_type,
        "property_name": pname,
        "room_label": room,
        "area_sqm": area,
        "rent_values_yen": sorted(set(rent_values)) if rent_values else None,
        "sale_price_yen": sale_price,
        "tax_mode": tax_mode_hint,
    }
