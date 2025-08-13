from pathlib import Path
import tempfile
import pytest

from mysoku_renamer.file_manager import FileManager, preview_file_operations, FileOperationResult


class TestFileManager:
    
    def test_rename_file_success(self):
        """ファイルリネーム成功テスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            
            # テスト用ファイル作成
            original_file = temp_dir / "original.pdf"
            original_file.write_text("test content")
            
            manager = FileManager()
            result = manager.rename_file(original_file, "renamed.pdf")
            
            assert result.success is True
            assert result.operation_type == "rename"
            assert result.final_path == str(temp_dir / "renamed.pdf")
            assert not original_file.exists()  # 元ファイルは存在しない
            assert Path(result.final_path).exists()  # 新ファイルが存在
    
    def test_rename_file_collision_avoidance(self):
        """リネーム時の衝突回避テスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            
            # テスト用ファイル作成
            original_file = temp_dir / "original.pdf"
            original_file.write_text("original content")
            
            # 衝突するファイル作成
            existing_file = temp_dir / "target.pdf"
            existing_file.write_text("existing content")
            
            manager = FileManager()
            result = manager.rename_file(original_file, "target.pdf")
            
            assert result.success is True
            assert result.final_path == str(temp_dir / "target-1.pdf")
            assert Path(result.final_path).exists()
            assert existing_file.exists()  # 既存ファイルはそのまま
    
    def test_rename_file_not_exist(self):
        """存在しないファイルのリネームテスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            non_existent = temp_dir / "not_exist.pdf"
            
            manager = FileManager()
            result = manager.rename_file(non_existent, "target.pdf")
            
            assert result.success is False
            assert result.final_path is None
            assert "does not exist" in result.error_message
    
    def test_copy_file_success(self):
        """ファイルコピー成功テスト"""
        with tempfile.TemporaryDirectory() as td:
            source_dir = Path(td) / "source"
            target_dir = Path(td) / "target"
            source_dir.mkdir()
            
            # テスト用ファイル作成
            original_file = source_dir / "original.pdf"
            original_file.write_text("test content")
            
            manager = FileManager()
            result = manager.copy_file(original_file, "copied.pdf", target_dir)
            
            assert result.success is True
            assert result.operation_type == "copy"
            assert result.final_path == str(target_dir / "copied.pdf")
            assert original_file.exists()  # 元ファイルは残る
            assert Path(result.final_path).exists()  # コピーファイルが存在
            
            # 内容が同じことを確認
            assert original_file.read_text() == Path(result.final_path).read_text()
    
    def test_copy_file_with_collision(self):
        """コピー時の衝突回避テスト"""
        with tempfile.TemporaryDirectory() as td:
            source_dir = Path(td) / "source"
            target_dir = Path(td) / "target"
            source_dir.mkdir()
            target_dir.mkdir()
            
            # テスト用ファイル作成
            original_file = source_dir / "original.pdf"
            original_file.write_text("original content")
            
            # 衝突するファイル作成
            existing_file = target_dir / "target.pdf"
            existing_file.write_text("existing content")
            
            manager = FileManager()
            result = manager.copy_file(original_file, "target.pdf", target_dir)
            
            assert result.success is True
            assert result.final_path == str(target_dir / "target-1.pdf")
            assert original_file.exists()
            assert existing_file.exists()
            assert Path(result.final_path).exists()
    
    def test_strict_mode_behavior(self):
        """Strictモードの動作テスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            non_existent = temp_dir / "not_exist.pdf"
            
            # Strictモードでエラー時に例外が発生することを確認
            manager = FileManager(strict_mode=True)
            
            with pytest.raises(Exception):
                manager.rename_file(non_existent, "target.pdf")
    
    def test_batch_process_rename(self):
        """バッチ処理（リネーム）テスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            
            # テスト用ファイル作成
            files = []
            for i in range(3):
                file_path = temp_dir / f"file_{i}.pdf"
                file_path.write_text(f"content {i}")
                files.append(file_path)
            
            # バッチ操作定義
            operations = [
                {'path': files[0], 'new_name': 'renamed_0.pdf'},
                {'path': files[1], 'new_name': 'renamed_1.pdf'},
                {'path': files[2], 'new_name': 'renamed_2.pdf'}
            ]
            
            manager = FileManager()
            stats = manager.batch_process(operations)
            
            assert stats['total'] == 3
            assert stats['success'] == 3
            assert stats['error'] == 0
            
            # ファイルが正しくリネームされていることを確認
            for i in range(3):
                assert (temp_dir / f"renamed_{i}.pdf").exists()
                assert not files[i].exists()
    
    def test_batch_process_copy(self):
        """バッチ処理（コピー）テスト"""
        with tempfile.TemporaryDirectory() as td:
            source_dir = Path(td) / "source"
            target_dir = Path(td) / "target"
            source_dir.mkdir()
            
            # テスト用ファイル作成
            files = []
            for i in range(2):
                file_path = source_dir / f"file_{i}.pdf"
                file_path.write_text(f"content {i}")
                files.append(file_path)
            
            # バッチ操作定義
            operations = [
                {'path': files[0], 'new_name': 'copied_0.pdf'},
                {'path': files[1], 'new_name': 'copied_1.pdf'}
            ]
            
            manager = FileManager()
            stats = manager.batch_process(operations, output_dir=target_dir)
            
            assert stats['total'] == 2
            assert stats['success'] == 2
            assert stats['error'] == 0
            
            # 元ファイルとコピーファイルの両方が存在することを確認
            for i in range(2):
                assert files[i].exists()  # 元ファイル
                assert (target_dir / f"copied_{i}.pdf").exists()  # コピーファイル
    
    def test_get_operation_summary(self):
        """操作サマリー取得テスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            
            # テスト用ファイル作成
            original_file = temp_dir / "original.pdf"
            original_file.write_text("test content")
            
            manager = FileManager()
            manager.rename_file(original_file, "renamed.pdf")
            
            summary = manager.get_operation_summary()
            assert summary['total_operations'] == 1
            assert summary['successful'] == 1
            assert summary['failed'] == 0
            assert summary['rename_operations'] == 1
            assert summary['copy_operations'] == 0
    
    def test_get_failed_operations(self):
        """失敗操作の取得テスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            non_existent = temp_dir / "not_exist.pdf"
            
            manager = FileManager()  # Non-strict mode
            manager.rename_file(non_existent, "target.pdf")
            
            failed = manager.get_failed_operations()
            assert len(failed) == 1
            assert failed[0].success is False
    
    def test_clear_log(self):
        """ログクリアテスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            original_file = temp_dir / "original.pdf"
            original_file.write_text("test content")
            
            manager = FileManager()
            manager.rename_file(original_file, "renamed.pdf")
            
            assert len(manager.operation_log) == 1
            
            manager.clear_log()
            assert len(manager.operation_log) == 0


