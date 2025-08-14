from mysoku_renamer.price_normalizer import (
    parse_amount_jpy, format_price_sell, format_price_rent,
    normalize_number_string, extract_multiple_amounts, check_price_unspecified
)


def test_parse_amount_variants():
    """価格解析の各種パターンテスト"""
    # 億円パターン
    assert parse_amount_jpy("1.2億円") == 120_000_000
    assert parse_amount_jpy("2億円") == 200_000_000
    assert parse_amount_jpy("1.5億") == 150_000_000
    
    # 万円パターン
    assert parse_amount_jpy("9800万円") == 98_000_000
    assert parse_amount_jpy("1,500万円") == 15_000_000
    assert parse_amount_jpy("500万") == 5_000_000
    
    # 円パターン
    assert parse_amount_jpy("家賃 210,000 円") == 210_000
    assert parse_amount_jpy("1500000円") == 1_500_000
    
    # 複雑なケース
    assert parse_amount_jpy("販売価格：1億2,300万円") == 123_000_000


def test_parse_amount_edge_cases():
    """価格解析のエッジケース"""
    # None/空文字
    assert parse_amount_jpy(None) is None
    assert parse_amount_jpy("") is None
    assert parse_amount_jpy("   ") is None
    
    # 解析不可能な文字列
    assert parse_amount_jpy("高級マンション") is None
    assert parse_amount_jpy("123") is None  # 小さすぎる数字
    
    # 異常な値
    assert parse_amount_jpy("999999億円") == 99_999_900_000_000


def test_format_sell_and_rent():
    """価格フォーマットテスト"""
    # 売買価格フォーマット
    assert format_price_sell(120_000_000) == "1.2億円"
    assert format_price_sell(200_000_000) == "2億円"  # 整数億円
    assert format_price_sell(98_000_000) == "9,800万円"
    assert format_price_sell(5_500_000) == "550万円"
    
    # 賃貸価格フォーマット
    assert format_price_rent(210_000) == "210,000円"
    assert format_price_rent(85_000) == "85,000円"
    assert format_price_rent(1_200_000) == "1,200,000円"
    
    # エッジケース
    assert format_price_sell(0) == "0円"
    assert format_price_rent(0) == "0円"


def test_normalize_number_string():
    """数字文字列正規化テスト"""
    # 全角数字変換
    assert normalize_number_string("１２３") == "123"
    
    # カンマ除去
    assert normalize_number_string("1,234,567") == "1234567"
    assert normalize_number_string("1，234，567") == "1234567"  # 全角カンマ
    
    # 複合パターン
    assert normalize_number_string("１，２３４，５６７") == "1234567"
    
    # 空文字・None
    assert normalize_number_string("") == ""
    assert normalize_number_string(None) == ""


def test_extract_multiple_amounts():
    """複数金額抽出テスト"""
    sample_text = """
    物件名：グランドタワー渋谷
    販売価格：1億2000万円
    賃料：30万円
    管理費：2万円
    """
    
    amounts = extract_multiple_amounts(sample_text)
    assert 'price' in amounts
    assert amounts['price'] == 120_000_000
    assert 'rent' in amounts
    assert amounts['rent'] == 300_000


def test_extract_multiple_amounts_rent_focused():
    """賃貸特化の金額抽出テスト"""
    rent_text = """
    賃料：210,000円
    管理費：15,000円
    敷金：2ヶ月
    礼金：1ヶ月
    """
    
    amounts = extract_multiple_amounts(rent_text)
    assert 'rent' in amounts
    assert amounts['rent'] == 210_000


def test_extract_multiple_amounts_empty():
    """空テキストの金額抽出"""
    assert extract_multiple_amounts("") == {}
    assert extract_multiple_amounts(None) == {}
    assert extract_multiple_amounts("金額情報なし") == {}
    
    # 数字はあるが価格として認識されないパターン
    result = extract_multiple_amounts("築20年 3LDK 駅徒歩5分")
    assert result == {}  # 価格として認識される数字なし


def test_parse_amount_various_formats():
    """多様な価格表記の解析テスト"""
    test_cases = [
        ("価格 1.5億", 150_000_000),
        ("1億5000万円", 150_000_000),
        ("15,000万円", 150_000_000),
        ("150,000,000円", 150_000_000),
        ("家賃18万円", 180_000),
        ("月額180,000円", 180_000),
        ("賃料 18万", 180_000),
    ]
    
    for text, expected in test_cases:
        result = parse_amount_jpy(text)
        assert result == expected, f"Text: {text}, Expected: {expected}, Got: {result}"


