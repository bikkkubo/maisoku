from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging

LOG = logging.getLogger("mysoku_renamer.tsv_logger")


class TSVLogger:
    """TSVファイルの読み書きを管理するクラス"""
    
    def __init__(self, encoding: str = "utf-8"):
        self.encoding = encoding
    
    def write_rollback_tsv(self, 
                          operations: List[Dict[str, Any]], 
                          output_path: Path) -> bool:
        """
        ロールバック用TSVファイルを書き出す
        
        Args:
            operations: 操作結果リスト
            output_path: 出力パス
            
        Returns:
            書き込み成功可否
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            headers = ['old_path', 'new_path', 'kind', 'name', 'amount', 'timestamp', 'notes']
            
            with output_path.open('w', newline='', encoding=self.encoding) as f:
                writer = csv.writer(f, delimiter='\t')
                writer.writerow(headers)
                
                for op in operations:
                    row = [
                        op.get('old_path', ''),
                        op.get('new_path', ''),
                        op.get('kind', ''),
                        op.get('name', ''),
                        str(op.get('amount', '')) if op.get('amount') else '',
                        op.get('timestamp', datetime.now().isoformat()),
                        op.get('notes', '')
                    ]
                    writer.writerow(row)
            
            LOG.info("Rollback TSV written: %s (%d operations)", output_path, len(operations))
            return True
            
        except Exception as e:
            LOG.error("Failed to write rollback TSV: %s", e)
            return False
    
    def write_error_tsv(self, 
                       errors: List[Dict[str, Any]], 
                       output_path: Path,
                       append: bool = True) -> bool:
        """
        エラー情報をTSVファイルに書き出す
        
        Args:
            errors: エラー情報リスト
            output_path: 出力パス
            append: 追記モード
            
        Returns:
            書き込み成功可否
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            mode = 'a' if append and output_path.exists() else 'w'
            headers = ['original_path', 'error_type', 'error_message', 'timestamp']
            
            with output_path.open(mode, newline='', encoding=self.encoding) as f:
                writer = csv.writer(f, delimiter='\t')
                
                # ヘッダーを書き込む（新規作成時のみ）
                if mode == 'w':
                    writer.writerow(headers)
                
                for error in errors:
                    row = [
                        error.get('original_path', ''),
                        error.get('error_type', ''),
                        error.get('error_message', ''),
                        error.get('timestamp', datetime.now().isoformat())
                    ]
                    writer.writerow(row)
            
            LOG.debug("Error TSV written: %s (%d errors)", output_path, len(errors))
            return True
            
        except Exception as e:
            LOG.error("Failed to write error TSV: %s", e)
            return False
    
    def write_preview_tsv(self, 
                         results: List[Dict[str, Any]], 
                         output_path: Path) -> bool:
        """
        プレビュー結果をTSVファイルに書き出す
        
        Args:
            results: 結果リスト
            output_path: 出力パス
            
        Returns:
            書き込み成功可否
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            headers = ['path', 'status', 'kind', 'name', 'amount', 'text_length', 'new_name', 'notes']
            
            with output_path.open('w', newline='', encoding=self.encoding) as f:
                writer = csv.writer(f, delimiter='\t')
                writer.writerow(headers)
                
                for result in results:
                    row = [
                        result.get('path', ''),
                        result.get('status', ''),
                        result.get('kind', ''),
                        result.get('name', ''),
                        str(result.get('amount', '')) if result.get('amount') else '',
                        str(result.get('text_length', '')) if result.get('text_length') is not None else '',
                        result.get('new_name', ''),
                        result.get('notes', '')
                    ]
                    writer.writerow(row)
            
            LOG.info("Preview TSV written: %s (%d results)", output_path, len(results))
            return True
            
        except Exception as e:
            LOG.error("Failed to write preview TSV: %s", e)
            return False
    
    def write_apply_tsv(self, 
                       results: List[Dict[str, Any]], 
                       output_path: Path) -> bool:
        """
        apply結果をTSVファイルに書き出す
        
        Args:
            results: 結果リスト
            output_path: 出力パス
            
        Returns:
            書き込み成功可否
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            headers = ['path', 'status', 'kind', 'name', 'amount', 'text_length', 
                      'new_name', 'actual_new_path', 'timestamp', 'notes']
            
            with output_path.open('w', newline='', encoding=self.encoding) as f:
                writer = csv.writer(f, delimiter='\t')
                writer.writerow(headers)
                
                for result in results:
                    row = [
                        result.get('path', ''),
                        result.get('status', ''),
                        result.get('kind', ''),
                        result.get('name', ''),
                        str(result.get('amount', '')) if result.get('amount') else '',
                        str(result.get('text_length', '')) if result.get('text_length') is not None else '',
                        result.get('new_name', ''),
                        result.get('actual_new_path', ''),
                        result.get('timestamp', datetime.now().isoformat()),
                        result.get('notes', '')
                    ]
                    writer.writerow(row)
            
            LOG.info("Apply TSV written: %s (%d results)", output_path, len(results))
            return True
            
        except Exception as e:
            LOG.error("Failed to write apply TSV: %s", e)
            return False
    
    def read_rollback_tsv(self, input_path: Path) -> List[Dict[str, str]]:
        """
        ロールバック用TSVファイルを読み込む
        
        Args:
            input_path: 入力パス
            
        Returns:
            読み込まれたデータリスト
        """
        try:
            if not input_path.exists():
                LOG.error("Rollback TSV not found: %s", input_path)
                return []
            
            results = []
            with input_path.open('r', encoding=self.encoding) as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    results.append(dict(row))
            
            LOG.info("Rollback TSV read: %s (%d entries)", input_path, len(results))
            return results
            
        except Exception as e:
            LOG.error("Failed to read rollback TSV: %s", e)
            return []
    
    def validate_tsv_format(self, 
                           tsv_path: Path, 
                           expected_headers: List[str]) -> Dict[str, Union[bool, str, List[str]]]:
        """
        TSVファイルの形式を検証する
        
        Args:
            tsv_path: 検証対象のTSVパス
            expected_headers: 期待されるヘッダーリスト
            
        Returns:
            検証結果辞書
        """
        result = {
            'valid': False,
            'exists': tsv_path.exists(),
            'readable': False,
            'headers_match': False,
            'row_count': 0,
            'actual_headers': [],
            'error_message': ''
        }
        
        try:
            if not result['exists']:
                result['error_message'] = 'File does not exist'
                return result
            
            with tsv_path.open('r', encoding=self.encoding) as f:
                reader = csv.reader(f, delimiter='\t')
                try:
                    actual_headers = next(reader)
                    result['actual_headers'] = actual_headers
                    result['readable'] = True
                    
                    # ヘッダーの一致確認
                    result['headers_match'] = actual_headers == expected_headers
                    
                    # 行数カウント
                    row_count = sum(1 for _ in reader)
                    result['row_count'] = row_count
                    
                    result['valid'] = result['readable'] and result['headers_match']
                    
                except StopIteration:
                    result['error_message'] = 'Empty file or no headers'
                    
        except Exception as e:
            result['error_message'] = str(e)
        
        return result


def generate_timestamped_filename(base_name: str, 
                                 extension: str = '.tsv',
                                 timestamp: Optional[datetime] = None) -> str:
    """
    タイムスタンプ付きファイル名を生成する
    
    Args:
        base_name: ベースファイル名
        extension: 拡張子
        timestamp: タイムスタンプ（Noneなら現在時刻）
        
    Returns:
        タイムスタンプ付きファイル名
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
    return f"{base_name}_{timestamp_str}{extension}"


def create_rollback_entry(original_path: str,
                         new_path: str,
                         kind: str = '',
                         name: str = '',
                         amount: Union[int, str, None] = None,
                         notes: str = '') -> Dict[str, Any]:
    """
    ロールバックエントリを作成する
    
    Args:
        original_path: 元のファイルパス
        new_path: 新しいファイルパス
        kind: 取引種別
        name: 物件名
        amount: 金額
        notes: 備考
        
    Returns:
        ロールバックエントリ辞書
    """
    return {
        'old_path': original_path,
        'new_path': new_path,
        'kind': kind,
        'name': name,
        'amount': amount,
        'timestamp': datetime.now().isoformat(),
        'notes': notes
    }