class TestPreviewFunctions:
    
    def test_preview_file_operations_rename(self):
        """ファイル操作プレビュー（リネーム）テスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            
            # テスト用ファイル作成
            files = []
            names = []
            for i in range(3):
                file_path = temp_dir / f"file_{i}.pdf"
                file_path.write_text(f"content {i}")
                files.append(file_path)
                names.append(f"renamed_{i}.pdf")
            
            preview = preview_file_operations(files, names)
            
            assert preview['total_files'] == 3
            assert preview['operation_type'] == 'rename'
            assert preview['collisions_expected'] == 0
            assert preview['missing_files'] == 0
            assert len(preview['operations']) == 3
    
    def test_preview_file_operations_copy(self):
        """ファイル操作プレビュー（コピー）テスト"""
        with tempfile.TemporaryDirectory() as td:
            source_dir = Path(td) / "source"
            target_dir = Path(td) / "target"
            source_dir.mkdir()
            target_dir.mkdir()
            
            # テスト用ファイル作成
            files = []
            names = []
            for i in range(2):
                file_path = source_dir / f"file_{i}.pdf"
                file_path.write_text(f"content {i}")
                files.append(file_path)
                names.append(f"copied_{i}.pdf")
            
            preview = preview_file_operations(files, names, target_dir)
            
            assert preview['operation_type'] == 'copy'
            assert preview['target_directory'] == str(target_dir)
    
    def test_preview_with_collisions(self):
        """衝突ありのプレビューテスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            
            # テスト用ファイル作成
            original_file = temp_dir / "original.pdf"
            original_file.write_text("original content")
            
            # 衝突するファイル作成
            existing_file = temp_dir / "target.pdf"
            existing_file.write_text("existing content")
            
            preview = preview_file_operations([original_file], ["target.pdf"])
            
            assert preview['collisions_expected'] == 1
            assert len(preview['operations']) == 1
            assert preview['operations'][0]['will_collide'] is True
            assert preview['operations'][0]['final_name'] == "target-1.pdf"
    
    def test_preview_missing_files(self):
        """存在しないファイルのプレビューテスト"""
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            non_existent = temp_dir / "not_exist.pdf"
            
            preview = preview_file_operations([non_existent], ["target.pdf"])
            
            assert preview['missing_files'] == 1
            assert len(preview['operations']) == 0  # 存在しないファイルは操作対象外
    
    def test_preview_mismatched_lists(self):
        """リストサイズ不一致のテスト"""
        files = [Path("file1.pdf"), Path("file2.pdf")]
        names = ["name1.pdf"]  # サイズが異なる
        
        with pytest.raises(ValueError, match="same length"):
            preview_file_operations(files, names)