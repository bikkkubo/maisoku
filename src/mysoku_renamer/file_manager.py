from __future__ import annotations
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict
import logging

LOG = logging.getLogger("mysoku_renamer.file_manager")


@dataclass
class FileOperationResult:
    original_path: str
    target_filename: str
    final_path: Optional[str]
    success: bool
    error_message: Optional[str] = None
    operation_type: str = "rename"  # "rename" | "copy"


class FileManager:
    """ファイル操作を管理するクラス"""
    
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.operation_log: List[FileOperationResult] = []
    
    def rename_file(self, original_path: Path, new_filename: str) -> FileOperationResult:
        """
        同一ディレクトリ内でファイルをリネームする
        
        Args:
            original_path: 元のファイルパス
            new_filename: 新しいファイル名
            
        Returns:
            操作結果
        """
        try:
            if not original_path.exists():
                return FileOperationResult(
                    original_path=str(original_path),
                    target_filename=new_filename,
                    final_path=None,
                    success=False,
                    error_message="Original file does not exist",
                    operation_type="rename"
                )
            
            target_dir = original_path.parent
            collision_free_name = self._get_collision_free_name(new_filename, target_dir)
            target_path = target_dir / collision_free_name
            
            LOG.debug("Renaming %s -> %s", original_path, target_path)
            original_path.rename(target_path)
            
            result = FileOperationResult(
                original_path=str(original_path),
                target_filename=new_filename,
                final_path=str(target_path),
                success=True,
                operation_type="rename"
            )
            self.operation_log.append(result)
            return result
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            LOG.debug("Rename failed: %s", error_msg)
            
            result = FileOperationResult(
                original_path=str(original_path),
                target_filename=new_filename,
                final_path=None,
                success=False,
                error_message=error_msg,
                operation_type="rename"
            )
            self.operation_log.append(result)
            
            if self.strict_mode:
                raise
            return result
    
    def copy_file(self, original_path: Path, new_filename: str, output_dir: Path) -> FileOperationResult:
        """
        ファイルを指定ディレクトリにコピーする
        
        Args:
            original_path: 元のファイルパス
            new_filename: 新しいファイル名
            output_dir: コピー先ディレクトリ
            
        Returns:
            操作結果
        """
        try:
            if not original_path.exists():
                return FileOperationResult(
                    original_path=str(original_path),
                    target_filename=new_filename,
                    final_path=None,
                    success=False,
                    error_message="Original file does not exist",
                    operation_type="copy"
                )
            
            # 出力ディレクトリを作成
            output_dir.mkdir(parents=True, exist_ok=True)
            
            collision_free_name = self._get_collision_free_name(new_filename, output_dir)
            target_path = output_dir / collision_free_name
            
            LOG.debug("Copying %s -> %s", original_path, target_path)
            shutil.copy2(original_path, target_path)
            
            result = FileOperationResult(
                original_path=str(original_path),
                target_filename=new_filename,
                final_path=str(target_path),
                success=True,
                operation_type="copy"
            )
            self.operation_log.append(result)
            return result
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            LOG.debug("Copy failed: %s", error_msg)
            
            result = FileOperationResult(
                original_path=str(original_path),
                target_filename=new_filename,
                final_path=None,
                success=False,
                error_message=error_msg,
                operation_type="copy"
            )
            self.operation_log.append(result)
            
            if self.strict_mode:
                raise
            return result
    
    def _get_collision_free_name(self, filename: str, target_dir: Path) -> str:
        """
        衝突を回避したファイル名を生成する
        
        Args:
            filename: 希望するファイル名
            target_dir: 対象ディレクトリ
            
        Returns:
            衝突回避済みファイル名
        """
        if not target_dir.exists():
            return filename
        
        target_path = target_dir / filename
        if not target_path.exists():
            return filename
        
        # 拡張子とステムを分離
        path_obj = Path(filename)
        stem = path_obj.stem
        suffix = path_obj.suffix
        
        # 連番を付けて衝突回避
        for i in range(1, 1000):
            candidate = f"{stem}-{i}{suffix}"
            if not (target_dir / candidate).exists():
                LOG.debug("Collision avoided: %s -> %s", filename, candidate)
                return candidate
        
        # 1000まで試してダメな場合はタイムスタンプ付与
        import time
        timestamp = int(time.time())
        fallback_name = f"{stem}-{timestamp}{suffix}"
        LOG.warning("High collision count, using timestamp: %s", fallback_name)
        return fallback_name
    
    def batch_process(self, 
                     file_operations: List[Dict], 
                     output_dir: Optional[Path] = None) -> Dict[str, int]:
        """
        複数ファイルの一括処理
        
        Args:
            file_operations: 操作リスト [{'path': Path, 'new_name': str}, ...]
            output_dir: 出力ディレクトリ（Noneなら rename モード）
            
        Returns:
            処理結果統計
        """
        stats = {'success': 0, 'error': 0, 'total': len(file_operations)}
        
        for operation in file_operations:
            original_path = Path(operation['path'])
            new_filename = operation['new_name']
            
            if output_dir:
                result = self.copy_file(original_path, new_filename, output_dir)
            else:
                result = self.rename_file(original_path, new_filename)
            
            if result.success:
                stats['success'] += 1
            else:
                stats['error'] += 1
                LOG.warning("Operation failed: %s -> %s (%s)", 
                           original_path, new_filename, result.error_message)
        
        return stats
    
    def get_operation_summary(self) -> Dict:
        """
        実行された操作の統計を取得する
        
        Returns:
            操作統計
        """
        total = len(self.operation_log)
        successful = sum(1 for op in self.operation_log if op.success)
        failed = total - successful
        
        rename_count = sum(1 for op in self.operation_log if op.operation_type == "rename")
        copy_count = sum(1 for op in self.operation_log if op.operation_type == "copy")
        
        return {
            'total_operations': total,
            'successful': successful,
            'failed': failed,
            'rename_operations': rename_count,
            'copy_operations': copy_count,
            'collision_avoided': sum(1 for op in self.operation_log 
                                   if op.success and op.target_filename != Path(op.final_path).name)
        }
    
    def get_failed_operations(self) -> List[FileOperationResult]:
        """
        失敗した操作のリストを取得する
        
        Returns:
            失敗した操作のリスト
        """
        return [op for op in self.operation_log if not op.success]
    
    def clear_log(self):
        """操作ログをクリアする"""
        self.operation_log.clear()


