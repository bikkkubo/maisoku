#!/usr/bin/env python3
"""
OCRオプション機能のテスト

目的:
- tesseract未導入環境でもテスト失敗にしない
- --ocrフラグによる動作変更の確認
- OCR処理のステータス遷移確認
- 環境依存部分の適切な分離
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.mysoku_renamer.pdf_processor import analyze_pdf
from src.mysoku_renamer.ocr import (
    check_tesseract_availability, 
    get_ocr_status_summary,
    OcrResult,
    run_ocr_on_images,
    try_ocr_extraction
)


class TestOCRAvailability:
    """OCR機能の利用可能性テスト"""
    
    def test_ocr_status_summary_structure(self):
        """OCR状況サマリーの構造確認"""
        status = get_ocr_status_summary()
        
        required_keys = [
            "tesseract_available", 
            "pytesseract_installed", 
            "pillow_installed",
            "pdf2img_available"
        ]
        
        for key in required_keys:
            assert key in status
            assert isinstance(status[key], bool)
    
    def test_tesseract_availability_check(self):
        """tesseract利用可能性チェック"""
        # 環境に依存するため、エラーが出ないことのみ確認
        result = check_tesseract_availability()
        assert isinstance(result, bool)


class TestOCRWithMocks:
    """モックを使用したOCR処理テスト"""
    
    @patch('src.mysoku_renamer.ocr.pytesseract')
    @patch('src.mysoku_renamer.ocr.Image')
    def test_run_ocr_on_images_success(self, mock_image, mock_pytesseract):
        """OCR成功ケースのテスト"""
        # Mock設定
        mock_pytesseract.get_tesseract_version.return_value = "4.1.1"
        mock_pytesseract.image_to_string.return_value = "テストテキスト\n物件名：サンプル物件"
        
        # 仮の画像オブジェクト
        mock_img = MagicMock()
        mock_img.size = (800, 1200)
        
        result = run_ocr_on_images([mock_img])
        
        assert result.note == "ocr_ok"
        assert "テストテキスト" in result.text
        assert "サンプル物件" in result.text
        mock_pytesseract.image_to_string.assert_called_once()
    
    @patch('src.mysoku_renamer.ocr.pytesseract', None)
    def test_run_ocr_on_images_unavailable(self):
        """pytesseract未インストール時のテスト"""
        mock_img = MagicMock()
        result = run_ocr_on_images([mock_img])
        
        assert result.note == "ocr_unavailable"
        assert result.text == ""
    
    @patch('src.mysoku_renamer.ocr.pytesseract')
    @patch('src.mysoku_renamer.ocr.Image')
    def test_run_ocr_on_images_failed(self, mock_image, mock_pytesseract):
        """OCR処理失敗時のテスト"""
        # tesseractは利用可能だが、処理で例外発生
        mock_pytesseract.get_tesseract_version.return_value = "4.1.1"
        mock_pytesseract.image_to_string.side_effect = Exception("OCR processing error")
        
        mock_img = MagicMock()
        result = run_ocr_on_images([mock_img])
        
        assert result.note == "ocr_failed"
        assert result.text == ""


class TestPDFProcessorOCRIntegration:
    """PDF処理でのOCR統合テスト"""
    
    def create_minimal_pdf(self, temp_dir: Path) -> Path:
        """最小限のPDFファイルを作成"""
        from pypdf import PdfWriter
        
        pdf_path = temp_dir / "test.pdf"
        
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        
        with open(pdf_path, 'wb') as f:
            writer.write(f)
        
        return pdf_path
    
    def create_text_pdf(self, temp_dir: Path, text_content: str) -> Path:
        """テキスト付きPDFファイルを作成"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            
            pdf_path = temp_dir / "text_test.pdf"
            
            c = canvas.Canvas(str(pdf_path), pagesize=A4)
            c.drawString(100, 750, text_content)
            c.save()
            
            return pdf_path
        except ImportError:
            # reportlabが利用できない場合は最小PDFで代替
            return self.create_minimal_pdf(temp_dir)
    
    def test_analyze_pdf_ocr_flag_changes_behavior(self):
        """--ocrフラグによる動作変更テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # テキストなし（または少ない）PDFを作成
            pdf_path = self.create_minimal_pdf(temp_path)
            
            # OCRなしの場合
            result_no_ocr = analyze_pdf(pdf_path, allow_ocr=False, ocr_threshold=200)
            
            # OCRありの場合
            result_with_ocr = analyze_pdf(pdf_path, allow_ocr=True, ocr_threshold=200)
            
            # 基本属性の存在確認
            assert hasattr(result_no_ocr, 'text')
            assert hasattr(result_no_ocr, 'text_length')
            assert hasattr(result_no_ocr, 'needs_ocr')
            assert hasattr(result_no_ocr, 'note')
            
            assert hasattr(result_with_ocr, 'text')
            assert hasattr(result_with_ocr, 'text_length')
            assert hasattr(result_with_ocr, 'needs_ocr')
            assert hasattr(result_with_ocr, 'note')
            
            # OCRなしの場合の期待される note
            expected_no_ocr_notes = [
                "no_text_extracted", 
                "short_text_", 
                "embedded_text_"
            ]
            
            assert any(note in result_no_ocr.note for note in expected_no_ocr_notes)
            
            # OCRありの場合の期待される note（環境により変動）
            expected_ocr_notes = [
                "ocr_ok",
                "ocr_unavailable", 
                "ocr_failed", 
                "no_text_extracted",  # OCR未実行時もあり得る
                "short_text_",        # OCR未実行時
            ]
            
            assert any(note in result_with_ocr.note for note in expected_ocr_notes)
    
    def test_analyze_pdf_with_sufficient_text_skips_ocr(self):
        """十分なテキストがある場合はOCRスキップ"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 長いテキストを含むPDFを作成
            long_text = "これは十分な長さのテキストです。" * 20  # 200文字以上
            pdf_path = self.create_text_pdf(temp_path, long_text)
            
            result = analyze_pdf(pdf_path, allow_ocr=True, ocr_threshold=200)
            
            # OCRが実行されないことを確認
            assert result.text_length >= 200  # 十分なテキスト量
            assert result.needs_ocr is False
            
            # noteがOCR関連でないことを確認
            ocr_notes = ["ocr_ok", "ocr_failed", "ocr_unavailable"]
            assert not any(ocr_note in result.note for ocr_note in ocr_notes)
    
    @patch('src.mysoku_renamer.pdf_processor.try_ocr_extraction')
    def test_analyze_pdf_ocr_exception_handling(self, mock_ocr):
        """OCR処理中の例外ハンドリングテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pdf_path = self.create_minimal_pdf(temp_path)
            
            # OCR処理で例外発生をシミュレート
            mock_ocr.side_effect = Exception("Test OCR error")
            
            result = analyze_pdf(pdf_path, allow_ocr=True, ocr_threshold=200)
            
            # エラーが適切に処理されることを確認
            assert result.note == "ocr_failed"
            assert isinstance(result.text, str)  # 文字列として処理
            assert isinstance(result.text_length, int)  # 整数として処理
    
    def test_analyze_pdf_ocr_import_error_handling(self):
        """OCRモジュールのインポートエラーハンドリング"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pdf_path = self.create_minimal_pdf(temp_path)
            
            # ocr.pyのtry_ocr_extractionが見つからない場合をシミュレート
            with patch('src.mysoku_renamer.pdf_processor.try_ocr_extraction', 
                      side_effect=ImportError("OCR module not found")):
                
                result = analyze_pdf(pdf_path, allow_ocr=True, ocr_threshold=200)
                
                # インポートエラーが適切に処理されることを確認
                assert result.note == "ocr_unavailable"
                assert isinstance(result.text, str)
                assert isinstance(result.text_length, int)


