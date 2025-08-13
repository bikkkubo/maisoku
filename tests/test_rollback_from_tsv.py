#!/usr/bin/env python3
"""
rollback_from_tsv.py の単体テスト

テスト対象:
- TSVファイル解析
- ロールバック動作判定
- ファイル操作実行
- エラーハンドリング
- ドライランモード
"""

import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from rollback_from_tsv import (
    RollbackEntry,
    RollbackResult,
    determine_rollback_action,
    execute_rollback_action,
    parse_tsv_file,
    rollback_from_tsv,
    write_errors_tsv
)


class TestRollbackFromTsv(unittest.TestCase):
    
    def setUp(self):
        """テスト用一時ディレクトリ作成"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
        # テスト用ファイル作成
        self.old_file = self.temp_path / "old_file.pdf"
        self.new_file = self.temp_path / "new_file.pdf"
        self.outdir = self.temp_path / "output"
        self.outdir.mkdir()
        self.outdir_file = self.outdir / "outdir_file.pdf"
        
    def tearDown(self):
        """一時ディレクトリ削除"""
        self.temp_dir.cleanup()
        
    def create_tsv_file(self, entries: list) -> Path:
        """テスト用TSVファイル作成"""
        tsv_path = self.temp_path / "test.tsv"
        
        with open(tsv_path, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['old_path', 'new_path', 'kind', 'name', 'amount', 'timestamp', 'notes']
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()
            
            for entry in entries:
                writer.writerow(entry)
        
        return tsv_path

    def test_parse_tsv_file_normal(self):
        """正常なTSVファイル解析テスト"""
        entries_data = [
            {
                'old_path': '/old/file1.pdf',
                'new_path': '/new/file1.pdf',
                'kind': 'sell',
                'name': 'テスト物件1',
                'amount': '100000000',
                'timestamp': '2024-01-01T12:00:00',
                'notes': 'test_note'
            },
            {
                'old_path': '/old/file2.pdf', 
                'new_path': '/new/file2.pdf',
                'kind': 'rent',
                'name': 'テスト物件2',
                'amount': '180000',
                'timestamp': '2024-01-01T12:01:00',
                'notes': ''
            }
        ]
        
        tsv_path = self.create_tsv_file(entries_data)
        entries = parse_tsv_file(tsv_path)
        
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].old_path, '/old/file1.pdf')
        self.assertEqual(entries[0].new_path, '/new/file1.pdf')
        self.assertEqual(entries[0].kind, 'sell')
        self.assertEqual(entries[0].name, 'テスト物件1')
        self.assertEqual(entries[1].amount, '180000')
        
    def test_parse_tsv_file_alternative_columns(self):
        """代替列名でのTSVファイル解析テスト（path/actual_new_path）"""
        tsv_path = self.temp_path / "alt_test.tsv"
        
        with open(tsv_path, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['path', 'actual_new_path', 'kind', 'name', 'amount', 'timestamp', 'notes']
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()
            
            writer.writerow({
                'path': '/original/file.pdf',
                'actual_new_path': '/renamed/file.pdf',
                'kind': 'sell',
                'name': 'テスト',
                'amount': '50000000',
                'timestamp': '2024-01-01T12:00:00',
                'notes': 'alt_test'
            })
        
        entries = parse_tsv_file(tsv_path)
        
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].old_path, '/original/file.pdf')
        self.assertEqual(entries[0].new_path, '/renamed/file.pdf')

    def test_determine_rollback_action_rename(self):
        """同一ディレクトリ内リネーム判定テスト"""
        # ファイル作成
        self.new_file.write_text("test content")
        
        entry = RollbackEntry(
            old_path=str(self.old_file),
            new_path=str(self.new_file),
            kind="sell", name="test", amount="1000", timestamp="", notes=""
        )
        
        action = determine_rollback_action(entry)
        self.assertEqual(action, "rename")
        
    def test_determine_rollback_action_delete(self):
        """異なるディレクトリ削除判定テスト（outdir運用）"""
        # outdir内にファイル作成
        self.outdir_file.write_text("test content")
        
        entry = RollbackEntry(
            old_path=str(self.old_file),  # 元ディレクトリ
            new_path=str(self.outdir_file),  # outdir
            kind="sell", name="test", amount="1000", timestamp="", notes=""
        )
        
        action = determine_rollback_action(entry)
        self.assertEqual(action, "delete")
        
    def test_determine_rollback_action_skip_not_found(self):
        """ファイル不存在スキップ判定テスト"""
        entry = RollbackEntry(
            old_path=str(self.old_file),
            new_path=str(self.new_file),  # 存在しない
            kind="sell", name="test", amount="1000", timestamp="", notes=""
        )
        
        action = determine_rollback_action(entry)
        self.assertEqual(action, "skip_not_found")
        
    def test_determine_rollback_action_skip_collision(self):
        """衝突スキップ判定テスト"""
        # 新旧両方のファイルを作成（衝突状態）
        self.old_file.write_text("old content")
        self.new_file.write_text("new content")
        
        entry = RollbackEntry(
            old_path=str(self.old_file),
            new_path=str(self.new_file),
            kind="sell", name="test", amount="1000", timestamp="", notes=""
        )
        
        action = determine_rollback_action(entry)
        self.assertEqual(action, "skip_collision")

    def test_execute_rollback_action_rename(self):
        """リネーム実行テスト"""
        # newファイルを作成
        self.new_file.write_text("test content")
        
        entry = RollbackEntry(
            old_path=str(self.old_file),
            new_path=str(self.new_file),
            kind="sell", name="test", amount="1000", timestamp="", notes=""
        )
        
        error = execute_rollback_action(entry, "rename", dry_run=False)
        
        self.assertIsNone(error)
        self.assertTrue(self.old_file.exists())
        self.assertFalse(self.new_file.exists())
        
    def test_execute_rollback_action_delete(self):
        """削除実行テスト"""
        # ファイル作成
        self.outdir_file.write_text("test content")
        
        entry = RollbackEntry(
            old_path=str(self.old_file),
            new_path=str(self.outdir_file),
            kind="sell", name="test", amount="1000", timestamp="", notes=""
        )
        
        error = execute_rollback_action(entry, "delete", dry_run=False)
        
        self.assertIsNone(error)
        self.assertFalse(self.outdir_file.exists())
        
    def test_execute_rollback_action_dry_run(self):
        """ドライラン実行テスト"""
        self.new_file.write_text("test content")
        
        entry = RollbackEntry(
            old_path=str(self.old_file),
            new_path=str(self.new_file),
            kind="sell", name="test", amount="1000", timestamp="", notes=""
        )
        
        # ドライランではファイル操作は行われない
        error = execute_rollback_action(entry, "rename", dry_run=True)
        
        self.assertIsNone(error)
        self.assertTrue(self.new_file.exists())  # 元のまま
        self.assertFalse(self.old_file.exists())  # 変更されない
        
    def test_execute_rollback_action_error(self):
        """実行エラーテスト"""
        # 存在しないファイルに対してリネーム実行
        entry = RollbackEntry(
            old_path=str(self.old_file),
            new_path=str(self.new_file),  # 存在しない
            kind="sell", name="test", amount="1000", timestamp="", notes=""
        )
        
        error = execute_rollback_action(entry, "rename", dry_run=False)
        
        self.assertIsNotNone(error)
        self.assertIn("操作失敗", error)

    def test_write_errors_tsv(self):
        """エラーTSV書き込みテスト"""
        errors = [
            {
                'original_path': '/test/file1.pdf',
                'error_type': 'ROLLBACK_ERROR',
                'error_message': 'テストエラー1',
                'timestamp': '2024-01-01T12:00:00'
            },
            {
                'original_path': '/test/file2.pdf',
                'error_type': 'ROLLBACK_ERROR', 
                'error_message': 'テストエラー2',
                'timestamp': '2024-01-01T12:01:00'
            }
        ]
        
        errors_tsv_path = self.temp_path / "test_errors.tsv"
        write_errors_tsv(errors, errors_tsv_path)
        
        # ファイル内容確認
        self.assertTrue(errors_tsv_path.exists())
        
        with open(errors_tsv_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('original_path\terror_type\terror_message\ttimestamp')
            self.assertIn('/test/file1.pdf')
            self.assertIn('テストエラー1')
            self.assertIn('/test/file2.pdf')
            
    @patch('rollback_from_tsv.logging')
    def test_rollback_from_tsv_integration(self, mock_logging):
        """統合テスト：TSVからのロールバック実行"""
        # テストファイル作成
        file1 = self.temp_path / "rename_test.pdf"
        file2 = self.outdir / "delete_test.pdf"
        missing_file = self.temp_path / "missing.pdf"
        
        file1.write_text("file1 content")
        file2.write_text("file2 content")
        
        # TSVデータ作成
        entries_data = [
            {
                'old_path': str(self.temp_path / "original1.pdf"),
                'new_path': str(file1),
                'kind': 'sell', 'name': '物件1', 'amount': '1000000',
                'timestamp': '2024-01-01T12:00:00', 'notes': 'test1'
            },
            {
                'old_path': str(self.temp_path / "original2.pdf"), 
                'new_path': str(file2),
                'kind': 'rent', 'name': '物件2', 'amount': '180000',
                'timestamp': '2024-01-01T12:01:00', 'notes': 'test2'
            },
            {
                'old_path': str(self.temp_path / "original3.pdf"),
                'new_path': str(missing_file),
                'kind': 'sell', 'name': '物件3', 'amount': '5000000',
                'timestamp': '2024-01-01T12:02:00', 'notes': 'test3'
            }
        ]
        
        tsv_path = self.create_tsv_file(entries_data)
        
        # ロールバック実行
        result = rollback_from_tsv(tsv_path, dry_run=False)
        
        # 結果検証
        self.assertEqual(result.success_count, 2)  # rename + delete
        self.assertEqual(result.failure_count, 0)
        self.assertEqual(result.skip_count, 1)  # missing file
        
        # ファイル状態確認
        self.assertTrue((self.temp_path / "original1.pdf").exists())  # リネーム完了
        self.assertFalse(file1.exists())  # 元ファイルは存在しない
        self.assertFalse(file2.exists())  # 削除完了

    def test_rollback_from_tsv_empty_file(self):
        """空TSVファイルテスト"""
        # 空のTSVファイル作成
        tsv_path = self.temp_path / "empty.tsv"
        with open(tsv_path, 'w', encoding='utf-8') as f:
            f.write("old_path\tnew_path\tkind\tname\tamount\ttimestamp\tnotes\n")
        
        result = rollback_from_tsv(tsv_path, dry_run=False)
        
        self.assertEqual(result.success_count, 0)
        self.assertEqual(result.failure_count, 0)
        self.assertEqual(result.skip_count, 0)


if __name__ == '__main__':
    unittest.main()