from pathlib import Path
from datetime import datetime
import tempfile
import pytest

from mysoku_renamer.tsv_logger import (
    TSVLogger, generate_timestamped_filename, create_rollback_entry
)


class TestTSVLogger:
    
    def test_write_rollback_tsv(self):
        """ロールバックTSV書き込みテスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            output_path = temp_dir / "rollback_test.tsv"
            
            operations = [
                {
                    'old_path': '/test/original1.pdf',
                    'new_path': '/test/renamed1.pdf',
                    'kind': 'sell',
                    'name': 'テスト物件1',
                    'amount': 100_000_000,
                    'notes': 'test note 1'
                },
                {
                    'old_path': '/test/original2.pdf',
                    'new_path': '/test/renamed2.pdf',
                    'kind': 'rent',
                    'name': 'テスト物件2',
                    'amount': 200_000,
                    'notes': 'test note 2'
                }
            ]
            
            logger = TSVLogger()
            success = logger.write_rollback_tsv(operations, output_path)
            
            assert success is True
            assert output_path.exists()
            
            # ファイル内容を確認
            content = output_path.read_text(encoding='utf-8')
            lines = content.strip().split('\n')
            
            # ヘッダー確認
            headers = lines[0].split('\t')
            expected_headers = ['old_path', 'new_path', 'kind', 'name', 'amount', 'timestamp', 'notes']
            assert headers == expected_headers
            
            # データ行数確認
            assert len(lines) == 3  # ヘッダー + データ2行
            
            # 1行目のデータ確認
            row1 = lines[1].split('\t')
            assert row1[0] == '/test/original1.pdf'
            assert row1[1] == '/test/renamed1.pdf'
            assert row1[2] == 'sell'
            assert row1[3] == 'テスト物件1'
            assert row1[4] == '100000000'
    
    def test_write_error_tsv(self):
        """エラーTSV書き込みテスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            output_path = temp_dir / "errors_test.tsv"
            
            errors = [
                {
                    'original_path': '/test/error1.pdf',
                    'error_type': 'PDF_READ_ERROR',
                    'error_message': 'Cannot read PDF file',
                    'timestamp': '2024-01-01T12:00:00'
                }
            ]
            
            logger = TSVLogger()
            success = logger.write_error_tsv(errors, output_path)
            
            assert success is True
            assert output_path.exists()
            
            content = output_path.read_text(encoding='utf-8')
            lines = content.strip().split('\n')
            
            # ヘッダー確認
            headers = lines[0].split('\t')
            expected_headers = ['original_path', 'error_type', 'error_message', 'timestamp']
            assert headers == expected_headers
            
            # データ確認
            row1 = lines[1].split('\t')
            assert row1[0] == '/test/error1.pdf'
            assert row1[1] == 'PDF_READ_ERROR'
            assert row1[2] == 'Cannot read PDF file'
    
    def test_write_error_tsv_append_mode(self):
        """エラーTSV追記モードテスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            output_path = temp_dir / "errors_append_test.tsv"
            
            # 初回書き込み
            errors1 = [{'original_path': '/test/error1.pdf', 'error_type': 'TYPE1', 'error_message': 'msg1'}]
            logger = TSVLogger()
            logger.write_error_tsv(errors1, output_path, append=False)
            
            # 追記書き込み
            errors2 = [{'original_path': '/test/error2.pdf', 'error_type': 'TYPE2', 'error_message': 'msg2'}]
            logger.write_error_tsv(errors2, output_path, append=True)
            
            content = output_path.read_text(encoding='utf-8')
            lines = content.strip().split('\n')
            
            # ヘッダー1行 + データ2行
            assert len(lines) == 3
            assert 'error1.pdf' in lines[1]
            assert 'error2.pdf' in lines[2]
    
    def test_write_preview_tsv(self):
        """プレビューTSV書き込みテスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            output_path = temp_dir / "preview_test.tsv"
            
            results = [
                {
                    'path': '/test/file1.pdf',
                    'status': 'OK',
                    'kind': 'sell',
                    'name': 'テスト物件',
                    'amount': 150_000_000,
                    'text_length': 1500,
                    'new_name': '【売買】テスト物件_1.5億円.pdf',
                    'notes': 'test note'
                }
            ]
            
            logger = TSVLogger()
            success = logger.write_preview_tsv(results, output_path)
            
            assert success is True
            assert output_path.exists()
            
            content = output_path.read_text(encoding='utf-8')
            lines = content.strip().split('\n')
            
            # ヘッダー確認
            headers = lines[0].split('\t')
            expected_headers = ['path', 'status', 'kind', 'name', 'amount', 'text_length', 'new_name', 'notes']
            assert headers == expected_headers
            
            # データ確認
            row1 = lines[1].split('\t')
            assert row1[2] == 'sell'
            assert row1[3] == 'テスト物件'
            assert row1[6] == '【売買】テスト物件_1.5億円.pdf'
    
    def test_write_apply_tsv(self):
        """適用結果TSV書き込みテスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            output_path = temp_dir / "apply_test.tsv"
            
            results = [
                {
                    'path': '/test/file1.pdf',
                    'status': 'OK',
                    'kind': 'rent',
                    'name': 'テスト賃貸',
                    'amount': 180_000,
                    'text_length': 800,
                    'new_name': '【賃貸】テスト賃貸_家賃180,000円.pdf',
                    'actual_new_path': '/test/【賃貸】テスト賃貸_家賃180,000円.pdf',
                    'timestamp': '2024-01-01T12:00:00',
                    'notes': 'Applied successfully'
                }
            ]
            
            logger = TSVLogger()
            success = logger.write_apply_tsv(results, output_path)
            
            assert success is True
            
            content = output_path.read_text(encoding='utf-8')
            lines = content.strip().split('\n')
            
            # ヘッダー確認
            headers = lines[0].split('\t')
            expected_headers = ['path', 'status', 'kind', 'name', 'amount', 'text_length', 
                              'new_name', 'actual_new_path', 'timestamp', 'notes']
            assert headers == expected_headers
            
            # actual_new_path列の確認
            row1 = lines[1].split('\t')
            assert row1[7] == '/test/【賃貸】テスト賃貸_家賃180,000円.pdf'
    
    def test_read_rollback_tsv(self):
        """ロールバックTSV読み込みテスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            tsv_path = temp_dir / "rollback_read_test.tsv"
            
            # テストデータを書き込み
            test_data = [
                {
                    'old_path': '/test/old1.pdf',
                    'new_path': '/test/new1.pdf',
                    'kind': 'sell',
                    'name': '物件1',
                    'amount': 80_000_000
                }
            ]
            
            logger = TSVLogger()
            logger.write_rollback_tsv(test_data, tsv_path)
            
            # 読み込みテスト
            read_data = logger.read_rollback_tsv(tsv_path)
            
            assert len(read_data) == 1
            assert read_data[0]['old_path'] == '/test/old1.pdf'
            assert read_data[0]['new_path'] == '/test/new1.pdf'
            assert read_data[0]['kind'] == 'sell'
            assert read_data[0]['name'] == '物件1'
    
    def test_read_rollback_tsv_not_exist(self):
        """存在しないTSV読み込みテスト"""
        non_existent = Path("/tmp/does_not_exist.tsv")
        
        logger = TSVLogger()
        result = logger.read_rollback_tsv(non_existent)
        
        assert result == []
    
    def test_validate_tsv_format(self):
        """TSVフォーマット検証テスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            valid_tsv = temp_dir / "valid.tsv"
            
            # 正常なTSVを作成
            rollback_data = [{'old_path': '/test/old.pdf', 'new_path': '/test/new.pdf', 'kind': 'sell', 'name': 'test', 'amount': 100}]
            logger = TSVLogger()
            logger.write_rollback_tsv(rollback_data, valid_tsv)
            
            # 検証テスト
            expected_headers = ['old_path', 'new_path', 'kind', 'name', 'amount', 'timestamp', 'notes']
            validation = logger.validate_tsv_format(valid_tsv, expected_headers)
            
            assert validation['valid'] is True
            assert validation['exists'] is True
            assert validation['readable'] is True
            assert validation['headers_match'] is True
            assert validation['row_count'] == 1
    
    def test_validate_tsv_format_invalid_headers(self):
        """不正ヘッダーのTSV検証テスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            invalid_tsv = temp_dir / "invalid.tsv"
            
            # 不正なヘッダーのTSVを作成
            invalid_tsv.write_text("wrong\theader\tformat\n", encoding='utf-8')
            
            logger = TSVLogger()
            expected_headers = ['old_path', 'new_path', 'kind']
            validation = logger.validate_tsv_format(invalid_tsv, expected_headers)
            
            assert validation['valid'] is False
            assert validation['headers_match'] is False
            assert validation['actual_headers'] == ['wrong', 'header', 'format']
    
    def test_validate_tsv_format_not_exist(self):
        """存在しないTSV検証テスト"""
        non_existent = Path("/tmp/does_not_exist.tsv")
        
        logger = TSVLogger()
        validation = logger.validate_tsv_format(non_existent, ['header'])
        
        assert validation['valid'] is False
        assert validation['exists'] is False
        assert 'does not exist' in validation['error_message']