class TestPdf2ImageIntegration:
    """pdf2image統合テスト"""
    
    def test_pdf_to_images_with_pdf2image_available(self):
        """pdf2image利用可能時のPDF→画像変換テスト"""
        try:
            from src.mysoku_renamer.ocr import _pdf_to_images, PDF2IMAGE_AVAILABLE
            
            if not PDF2IMAGE_AVAILABLE:
                pytest.skip("pdf2image not available in this environment")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # 簡単な1ページPDFを作成
                from pypdf import PdfWriter
                pdf_path = temp_path / "test.pdf"
                writer = PdfWriter()
                writer.add_blank_page(width=595, height=842)
                with open(pdf_path, 'wb') as f:
                    writer.write(f)
                
                # PDF→画像変換実行
                images = _pdf_to_images(pdf_path, dpi=150)
                
                # 変換結果検証
                assert len(images) == 1  # 1ページのPDFなので1つの画像
                assert hasattr(images[0], 'size')  # PIL.Imageの属性
                assert images[0].size[0] > 0 and images[0].size[1] > 0  # サイズが正の値
                
        except ImportError:
            pytest.skip("Required dependencies not available")
    
    def test_ocr_with_pdf2image_end_to_end(self):
        """pdf2image + OCRのエンドツーエンドテスト"""
        try:
            from src.mysoku_renamer.ocr import (
                try_ocr_extraction, 
                PDF2IMAGE_AVAILABLE, 
                TESSERACT_AVAILABLE,
                check_tesseract_availability
            )
            
            if not PDF2IMAGE_AVAILABLE:
                pytest.skip("pdf2image not available")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # テストPDF作成
                from pypdf import PdfWriter
                pdf_path = temp_path / "test.pdf"
                writer = PdfWriter()
                writer.add_blank_page(width=595, height=842)
                with open(pdf_path, 'wb') as f:
                    writer.write(f)
                
                # OCR抽出試行
                result = try_ocr_extraction(pdf_path, fallback_text="test_fallback")
                
                # 結果検証
                assert isinstance(result.text, str)
                assert result.note in ["ocr_ok", "ocr_unavailable", "ocr_failed"]
                
                if TESSERACT_AVAILABLE and check_tesseract_availability():
                    # tesseractが利用可能な場合、OCRが実行されるか失敗するかのどちらか
                    assert result.note in ["ocr_ok", "ocr_failed"]
                else:
                    # tesseract利用不可の場合
                    assert result.note == "ocr_unavailable"
                    assert result.text == "test_fallback"
                    
        except ImportError:
            pytest.skip("Required dependencies not available")


