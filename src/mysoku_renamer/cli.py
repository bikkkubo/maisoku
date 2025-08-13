import argparse
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from .types import ProcessResult
from .pdf_processor import analyze_pdf
from .info_parser import parse_info
from .file_namer import generate_filename, generate_collision_free_filename
from .file_manager import FileManager, preview_file_operations
from .tsv_logger import TSVLogger, generate_timestamped_filename, create_rollback_entry

LOG = logging.getLogger("mysoku_renamer")

def find_pdfs(path: Path, max_files: int | None = None) -> List[Path]:
    if path.is_file() and path.suffix.lower() == ".pdf":
        candidates = [path]
    elif path.is_dir():
        candidates = sorted(p for p in path.rglob("*.pdf"))
    else:
        raise FileNotFoundError(f"Path not found or not a PDF: {path}")
    return candidates[:max_files] if max_files else candidates

def _process_single_pdf(pdf_path: Path, allow_ocr: bool = False) -> tuple[ProcessResult, dict]:
    """
    単一PDFファイルを処理する
    
    Args:
        pdf_path: 処理対象PDFファイル
        allow_ocr: OCR機能を有効にするか（デフォルト: False）
    
    Returns:
        (ProcessResult, info_dict) のタプル
    """
    try:
        LOG.debug("Processing: %s (OCR: %s)", pdf_path, "enabled" if allow_ocr else "disabled")
        ar = analyze_pdf(pdf_path, allow_ocr=allow_ocr)
        info = parse_info(ar.text)
        
        # 新しいファイル名を生成
        new_filename = generate_filename(info, pdf_path)
        
        result = ProcessResult(
            path=str(pdf_path),
            status="OK",
            text_length=ar.text_length,
            new_name=new_filename,
            notes=("needs_ocr" if ar.needs_ocr else ar.note),
        )
        
        # 動的属性として情報を追加
        setattr(result, "kind", info.kind)
        setattr(result, "name", info.name)
        setattr(result, "amount", info.amount)
        
        info_dict = {
            'kind': info.kind,
            'name': info.name,
            'amount': info.amount,
            'needs_ocr': ar.needs_ocr
        }
        
        return result, info_dict
        
    except Exception as e:
        LOG.debug("Error processing %s: %s", pdf_path, e)
        
        error_result = ProcessResult(
            path=str(pdf_path),
            status="ERROR",
            text_length=None,
            new_name=None,
            notes=f"{type(e).__name__}: {str(e)[:100]}",
        )
        
        # エラー時は空の属性を設定
        setattr(error_result, "kind", "")
        setattr(error_result, "name", "")
        setattr(error_result, "amount", "")
        
        error_dict = {
            'kind': '',
            'name': '',
            'amount': '',
            'needs_ocr': False
        }
        
        return error_result, error_dict

def setup_logging(debug: bool, logfile: str | None) -> None:
    level = logging.DEBUG if debug else logging.INFO
    handlers = [logging.StreamHandler()]
    if logfile:
        handlers.append(logging.FileHandler(logfile, encoding="utf-8"))
    logging.basicConfig(level=level, handlers=handlers, format="%(levelname)s %(message)s")

