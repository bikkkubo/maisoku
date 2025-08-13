from mysoku_renamer.property_cleaner import clean_name, sanitize_filename, extract_name_candidates


def test_clean_name_basic():
    """基本的な物件名クリーニングテスト"""
    # 部屋番号除去
    assert clean_name("グランドタワー渋谷 1203号室") == "グランドタワー渋谷"
    assert clean_name("レジデンス代官山 304号") == "レジデンス代官山"
    assert clean_name("パークハイツ新宿 15F") == "パークハイツ新宿"
    
    # 括弧内ノイズ除去
    assert clean_name("レジデンス代官山(掲載用)") == "レジデンス代官山"
    assert clean_name("グランドメゾン青山（新着）") == "グランドメゾン青山"
    
    # 複合パターン
    assert clean_name("タワーマンション六本木 2501号室(価格改定)") == "タワーマンション六本木"


def test_clean_name_edge_cases():
    """エッジケースのテスト"""
    # None/空文字
    assert clean_name(None) is None
    assert clean_name("") is None
    assert clean_name("   ") is None
    
    # 短すぎる場合
    assert clean_name("A") is None
    assert clean_name("12") is None  # 数字のみ
    
    # ノイズ語のみ
    assert clean_name("掲載用") is None
    assert clean_name("新着 更新日") is None


def test_sanitize_filename():
    """ファイル名サニタイズテスト"""
    # 禁止文字の置換
    forbidden_chars = '\\/:*?"<>|'
    input_str = f"テスト{forbidden_chars}ファイル"
    result = sanitize_filename(input_str)
    for char in forbidden_chars:
        assert char not in result
    assert "テスト" in result
    assert "ファイル" in result
    
    # 全角スペース変換
    assert sanitize_filename("テスト　ファイル") == "テスト ファイル"
    
    # 連続スペース正規化
    assert sanitize_filename("テスト    ファイル") == "テスト ファイル"
    assert sanitize_filename("  テスト  ") == "テスト"


def test_extract_name_candidates():
    """物件名候補抽出テスト"""
    sample_text = """
    物件No: 12345
    ★新着★グランドタワー渋谷 1203号室
    販売価格: 1億2000万円
    所在地: 東京都渋谷区...
    築年月: 2020年3月
    """
    
    candidates = extract_name_candidates(sample_text)
    assert len(candidates) > 0
    
    # 物件名らしい行が上位に来ることを確認
    found_property_name = False
    for candidate in candidates[:3]:  # 上位3件をチェック
        if "グランドタワー渋谷" in candidate:
            found_property_name = True
            break
    assert found_property_name


def test_extract_name_candidates_empty():
    """空テキストの候補抽出テスト"""
    assert extract_name_candidates("") == []
    assert extract_name_candidates(None) == []


def test_clean_name_noise_tokens():
    """ノイズ語除去の包括テスト"""
    test_cases = [
        ("マンション青山 掲載用", "マンション青山"),
        ("レジデンス NEW 新着", "レジデンス"),
        ("タワー更新価格改定", "タワー"),
        ("物件No12345 グランドハイツ", "グランドハイツ"),
        ("値下げ！パークハウス", "パークハウス"),
    ]
    
    for input_str, expected in test_cases:
        result = clean_name(input_str)
        assert result == expected, f"Input: {input_str}, Expected: {expected}, Got: {result}"


def test_clean_name_room_patterns():
    """部屋番号・階数パターンの除去テスト"""
    test_cases = [
        ("グランドメゾン 201号", "グランドメゾン"),
        ("タワー住宅 15F", "タワー住宅"),
        ("レジデンス 3階", "レジデンス"),
        ("ハイツ#405", "ハイツ"),
        ("マンション-302", "マンション"),
        ("アパート 101室", "アパート"),
    ]
    
    for input_str, expected in test_cases:
        result = clean_name(input_str)
        assert result == expected, f"Input: {input_str}, Expected: {expected}, Got: {result}"