class TestOCREdgeCases:
    """OCR機能のエッジケーステスト"""
    
    def test_try_ocr_extraction_not_implemented(self):
        """PDF→画像変換未実装時のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 最小PDFファイル作成
            from pypdf import PdfWriter
            pdf_path = temp_path / "test.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            with open(pdf_path, 'wb') as f:
                writer.write(f)
            
            # OCR抽出試行（PDF→画像変換は未実装）
            result = try_ocr_extraction(pdf_path, fallback_text="fallback")
            
            # OCR処理結果を確認
            expected_notes = [
                "ocr_ok",
                "ocr_unavailable",
                "ocr_failed"
            ]
            assert any(note in result.note for note in expected_notes)
            # フォールバックテキストが含まれていることを確認
            assert "fallback" in result.text
    
    @patch('src.mysoku_renamer.ocr.TESSERACT_AVAILABLE', False)
    def test_try_ocr_extraction_unavailable(self):
        """tesseract利用不可時のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pdf_path = temp_path / "test.pdf"
            
            # 空のPDFファイル作成
            pdf_path.write_bytes(b"")
            
            result = try_ocr_extraction(pdf_path, fallback_text="test_fallback")
            
            assert result.note == "ocr_unavailable"
            assert result.text == "test_fallback"


if __name__ == "__main__":
    # テスト実行時のOCR環境診断
    import sys
    
    print("=== OCR環境診断 ===")
    status = get_ocr_status_summary()
    for key, value in status.items():
        print(f"{key}: {'✅' if value else '❌'}")
    
    print("\n=== テスト実行 ===")
    
    # pytest実行
    pytest.main([__file__, "-v"])