class TestUtilityFunctions:
    
    def test_generate_timestamped_filename(self):
        """タイムスタンプ付きファイル名生成テスト"""
        timestamp = datetime(2024, 1, 15, 14, 30, 45)
        filename = generate_timestamped_filename("rollback", ".tsv", timestamp)
        
        assert filename == "rollback_20240115_143045.tsv"
    
    def test_generate_timestamped_filename_current_time(self):
        """現在時刻でのタイムスタンプファイル名生成テスト"""
        filename = generate_timestamped_filename("test", ".log")
        
        # 基本的な形式チェック
        assert filename.startswith("test_")
        assert filename.endswith(".log")
        assert len(filename) == len("test_YYYYMMDD_HHMMSS.log")
    
    def test_create_rollback_entry(self):
        """ロールバックエントリ作成テスト"""
        entry = create_rollback_entry(
            original_path="/test/original.pdf",
            new_path="/test/renamed.pdf",
            kind="sell",
            name="テスト物件",
            amount=120_000_000,
            notes="test operation"
        )
        
        assert entry['old_path'] == "/test/original.pdf"
        assert entry['new_path'] == "/test/renamed.pdf"
        assert entry['kind'] == "sell"
        assert entry['name'] == "テスト物件"
        assert entry['amount'] == 120_000_000
        assert entry['notes'] == "test operation"
        assert 'timestamp' in entry
        
        # タイムスタンプがISO形式であることを確認
        timestamp_str = entry['timestamp']
        try:
            datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except ValueError:
            pytest.fail("Timestamp is not in valid ISO format")
    
    def test_create_rollback_entry_minimal(self):
        """最小限のロールバックエントリ作成テスト"""
        entry = create_rollback_entry(
            original_path="/test/original.pdf",
            new_path="/test/renamed.pdf"
        )
        
        assert entry['old_path'] == "/test/original.pdf"
        assert entry['new_path'] == "/test/renamed.pdf"
        assert entry['kind'] == ""
        assert entry['name'] == ""
        assert entry['amount'] is None
        assert entry['notes'] == ""
        assert 'timestamp' in entry


class TestTSVLoggerErrorHandling:
    
    def test_write_to_readonly_directory(self):
        """読み取り専用ディレクトリへの書き込みテスト"""
        # このテストは環境によってスキップされる場合があります
        try:
            with tempfile.TemporaryDirectory() as td:
                temp_dir = Path(td)
                readonly_dir = temp_dir / "readonly"
                readonly_dir.mkdir()
                readonly_dir.chmod(0o444)  # 読み取り専用
                
                output_path = readonly_dir / "test.tsv"
                
                logger = TSVLogger()
                success = logger.write_rollback_tsv([], output_path)
                
                # 書き込み失敗することを期待
                assert success is False
                
        except (PermissionError, OSError):
            # 権限設定ができない環境ではテストをスキップ
            pytest.skip("Cannot test readonly directory on this system")
    
    def test_invalid_encoding(self):
        """不正なエンコーディングのテスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            output_path = temp_dir / "encoding_test.tsv"
            
            # 無効なエンコーディングでTSVLoggerを作成
            logger = TSVLogger(encoding="invalid-encoding")
            
            # 書き込みが失敗することを期待
            success = logger.write_rollback_tsv([{'old_path': 'test', 'new_path': 'test'}], output_path)
            assert success is False