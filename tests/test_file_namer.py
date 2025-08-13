from pathlib import Path
import tempfile
import pytest

from mysoku_renamer.file_namer import (
    generate_filename, generate_collision_free_filename, validate_filename,
    extract_naming_info_from_filename, _format_amount_for_filename, _truncate_filename
)
from mysoku_renamer.info_parser import ParsedInfoRaw


def test_generate_filename_sell_with_amount():
    """売買物件（金額あり）の命名テスト"""
    info = ParsedInfoRaw(kind="sell", name="グランドタワー渋谷", amount=123_000_000)
    original_path = Path("/test/original.pdf")
    
    result = generate_filename(info, original_path)
    assert result == "【売買】グランドタワー渋谷_1.2億円.pdf"


def test_generate_filename_sell_under_100m():
    """売買物件（1億円未満）の命名テスト"""
    info = ParsedInfoRaw(kind="sell", name="パークハウス新宿", amount=85_000_000)
    original_path = Path("/test/original.pdf")
    
    result = generate_filename(info, original_path)
    assert result == "【売買】パークハウス新宿_8,500万円.pdf"


def test_generate_filename_sell_exactly_100m():
    """売買物件（ちょうど1億円）の命名テスト"""
    info = ParsedInfoRaw(kind="sell", name="メゾン青山", amount=100_000_000)
    original_path = Path("/test/original.pdf")
    
    result = generate_filename(info, original_path)
    assert result == "【売買】メゾン青山_1億円.pdf"


def test_generate_filename_rent_with_amount():
    """賃貸物件（金額あり）の命名テスト"""
    info = ParsedInfoRaw(kind="rent", name="レジデンス恵比寿", amount=210_000)
    original_path = Path("/test/original.pdf")
    
    result = generate_filename(info, original_path)
    assert result == "【賃貸】レジデンス恵比寿_家賃210,000円.pdf"


def test_generate_filename_sell_missing_amount():
    """売買物件（金額なし）の命名テスト"""
    info = ParsedInfoRaw(kind="sell", name="タワーマンション六本木", amount=None)
    original_path = Path("/test/original.pdf")
    
    result = generate_filename(info, original_path)
    assert result == "【売買】タワーマンション六本木_価格未取得.pdf"


def test_generate_filename_rent_missing_amount():
    """賃貸物件（金額なし）の命名テスト"""
    info = ParsedInfoRaw(kind="rent", name="アパート代官山", amount=None)
    original_path = Path("/test/original.pdf")
    
    result = generate_filename(info, original_path)
    assert result == "【賃貸】アパート代官山_家賃未取得.pdf"


def test_generate_filename_unknown():
    """不明物件の命名テスト"""
    info = ParsedInfoRaw(kind="unknown", name="高級マンション", amount=None)
    original_path = Path("/test/original.pdf")
    
    result = generate_filename(info, original_path)
    assert result == "【その他】高級マンション_取引種別未取得.pdf"


def test_generate_filename_missing_name():
    """物件名なしの命名テスト"""
    info = ParsedInfoRaw(kind="sell", name=None, amount=50_000_000)
    original_path = Path("/test/sample_property.pdf")
    
    result = generate_filename(info, original_path)
    assert result == "【その他】sample_property_未確定.pdf"


def test_generate_filename_all_missing():
    """すべて情報なしの命名テスト"""
    info = ParsedInfoRaw(kind="unknown", name=None, amount=None)
    original_path = Path("/test/mystery.pdf")
    
    result = generate_filename(info, original_path)
    assert result == "【その他】mystery_未確定.pdf"


def test_generate_filename_forbidden_chars():
    """禁止文字を含む物件名の処理テスト"""
    info = ParsedInfoRaw(kind="sell", name='テスト/物件:名前*危険"文字<含む>', amount=80_000_000)
    original_path = Path("/test/original.pdf")
    
    result = generate_filename(info, original_path)
    # 禁止文字が・に置換されることを確認
    assert "/" not in result
    assert "*" not in result
    assert '"' not in result
    assert "【売買】" in result
    assert "8,000万円" in result