def cmd_dry_run(args: argparse.Namespace) -> int:
    """ドライランモード：実際のファイル変更は行わず、処理結果をプレビューする"""
    base = Path(args.path).expanduser().resolve()
    pdfs = find_pdfs(base, args.max_files)

    rows: List[ProcessResult] = []
    
    # 統計情報
    stats = {
        "error_count": 0,
        "ocr_needed_count": 0,
        "ocr_used_count": 0,
        "kind_stats": {"sell": 0, "rent": 0, "unknown": 0},
        "name_missing": 0,
        "amount_missing": 0
    }
    
    # T4: ファイル操作のプレビュー用リスト
    preview_paths = []
    preview_names = []
    
    # 各PDFを処理
    for p in pdfs:
        result, info_dict = _process_single_pdf(p, allow_ocr=args.ocr)
        rows.append(result)
        
        # 統計更新
        if result.status == "ERROR":
            stats["error_count"] += 1
        else:
            if info_dict["needs_ocr"]:
                stats["ocr_needed_count"] += 1
            
            # OCR使用統計
            if args.ocr and result.notes and "ocr_ok" in result.notes:
                stats["ocr_used_count"] += 1
            
            kind = info_dict["kind"]
            if kind in stats["kind_stats"]:
                stats["kind_stats"][kind] += 1
            
            if not info_dict["name"]:
                stats["name_missing"] += 1
            if not info_dict["amount"]:
                stats["amount_missing"] += 1
                
            # プレビュー用データ
            if result.new_name:
                preview_paths.append(p)
                preview_names.append(result.new_name)

    # T4: ファイル操作プレビューの生成
    output_dir = Path(args.outdir).resolve() if hasattr(args, 'outdir') and args.outdir else None
    if preview_paths:
        file_preview = preview_file_operations(preview_paths, preview_names, output_dir)
        LOG.info("File operation preview: %s mode, %d files, %d collisions expected", 
                 file_preview['operation_type'], 
                 file_preview['total_files'],
                 file_preview['collisions_expected'])

    # TSV出力
    out_tsv = Path(args.output or "mysoku_preview.tsv").resolve()
    tsv_logger = TSVLogger()
    
    # ResultをTSV用の辞書に変換
    tsv_data = []
    for r in rows:
        tsv_data.append({
            'path': r.path,
            'status': r.status,
            'kind': getattr(r, 'kind', ''),
            'name': getattr(r, 'name', ''),
            'amount': getattr(r, 'amount', ''),
            'text_length': r.text_length,
            'new_name': r.new_name,
            'notes': r.notes
        })
    
    success = tsv_logger.write_preview_tsv(tsv_data, out_tsv)
    if not success:
        LOG.error("Failed to write preview TSV")
        return 1
    
    # 結果サマリー
    success_count = len(rows) - stats["error_count"]
    if args.ocr and stats["ocr_used_count"] > 0:
        LOG.info("dry-run completed: %d total, %d success, %d errors, %d OCR used -> %s", 
                 len(rows), success_count, stats["error_count"], stats["ocr_used_count"], out_tsv)
    else:
        LOG.info("dry-run completed: %d total, %d success, %d errors, %d need OCR -> %s", 
                 len(rows), success_count, stats["error_count"], stats["ocr_needed_count"], out_tsv)
    
    # 詳細統計
    if success_count > 0:
        LOG.info("Kind distribution: sell=%d, rent=%d, unknown=%d", 
                 stats["kind_stats"]["sell"], stats["kind_stats"]["rent"], stats["kind_stats"]["unknown"])
        LOG.info("Missing data: name=%d, amount=%d", 
                 stats["name_missing"], stats["amount_missing"])
    
    return 0

