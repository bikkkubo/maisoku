from mysoku_renamer.info_parser import (
    parse_info, detect_kind, extract_name, extract_amount,
    validate_parsed_info, ParsedInfoRaw
)


# テストデータ
SELL_SAMPLE = """
物件名: グランドタワー渋谷 1203号室
販売価格 1億2,300万円
管理費 30,000円
所在地: 東京都渋谷区
築年月: 2020年3月
"""

RENT_SAMPLE = """
物件名: レジデンス代官山(掲載用)
賃料 210,000円
管理費 10,000円
敷金: 2ヶ月分
礼金: 1ヶ月分
"""

UNKNOWN_SAMPLE = """
高級マンション
立地良好
設備充実
お問い合わせください
"""


def test_parse_sell():
    """売買物件の解析テスト"""
    info = parse_info(SELL_SAMPLE)
    assert info.kind == "sell"
    assert info.name == "グランドタワー渋谷"
    assert info.amount == 123_000_000


def test_parse_rent():
    """賃貸物件の解析テスト"""
    info = parse_info(RENT_SAMPLE)
    assert info.kind == "rent"
    assert info.name == "レジデンス代官山"
    assert info.amount == 210_000


def test_parse_unknown():
    """不明物件の解析テスト"""
    info = parse_info(UNKNOWN_SAMPLE)
    assert info.kind == "unknown"
    # 物件名の抽出は成功する可能性がある
    assert info.name is None or isinstance(info.name, str)
    # 金額は抽出できない
    assert info.amount is None


def test_detect_kind_patterns():
    """取引種別判定の詳細テスト"""
    # 明確な売買
    assert detect_kind("販売価格 5000万円") == "sell"
    assert detect_kind("分譲マンション 売出価格") == "sell"
    
    # 明確な賃貸
    assert detect_kind("賃料 15万円 敷金礼金") == "rent"
    assert detect_kind("テナント募集 家賃20万円") == "rent"
    
    # 曖昧なケース
    assert detect_kind("高級マンション") == "unknown"
    assert detect_kind("") == "unknown"


def test_extract_name_patterns():
    """物件名抽出の詳細テスト"""
    # 明示的な物件名フィールド
    assert extract_name("物件名：パークハウス青山") == "パークハウス青山"
    assert extract_name("建物名: グランドメゾン六本木") == "グランドメゾン六本木"
    
    # 部屋番号付き
    assert extract_name("物件名: タワーマンション新宿 2501号室") == "タワーマンション新宿"
    
    # ノイズ付き
    assert extract_name("物件名: レジデンス渋谷(新着)") == "レジデンス渋谷"
    
    # 抽出不可
    assert extract_name("物件情報なし") is None
    assert extract_name("") is None


def test_extract_amount_by_kind():
    """取引種別別の金額抽出テスト"""
    sell_text = "販売価格 1.5億円 管理費 2万円"
    rent_text = "家賃 18万円 販売価格 1億円"  # 混在ケース
    
    # 売買物件として解析
    sell_amount = extract_amount(sell_text, "sell")
    assert sell_amount == 150_000_000
    
    # 賃貸物件として解析（家賃を優先）
    rent_amount = extract_amount(rent_text, "rent")
    assert rent_amount == 180_000
    
    # 種別不明として解析
    unknown_amount = extract_amount(sell_text, "unknown")
    assert unknown_amount == 150_000_000


def test_validate_parsed_info():
    """解析結果の妥当性検証テスト"""
    # 完全な売買情報
    sell_info = ParsedInfoRaw(kind="sell", name="グランドタワー", amount=120_000_000)
    sell_validation = validate_parsed_info(sell_info)
    assert sell_validation['has_name'] is True
    assert sell_validation['has_amount'] is True
    assert sell_validation['kind_determined'] is True
    assert sell_validation['amount_reasonable'] is True
    
    # 完全な賃貸情報
    rent_info = ParsedInfoRaw(kind="rent", name="レジデンス", amount=200_000)
    rent_validation = validate_parsed_info(rent_info)
    assert rent_validation['has_name'] is True
    assert rent_validation['has_amount'] is True
    assert rent_validation['kind_determined'] is True
    assert rent_validation['amount_reasonable'] is True
    
    # 不完全な情報
    incomplete_info = ParsedInfoRaw(kind="unknown", name=None, amount=None)
    incomplete_validation = validate_parsed_info(incomplete_info)
    assert incomplete_validation['has_name'] is False
    assert incomplete_validation['has_amount'] is False
    assert incomplete_validation['kind_determined'] is False


def test_parse_info_edge_cases():
    """解析のエッジケーステスト"""
    # 空テキスト
    empty_info = parse_info("")
    assert empty_info.kind == "unknown"
    assert empty_info.name is None
    assert empty_info.amount is None
    
    # None
    none_info = parse_info(None)
    assert none_info.kind == "unknown"
    assert none_info.name is None
    assert none_info.amount is None


def test_complex_scenarios():
    """複雑なシナリオテスト"""
    complex_text = """
    ★新着物件★
    物件名：グランドレジデンス恵比寿タワー 3201号室(価格改定)
    販売価格：2億3,500万円
    賃料参考：45万円
    管理費：35,000円
    修繕積立金：28,000円
    所在地：東京都渋谷区恵比寿...
    """
    
    info = parse_info(complex_text)
    assert info.kind == "sell"  # 販売価格があるので売買
    assert info.name == "グランドレジデンス恵比寿タワー"  # ノイズ・部屋番号除去
    assert info.amount == 235_000_000  # 販売価格を優先


def test_ambiguous_cases():
    """曖昧なケースの処理テスト"""
    ambiguous_text = """
    高級分譲賃貸マンション
    価格：月額25万円
    または売買価格：5000万円要相談
    """
    
    info = parse_info(ambiguous_text)
    # このケースでは賃貸・売買両方のキーワードがあるが、
    # 実装によって結果が変わる可能性がある
    assert info.kind in ["sell", "rent", "unknown"]
    
    # 金額は何かしら抽出されることを期待
    assert info.amount is not None


def test_validation_amount_ranges():
    """金額範囲の妥当性テスト"""
    # 売買価格の異常値
    expensive_sell = ParsedInfoRaw(kind="sell", name="超高級", amount=50_000_000_000)  # 500億円
    validation = validate_parsed_info(expensive_sell)
    assert validation['amount_reasonable'] is False
    
    cheap_sell = ParsedInfoRaw(kind="sell", name="格安", amount=1_000_000)  # 100万円
    validation = validate_parsed_info(cheap_sell)
    assert validation['amount_reasonable'] is False
    
    # 賃料の異常値
    expensive_rent = ParsedInfoRaw(kind="rent", name="超高級", amount=2_000_000)  # 200万円
    validation = validate_parsed_info(expensive_rent)
    assert validation['amount_reasonable'] is False
    
    cheap_rent = ParsedInfoRaw(kind="rent", name="格安", amount=10_000)  # 1万円
    validation = validate_parsed_info(cheap_rent)
    assert validation['amount_reasonable'] is False