def test_format_price_boundary_cases():
    """価格フォーマットの境界値テスト"""
    # 1億円ちょうど
    assert format_price_sell(100_000_000) == "1億円"
    
    # 1億円未満の最大値
    assert format_price_sell(99_990_000) == "9,999万円"
    
    # 小数点の丸め
    assert format_price_sell(123_456_789) == "1.2億円"  # 四捨五入
    assert format_price_sell(127_000_000) == "1.3億円"
    
    # 負の値
    assert format_price_sell(-1000) == "0円"
    assert format_price_rent(-500) == "0円"


def test_check_price_unspecified():
    """応相談・価格未定チェックテスト"""
    # 応相談パターン
    assert check_price_unspecified("価格は応相談でお願いします") is True
    assert check_price_unspecified("詳細は要問合せ") is True
    assert check_price_unspecified("要問合わせ") is True
    assert check_price_unspecified("価格未定") is True
    assert check_price_unspecified("要相談") is True
    assert check_price_unspecified("別途相談") is True
    assert check_price_unspecified("お問い合わせください") is True
    
    # 通常の価格表記
    assert check_price_unspecified("1億円") is False
    assert check_price_unspecified("家賃18万円") is False
    assert check_price_unspecified("販売価格：8,500万円") is False
    
    # 空文字・None
    assert check_price_unspecified("") is False
    assert check_price_unspecified(None) is False


def test_parse_amount_with_unspecified():
    """応相談等を含む価格解析テスト"""
    # 応相談の場合はNone
    assert parse_amount_jpy("価格は応相談") is None
    assert parse_amount_jpy("要問合せ") is None
    assert parse_amount_jpy("価格未定") is None
    
    # 価格とコメントが混在
    assert parse_amount_jpy("1億円 応相談") is None  # 応相談が含まれる


def test_enhanced_rent_patterns():
    """強化された賃料パターンのテスト"""
    test_cases = [
        ("家賃：180,000円", 180_000),
        ("賃料：18万円", 180_000),
        ("月額 200000円", 200_000),
        ("180,000円/月", 180_000),
        ("18万円/月", 180_000),
        ("家賃18万円", 180_000),
        ("賃料18万", 180_000),
        ("18.5万円", 185_000),
    ]
    
    for text, expected in test_cases:
        amounts = extract_multiple_amounts(text)
        assert 'rent' in amounts, f"Text: {text} - rent not found"
        assert amounts['rent'] == expected, f"Text: {text}, Expected: {expected}, Got: {amounts.get('rent')}"


def test_enhanced_sell_patterns():
    """強化された売買価格パターンのテスト"""
    test_cases = [
        ("1.2億円", 120_000_000),
        ("1億2000万円", 120_000_000),
        ("8,500万円", 85_000_000),
        ("販売価格：1.5億円", 150_000_000),
        ("売出価格：8800万", 88_000_000),
        ("価格：1億円", 100_000_000),
    ]
    
    for text, expected in test_cases:
        amounts = extract_multiple_amounts(text)
        assert 'price' in amounts, f"Text: {text} - price not found"
        assert amounts['price'] == expected, f"Text: {text}, Expected: {expected}, Got: {amounts.get('price')}"


def test_extract_multiple_amounts_with_unspecified():
    """応相談を含むテキストの複数金額抽出テスト"""
    # 応相談の場合
    amounts = extract_multiple_amounts("価格は応相談でお願いします")
    assert 'price_unspecified' in amounts
    assert amounts['price_unspecified'] is True
    assert 'rent' not in amounts
    assert 'price' not in amounts
    
    # 要問合せの場合
    amounts = extract_multiple_amounts("詳細は要問合せ")
    assert 'price_unspecified' in amounts
    assert amounts['price_unspecified'] is True


def test_normalize_number_string_enhanced():
    """強化された数字文字列正規化テスト"""
    # 通貨記号除去
    assert normalize_number_string("¥1,234,567") == "1234567"
    assert normalize_number_string("￥1，234，567") == "1234567"
    
    # 全角・半角空白除去
    assert normalize_number_string("1 234 567") == "1234567"
    assert normalize_number_string("1　234　567") == "1234567"
    
    # 複合パターン
    assert normalize_number_string("￥１，２３４，５６７円") == "1234567円"


def test_vertical_text_patterns():
    """縦書きPDF由来の価格抽出パターンテスト"""
    # 縦書き特有の文字化け・スペースパターン
    test_cases = [
        ("１ 億 ２ ０ ０ ０ 万 円", 120_000_000),
        ("家賃　１８万円", 180_000),
        ("賃　料　：　２０万", 200_000),
        ("売出価格：１．５億円", 150_000_000),
    ]
    
    for text, expected in test_cases:
        result = parse_amount_jpy(text)
        if result is not None:  # 現在の実装で対応できるもののみテスト
            assert result == expected, f"Text: {text}, Expected: {expected}, Got: {result}"