def test_generate_collision_free_filename():
    """衝突回避テスト"""
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        
        # 既存ファイルを作成
        existing_file = temp_dir / "【売買】テスト物件_1億円.pdf"
        existing_file.touch()
        
        # 衝突回避ファイル名の生成
        result = generate_collision_free_filename("【売買】テスト物件_1億円.pdf", temp_dir)
        assert result == "【売買】テスト物件_1億円-1.pdf"
        
        # さらに衝突する場合
        collision_file = temp_dir / "【売買】テスト物件_1億円-1.pdf"
        collision_file.touch()
        
        result2 = generate_collision_free_filename("【売買】テスト物件_1億円.pdf", temp_dir)
        assert result2 == "【売買】テスト物件_1億円-2.pdf"


def test_generate_collision_free_no_collision():
    """衝突なしの場合のテスト"""
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        
        result = generate_collision_free_filename("【売買】新物件_2億円.pdf", temp_dir)
        assert result == "【売買】新物件_2億円.pdf"


def test_validate_filename():
    """ファイル名妥当性検証テスト"""
    # 正常なファイル名
    valid_result = validate_filename("【売買】テスト物件_1億円.pdf")
    assert valid_result['has_content'] is True
    assert valid_result['has_extension'] is True
    assert valid_result['safe_chars'] is True
    assert valid_result['reasonable_length'] is True
    
    # 空ファイル名
    empty_result = validate_filename("")
    assert empty_result['has_content'] is False
    
    # 拡張子なし
    no_ext_result = validate_filename("テストファイル")
    assert no_ext_result['has_extension'] is False
    
    # 危険な文字
    unsafe_result = validate_filename("テスト/ファイル*.pdf")
    assert unsafe_result['safe_chars'] is False
    
    # 長すぎるファイル名
    long_name = "あ" * 300 + ".pdf"
    long_result = validate_filename(long_name)
    assert long_result['reasonable_length'] is False


def test_extract_naming_info_from_filename():
    """ファイル名からの情報抽出テスト"""
    # 売買物件
    sell_info = extract_naming_info_from_filename("【売買】グランドタワー_1.5億円.pdf")
    assert sell_info['kind'] == 'sell'
    assert sell_info['property_name'] == 'グランドタワー'
    assert sell_info['amount'] == '1.5億円'
    
    # 賃貸物件
    rent_info = extract_naming_info_from_filename("【賃貸】レジデンス_家賃18万円.pdf")
    assert rent_info['kind'] == 'rent'
    assert rent_info['property_name'] == 'レジデンス'
    assert rent_info['amount'] == '18万円'
    
    # その他
    other_info = extract_naming_info_from_filename("【その他】不明物件_未確定.pdf")
    assert other_info['kind'] == 'other'
    assert other_info['property_name'] == '不明物件'
    
    # 解析不可
    unknown_info = extract_naming_info_from_filename("普通のファイル.pdf")
    assert unknown_info['kind'] is None


def test_format_amount_for_filename():
    """金額フォーマットテスト"""
    # 売買価格
    assert _format_amount_for_filename(123_000_000, "sell") == "1.2億円"
    assert _format_amount_for_filename(85_000_000, "sell") == "8,500万円"
    
    # 賃貸価格
    assert _format_amount_for_filename(210_000, "rent") == "210,000円"
    assert _format_amount_for_filename(1_200_000, "rent") == "1,200,000円"


def test_truncate_filename():
    """ファイル名切り詰めテスト"""
    # 短いファイル名（変更なし）
    short = "短いファイル名.pdf"
    assert _truncate_filename(short, 100) == short
    
    # 長いファイル名（切り詰めあり）
    long_filename = "非常に長い物件名" * 20 + ".pdf"
    truncated = _truncate_filename(long_filename, 100)
    assert len(truncated.encode('utf-8')) <= 100
    assert truncated.endswith(".pdf") or len(truncated) < len(long_filename)
    
    # 空文字列
    assert _truncate_filename("", 100) == ""
    
    # None
    assert _truncate_filename(None, 100) == ""


def test_generate_filename_edge_cases():
    """エッジケースのテスト"""
    # 非常に長い物件名
    long_name = "超長い物件名" * 30
    info = ParsedInfoRaw(kind="sell", name=long_name, amount=100_000_000)
    original_path = Path("/test/original.pdf")
    
    result = generate_filename(info, original_path)
    assert len(result.encode('utf-8')) <= 255  # 一般的なファイル名制限
    assert result.endswith(".pdf")
    assert "【売買】" in result
    
    # 空白のみの物件名
    info_blank = ParsedInfoRaw(kind="sell", name="   ", amount=50_000_000)
    result_blank = generate_filename(info_blank, original_path)
    assert "名称未取得" in result_blank or "未確定" in result_blank