def preview_file_operations(file_list: List[Path], 
                          new_names: List[str],
                          output_dir: Optional[Path] = None) -> Dict:
    """
    ファイル操作のプレビューを生成する（実際の操作は行わない）
    
    Args:
        file_list: 対象ファイルリスト
        new_names: 新しいファイル名リスト
        output_dir: 出力ディレクトリ（Noneならrename）
        
    Returns:
        プレビュー結果
    """
    if len(file_list) != len(new_names):
        raise ValueError("file_list and new_names must have the same length")
    
    preview = {
        'total_files': len(file_list),
        'operation_type': 'copy' if output_dir else 'rename',
        'collisions_expected': 0,
        'missing_files': 0,
        'target_directory': str(output_dir) if output_dir else 'same_as_source',
        'operations': []
    }
    
    for original_path, new_name in zip(file_list, new_names):
        target_dir = output_dir if output_dir else original_path.parent
        
        # 存在チェック
        if not original_path.exists():
            preview['missing_files'] += 1
            continue
        
        # 衝突チェック
        collision_free_name = new_name
        if target_dir.exists():
            temp_manager = FileManager()
            collision_free_name = temp_manager._get_collision_free_name(new_name, target_dir)
            if collision_free_name != new_name:
                preview['collisions_expected'] += 1
        
        preview['operations'].append({
            'original': str(original_path),
            'target_name': new_name,
            'final_name': collision_free_name,
            'will_collide': collision_free_name != new_name
        })
    
    return preview