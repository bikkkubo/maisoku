#!/usr/bin/env python3
"""
ロールバックスクリプト - TSVファイルからファイル操作を逆転

使用方法:
    python scripts/rollback_from_tsv.py --tsv rollback.tsv [--dry-run]
    python scripts/rollback_from_tsv.py --tsv apply_result.tsv [--dry-run]

TSVフォーマット期待値:
    old_path,new_path,kind,name,amount,timestamp,notes
    または
    path,actual_new_path,kind,name,amount,timestamp,notes

動作:
    1. new_path が存在する場合 → old_path にリネーム/移動
    2. old_path が異なるディレクトリの場合 → new_path を削除（outdir運用時）
    3. 失敗時は errors.tsv に記録
"""

import argparse
import csv
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional


class RollbackEntry(NamedTuple):
    old_path: str
    new_path: str
    kind: str
    name: str
    amount: str
    timestamp: str
    notes: str


class RollbackResult(NamedTuple):
    success_count: int
    failure_count: int
    skip_count: int
    errors: List[Dict[str, str]]


def setup_logging(debug: bool = False) -> None:
    """ログ設定"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def parse_tsv_file(tsv_path: Path) -> List[RollbackEntry]:
    """TSVファイルを解析してRollbackEntryリストを生成"""
    entries = []
    
    try:
        with open(tsv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            
            for row_num, row in enumerate(reader, start=2):  # ヘッダー行を1行目とする
                try:
                    # TSV列の柔軟な解析（old_path/new_pathまたはpath/actual_new_path）
                    old_path = row.get('old_path', row.get('path', ''))
                    new_path = row.get('new_path', row.get('actual_new_path', ''))
                    
                    if not old_path or not new_path:
                        logging.warning(f"行{row_num}: old_path または new_path が空です - スキップ")
                        continue
                    
                    entry = RollbackEntry(
                        old_path=old_path,
                        new_path=new_path,
                        kind=row.get('kind', ''),
                        name=row.get('name', ''),
                        amount=row.get('amount', ''),
                        timestamp=row.get('timestamp', ''),
                        notes=row.get('notes', '')
                    )
                    entries.append(entry)
                    
                except Exception as e:
                    logging.error(f"行{row_num}の解析エラー: {e}")
                    continue
                    
    except FileNotFoundError:
        logging.error(f"TSVファイルが見つかりません: {tsv_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"TSVファイル読み込みエラー: {e}")
        sys.exit(1)
    
    return entries


def determine_rollback_action(entry: RollbackEntry) -> str:
    """ロールバック動作の判定"""
    old_path = Path(entry.old_path)
    new_path = Path(entry.new_path)
    
    if not new_path.exists():
        return "skip_not_found"
    
    # 同一ディレクトリ内の場合はリネーム
    if old_path.parent == new_path.parent:
        if old_path.exists():
            return "skip_collision"  # 衝突回避
        else:
            return "rename"
    
    # 異なるディレクトリ（outdir運用）の場合は削除
    else:
        return "delete"


def execute_rollback_action(entry: RollbackEntry, action: str, dry_run: bool = False) -> Optional[str]:
    """ロールバック動作実行"""
    old_path = Path(entry.old_path)
    new_path = Path(entry.new_path)
    
    try:
        if action == "rename":
            if dry_run:
                logging.info(f"[DRY-RUN] リネーム: {new_path} → {old_path}")
            else:
                logging.debug(f"リネーム実行: {new_path} → {old_path}")
                new_path.rename(old_path)
            return None
            
        elif action == "delete":
            if dry_run:
                logging.info(f"[DRY-RUN] 削除: {new_path}")
            else:
                logging.debug(f"削除実行: {new_path}")
                new_path.unlink()
            return None
            
        elif action == "skip_not_found":
            logging.debug(f"スキップ（ファイル不存在）: {new_path}")
            return None
            
        elif action == "skip_collision":
            logging.warning(f"スキップ（衝突）: {old_path} が既に存在")
            return f"衝突: {old_path} が既に存在"
            
        else:
            return f"不明なアクション: {action}"
            
    except Exception as e:
        error_msg = f"操作失敗 ({action}): {e}"
        logging.error(f"{new_path} - {error_msg}")
        return error_msg


def write_errors_tsv(errors: List[Dict[str, str]], errors_tsv_path: Path) -> None:
    """エラー情報をTSVに出力"""
    if not errors:
        return
        
    try:
        # 既存ファイルがあれば追記モード
        file_exists = errors_tsv_path.exists()
        
        with open(errors_tsv_path, 'a', encoding='utf-8', newline='') as f:
            fieldnames = ['original_path', 'error_type', 'error_message', 'timestamp']
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
            
            if not file_exists:
                writer.writeheader()
            
            for error in errors:
                writer.writerow(error)
                
        logging.info(f"エラー情報を記録: {errors_tsv_path} ({len(errors)}件)")
        
    except Exception as e:
        logging.error(f"エラーTSV書き込み失敗: {e}")


def rollback_from_tsv(tsv_path: Path, dry_run: bool = False) -> RollbackResult:
    """TSVファイルからロールバック実行"""
    entries = parse_tsv_file(tsv_path)
    
    if not entries:
        logging.warning("処理対象のエントリがありません")
        return RollbackResult(0, 0, 0, [])
    
    logging.info(f"ロールバック開始: {len(entries)}件 {'（ドライラン）' if dry_run else ''}")
    
    success_count = 0
    failure_count = 0
    skip_count = 0
    errors = []
    
    for i, entry in enumerate(entries, start=1):
        logging.debug(f"処理中 [{i}/{len(entries)}]: {entry.new_path}")
        
        action = determine_rollback_action(entry)
        error_message = execute_rollback_action(entry, action, dry_run)
        
        if error_message is None:
            if action in ["rename", "delete"]:
                success_count += 1
            else:
                skip_count += 1
        else:
            failure_count += 1
            errors.append({
                'original_path': entry.new_path,
                'error_type': 'ROLLBACK_ERROR',
                'error_message': error_message,
                'timestamp': datetime.now().isoformat()
            })
    
    return RollbackResult(success_count, failure_count, skip_count, errors)


def main():
    parser = argparse.ArgumentParser(
        description="TSVファイルからmysoku-renameの操作をロールバック",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
    python scripts/rollback_from_tsv.py --tsv rollback_20240101_120000.tsv --dry-run
    python scripts/rollback_from_tsv.py --tsv apply_result.tsv

TSVフォーマット（期待値）:
    old_path	new_path	kind	name	amount	timestamp	notes
    または
    path	actual_new_path	kind	name	amount	timestamp	notes
        """
    )
    
    parser.add_argument(
        '--tsv',
        type=Path,
        required=True,
        help='ロールバック対象のTSVファイル'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='ドライランモード（実際の操作は行わない）'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='デバッグログを有効にする'
    )
    parser.add_argument(
        '--errors-tsv',
        type=Path,
        default=Path('errors.tsv'),
        help='エラー情報の出力先TSVファイル（デフォルト: errors.tsv）'
    )
    
    args = parser.parse_args()
    
    # ログ設定
    setup_logging(args.debug)
    
    # TSVファイル存在確認
    if not args.tsv.exists():
        logging.error(f"TSVファイルが存在しません: {args.tsv}")
        sys.exit(1)
    
    # ロールバック実行
    try:
        result = rollback_from_tsv(args.tsv, args.dry_run)
        
        # 結果サマリー
        logging.info("=" * 50)
        logging.info("ロールバック結果:")
        logging.info(f"  成功: {result.success_count}件")
        logging.info(f"  失敗: {result.failure_count}件") 
        logging.info(f"  スキップ: {result.skip_count}件")
        logging.info(f"  合計: {result.success_count + result.failure_count + result.skip_count}件")
        
        # エラー記録
        if result.errors:
            write_errors_tsv(result.errors, args.errors_tsv)
            
        # 終了コード
        exit_code = 1 if result.failure_count > 0 else 0
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logging.info("ユーザーによって中断されました")
        sys.exit(2)
    except Exception as e:
        logging.error(f"予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()