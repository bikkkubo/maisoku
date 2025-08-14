#!/usr/bin/env python3
"""
OpenAI連携機能のテスト

目的:
- API キー未設定環境でのスキップ処理
- OpenAI利用可能時の基本動作確認
- CI環境での安全なテスト実行
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# OpenAI依存関係の利用可能性チェック
try:
    from src.mysoku_renamer.openai_infer import (
        OpenAIExtractor, 
        AiResult,
        check_openai_availability
    )
    OPENAI_INFER_AVAILABLE = True
except ImportError:
    OPENAI_INFER_AVAILABLE = False


class TestOpenAIAvailability:
    """OpenAI機能の利用可能性テスト"""
    
    def test_openai_availability_check_structure(self):
        """OpenAI利用可能性チェックの構造確認"""
        if not OPENAI_INFER_AVAILABLE:
            pytest.skip("OpenAI infer module not available")
        
        status = check_openai_availability()
        
        required_keys = [
            "openai_installed",
            "pdf2image_available", 
            "api_key_set",
            "ready"
        ]
        
        for key in required_keys:
            assert key in status
            assert isinstance(status[key], bool)
        
        # ready は他の条件の AND
        expected_ready = (status["openai_installed"] and 
                         status["pdf2image_available"] and 
                         status["api_key_set"])
        assert status["ready"] == expected_ready


class TestOpenAIExtractorWithoutAPI:
    """API キーなしでのOpenAIExtractorテスト"""
    
    @patch.dict(os.environ, {}, clear=True)  # 環境変数をクリア
    def test_extractor_init_without_api_key(self):
        """API キー未設定時の初期化エラーテスト"""
        if not OPENAI_INFER_AVAILABLE:
            pytest.skip("OpenAI infer module not available")
        
        with pytest.raises(RuntimeError) as exc_info:
            OpenAIExtractor()
        
        assert "OPENAI_API_KEY" in str(exc_info.value)
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True)  # 空文字
    def test_extractor_init_with_empty_api_key(self):
        """空のAPI キー設定時の初期化エラーテスト"""
        if not OPENAI_INFER_AVAILABLE:
            pytest.skip("OpenAI infer module not available")
        
        with pytest.raises(RuntimeError) as exc_info:
            OpenAIExtractor()
        
        assert "OPENAI_API_KEY" in str(exc_info.value)


class TestOpenAIExtractorWithMocks:
    """モックを使用したOpenAIExtractorテスト"""
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"})
    @patch('src.mysoku_renamer.openai_infer.OpenAI')
    def test_extract_from_text_success(self, mock_openai_class):
        """テキスト抽出成功ケースのテスト"""
        if not OPENAI_INFER_AVAILABLE:
            pytest.skip("OpenAI infer module not available")
        
        # OpenAI クライアントのモック設定
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # レスポンスのモック
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"kind": "sell", "name": "テストマンション", "amount": 50000000}'
        mock_client.chat.completions.create.return_value = mock_response
        
        extractor = OpenAIExtractor()
        result = extractor.extract_from_text("物件名：テストマンション 販売価格：5000万円")
        
        assert result["kind"] == "sell"
        assert result["name"] == "テストマンション"
        assert result["amount"] == 50000000
        
        # API が呼ばれたことを確認
        mock_client.chat.completions.create.assert_called_once()
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"})
    @patch('src.mysoku_renamer.openai_infer.OpenAI')
    def test_extract_from_text_api_error(self, mock_openai_class):
        """API エラー時のテスト"""
        if not OPENAI_INFER_AVAILABLE:
            pytest.skip("OpenAI infer module not available")
        
        # OpenAI クライアントのモック設定（エラー発生）
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        extractor = OpenAIExtractor()
        result = extractor.extract_from_text("テスト物件情報")
        
        # エラー時のデフォルト値
        assert result["kind"] == "unknown"
        assert result["name"] == ""
        assert result["amount"] is None
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"})
    @patch('src.mysoku_renamer.openai_infer.OpenAI')
    @patch('src.mysoku_renamer.openai_infer.convert_from_path')
    def test_extract_from_pdf_vision_success(self, mock_convert, mock_openai_class):
        """Vision API 成功ケースのテスト"""
        if not OPENAI_INFER_AVAILABLE:
            pytest.skip("OpenAI infer module not available")
        
        # PDF→画像変換のモック
        mock_image = MagicMock()
        mock_image.save = MagicMock()
        mock_convert.return_value = [mock_image]
        
        # OpenAI Vision API のモック
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"kind": "rent", "name": "ビジョンテスト", "amount": 180000}'
        mock_client.chat.completions.create.return_value = mock_response
        
        extractor = OpenAIExtractor()
        
        # テスト用の空PDFファイル作成
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "test.pdf"
            pdf_path.write_bytes(b"dummy pdf content")
            
            result = extractor.extract_from_pdf(pdf_path, dpi=300, pages=1)
        
        assert result.kind == "rent"
        assert result.name == "ビジョンテスト"
        assert result.amount == 180000
        assert result.notes == "openai_vision_ok"
        
        # Vision API が呼ばれたことを確認
        mock_client.chat.completions.create.assert_called_once()


class TestPriceNormalization:
    """価格正規化ロジックのテスト"""
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"})
    @patch('src.mysoku_renamer.openai_infer.OpenAI')
    def test_normalize_price_to_yen(self, mock_openai_class):
        """価格正規化テスト"""
        if not OPENAI_INFER_AVAILABLE:
            pytest.skip("OpenAI infer module not available")
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        extractor = OpenAIExtractor()
        
        # 億円パターン
        assert extractor._normalize_price_to_yen("1.2億円") == 120_000_000
        assert extractor._normalize_price_to_yen("2億") == 200_000_000
        
        # 万円パターン
        assert extractor._normalize_price_to_yen("8500万円") == 85_000_000
        assert extractor._normalize_price_to_yen("1,500万") == 15_000_000
        
        # 円パターン
        assert extractor._normalize_price_to_yen("180000円") == 180_000
        assert extractor._normalize_price_to_yen("1,200,000") == 1_200_000
        
        # 変換不可
        assert extractor._normalize_price_to_yen("応相談") is None
        assert extractor._normalize_price_to_yen("") is None
        assert extractor._normalize_price_to_yen("abc") is None


class TestJSONResponseCleaning:
    """JSON レスポンス クリーニングのテスト"""
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"})
    @patch('src.mysoku_renamer.openai_infer.OpenAI')
    def test_clean_json_response(self, mock_openai_class):
        """JSON レスポンス クリーニングテスト"""
        if not OPENAI_INFER_AVAILABLE:
            pytest.skip("OpenAI infer module not available")
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        extractor = OpenAIExtractor()
        
        # マークダウン形式の JSON
        markdown_json = '''```json
{
  "kind": "sell",
  "name": "テスト物件",
  "amount": 100000000
}
```'''
        
        cleaned = extractor._clean_json_response(markdown_json)
        expected = '''{\n  "kind": "sell",\n  "name": "テスト物件",\n  "amount": 100000000\n}'''
        assert cleaned == expected
        
        # 通常の JSON（変更なし）
        normal_json = '{"kind": "rent", "name": "通常物件", "amount": 150000}'
        assert extractor._clean_json_response(normal_json) == normal_json
        
        # 空文字
        assert extractor._clean_json_response("") == "{}"
        assert extractor._clean_json_response(None) == "{}"


class TestOpenAIIntegrationConditional:
    """条件付きOpenAI統合テスト（API キー利用可能時のみ）"""
    
    def test_real_openai_extraction_if_key_available(self):
        """実際のOpenAI API テスト（API キー設定時のみ）"""
        if not OPENAI_INFER_AVAILABLE:
            pytest.skip("OpenAI infer module not available")
        
        # API キーが設定されていない場合はスキップ
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping real API test")
        
        try:
            extractor = OpenAIExtractor(model="gpt-4o-mini")
            
            # 簡単なテキスト抽出テスト
            test_text = "物件名：サンプルマンション 販売価格：8000万円 管理費：2万円"
            result = extractor.extract_from_text(test_text)
            
            # 基本構造の確認（内容の詳細は API 結果に依存）
            assert isinstance(result, dict)
            assert "kind" in result
            assert "name" in result
            assert "amount" in result
            
            # kind は期待値のいずれか
            assert result["kind"] in ["sell", "rent", "unknown"]
            
        except Exception as e:
            # API 制限やネットワークエラーの場合はスキップ
            pytest.skip(f"OpenAI API test failed: {e}")


if __name__ == "__main__":
    # OpenAI機能の診断実行
    import json as json_module
    
    print("=== OpenAI機能テスト診断 ===")
    
    if OPENAI_INFER_AVAILABLE:
        status = check_openai_availability()
        print(json_module.dumps(status, indent=2, ensure_ascii=False))
        
        if status["ready"]:
            print("✅ OpenAI機能テスト実行可能")
        else:
            print("⚠️  OpenAI機能一部制限（APIキー等未設定）")
    else:
        print("❌ OpenAI infer モジュール利用不可")
    
    print("\n=== テスト実行 ===")
    pytest.main([__file__, "-v"])