def cmd_apply(args: argparse.Namespace) -> int:
    """アプライモード：実際にファイルのリネーム/コピーを実行する"""
    base = Path(args.path).expanduser().resolve()
    pdfs = find_pdfs(base, args.max_files)
    
    # 出力ディレクトリの設定
    output_dir = Path(args.outdir).resolve() if hasattr(args, 'outdir') and args.outdir else None
    strict_mode = hasattr(args, 'strict') and args.strict
    
    # FileManager初期化
    file_manager = FileManager(strict_mode=strict_mode)
    tsv_logger = TSVLogger()
    
    # タイムスタンプ付きファイル名の生成
    timestamp = datetime.now()
    rollback_filename = generate_timestamped_filename("mysoku_rollback", ".tsv", timestamp)
    apply_filename = generate_timestamped_filename("mysoku_apply", ".tsv", timestamp)
    
    rollback_path = base / rollback_filename
    apply_path = Path(args.output or apply_filename).resolve()
    
    LOG.info("Starting apply mode: %s -> %s", 
             "copy" if output_dir else "rename", 
             str(output_dir) if output_dir else "same directory")
    
    # 処理結果とロールバック情報を格納
    results = []
    rollback_entries = []
    errors = []
    
    # 統計情報
    stats = {
        "total": len(pdfs),
        "success": 0,
        "errors": 0,
        "ocr_needed": 0,
        "ocr_used": 0
    }
    
    # 各PDFを処理
    for i, p in enumerate(pdfs, 1):
        LOG.debug("Processing (%d/%d): %s", i, len(pdfs), p)
        
        try:
            # PDF解析・情報抽出
            result, info_dict = _process_single_pdf(p, allow_ocr=args.ocr)
            
            if result.status == "ERROR":
                stats["errors"] += 1
                errors.append({
                    'original_path': str(p),
                    'error_type': 'PDF_PROCESSING_ERROR',
                    'error_message': result.notes,
                    'timestamp': timestamp.isoformat()
                })
                results.append(result)
                continue
            
            if info_dict["needs_ocr"]:
                stats["ocr_needed"] += 1
            
            # OCR使用統計
            if args.ocr and result.notes and "ocr_ok" in result.notes:
                stats["ocr_used"] += 1
            
            # ファイル操作実行
            if output_dir:
                # コピーモード
                file_result = file_manager.copy_file(p, result.new_name, output_dir)
            else:
                # リネームモード  
                file_result = file_manager.rename_file(p, result.new_name)
            
            # 結果の更新
            if file_result.success:
                stats["success"] += 1
                result.notes = f"Applied: {file_result.operation_type} successful"
                
                # actual_new_path を設定
                setattr(result, 'actual_new_path', file_result.final_path)
                setattr(result, 'timestamp', timestamp.isoformat())
                
                # ロールバック情報記録
                rollback_entry = create_rollback_entry(
                    original_path=str(p),
                    new_path=file_result.final_path,
                    kind=getattr(result, 'kind', ''),
                    name=getattr(result, 'name', ''),
                    amount=getattr(result, 'amount', ''),
                    notes=f"{file_result.operation_type}_success"
                )
                rollback_entries.append(rollback_entry)
                
            else:
                stats["errors"] += 1
                result.status = "ERROR"
                result.notes = f"File operation failed: {file_result.error_message}"
                setattr(result, 'actual_new_path', '')
                setattr(result, 'timestamp', timestamp.isoformat())
                
                errors.append({
                    'original_path': str(p),
                    'error_type': 'FILE_OPERATION_ERROR', 
                    'error_message': file_result.error_message,
                    'timestamp': timestamp.isoformat()
                })
                
                # Strictモードで即座終了
                if strict_mode:
                    LOG.error("Strict mode: stopping at first error")
                    break
            
            results.append(result)
            
        except Exception as e:
            stats["errors"] += 1
            LOG.error("Unexpected error processing %s: %s", p, e)
            
            error_result = ProcessResult(
                path=str(p),
                status="ERROR",
                text_length=None,
                new_name=None,
                notes=f"Unexpected error: {type(e).__name__}: {str(e)[:100]}"
            )
            setattr(error_result, 'kind', '')
            setattr(error_result, 'name', '')
            setattr(error_result, 'amount', '')
            setattr(error_result, 'actual_new_path', '')
            setattr(error_result, 'timestamp', timestamp.isoformat())
            
            results.append(error_result)
            
            errors.append({
                'original_path': str(p),
                'error_type': 'UNEXPECTED_ERROR',
                'error_message': str(e),
                'timestamp': timestamp.isoformat()
            })
            
            if strict_mode:
                LOG.error("Strict mode: stopping at unexpected error")
                break
    
    # ロールバックTSVの書き出し（必須）
    if rollback_entries:
        rollback_success = tsv_logger.write_rollback_tsv(rollback_entries, rollback_path)
        if rollback_success:
            LOG.info("Rollback TSV written: %s", rollback_path)
        else:
            LOG.error("Failed to write rollback TSV: %s", rollback_path)
    
    # 適用結果TSVの書き出し
    apply_data = []
    for r in results:
        apply_data.append({
            'path': r.path,
            'status': r.status,
            'kind': getattr(r, 'kind', ''),
            'name': getattr(r, 'name', ''),
            'amount': getattr(r, 'amount', ''),
            'text_length': r.text_length,
            'new_name': r.new_name,
            'actual_new_path': getattr(r, 'actual_new_path', ''),
            'timestamp': getattr(r, 'timestamp', timestamp.isoformat()),
            'notes': r.notes
        })
    
    apply_success = tsv_logger.write_apply_tsv(apply_data, apply_path)
    if not apply_success:
        LOG.error("Failed to write apply results TSV")
    
    # エラーTSVの書き出し
    if errors:
        error_tsv_path = base / "errors.tsv"
        tsv_logger.write_error_tsv(errors, error_tsv_path, append=True)
    
    # 結果サマリー
    LOG.info("apply completed: %d total, %d success, %d errors -> %s", 
             stats["total"], stats["success"], stats["errors"], apply_path)
    
    # OCR統計
    if args.ocr and stats["ocr_used"] > 0:
        LOG.info("OCR usage: %d files processed successfully with OCR", stats["ocr_used"])
    elif stats["ocr_needed"] > 0 and not args.ocr:
        LOG.info("OCR candidates: %d files (consider using --ocr in future)", stats["ocr_needed"])
    
    # 操作サマリー
    operation_summary = file_manager.get_operation_summary()
    if operation_summary['total_operations'] > 0:
        LOG.info("File operations: %d total, %d successful, %d collisions avoided",
                 operation_summary['total_operations'],
                 operation_summary['successful'], 
                 operation_summary['collision_avoided'])
    
    # 終了コード決定
    return 1 if stats["errors"] > 0 else 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mysoku-rename", description="Mysoku PDF renamer with OCR support")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Preview only (TSV output)")
    mode.add_argument("--apply", action="store_true", help="Rename/copy files with rollback TSV")
    
    p.add_argument("path", help="PDF file or directory")
    p.add_argument("--output", help="TSV path for preview/apply results")
    p.add_argument("--outdir", help="Copy files to this directory (default: rename in same directory)")
    p.add_argument("--max-files", type=int, help="Limit number of PDFs to process")
    p.add_argument("--strict", action="store_true", help="Stop at first error (apply mode only)")
    p.add_argument("--ocr", action="store_true", help="Enable OCR fallback when text is scarce (requires tesseract)")
    p.add_argument("--debug", action="store_true", help="Enable debug logs")
    p.add_argument("--logfile", help="Log file path")
    return p

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.debug, args.logfile)
    if args.dry_run:
        return cmd_dry_run(args)
    if args.apply:
        return cmd_apply(args)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())