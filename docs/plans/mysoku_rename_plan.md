# PLAN: マイソクPDF自動リネーム

## 1. アーキテクチャ / 依存
- 構成図(テキスト):
  ```
  CLI Entry Point (mysoku-rename)
  ├── ArgumentParser (--dry-run/--apply/--outdir/--strict/--debug/--logfile/--max-files)
  ├── PDFProcessor (pypdf)
  │   ├── TextExtractor
  │   ├── OCRProcessor (オプション: pytesseract + Pillow)
  │   ├── PropertyNameCleaner (ノイズ語除去)
  │   └── PriceNormalizer (売買/賃貸別価格正規化)
  ├── FileNamer (命名規則適用)
  ├── FileManager (リネーム/コピー、衝突回避)
  ├── TSVLogger (ロールバック用記録)
  └── ErrorHandler (スキップ継続/strict終了)
  ```
- 処理フロー図(テキスト):
  ```
  1. ファイル列挙 (PDFファイル検出、最大500件制限)
     ↓
  2. 抽出処理 (pypdf テキスト抽出、<200文字でOCR判定フラグ)
     ├─ OCRフォールバック (--ocr指定時、text_length<200かつneeds_ocr=True)
     ↓
  3. 情報解析 (売買/賃貸判定、物件名抽出、価格正規化)
     ↓
  4. 命名生成 (命名規則適用、ファイル名文字種正規化)
     ↓
  5. dry-run出力 (プレビューTSV生成、衝突チェック)
     ↓
  6. apply実行 (リネーム/コピー、ロールバックTSV記録、エラーTSV)
  ```
- 主要依存/バージョン（最小方針）:
  - **pypdf**: 最新安定版 (PDF テキスト抽出) - 必須
  - **regex**: パターンマッチング強化 - 必須
  - **オプション依存**: pytesseract + Pillow (OCR機能、`--ocr`フラグ時のみ)
  - **標準ライブラリ**: pathlib, argparse, logging, csv, datetime, sys

## 2. データ/型/IF
- 型定義/スキーマ:
  ```python
  @dataclass
  class ParsedInfo:
      kind: str        # "売買", "賃貸", "その他" 
      name: str        # 物件名 (ノイズ除去後、"物件名未取得" fallback)
      amount: str      # 正規化後金額 ("価格1.5億円", "家賃180,000円", "未取得")
  
  @dataclass  
  class ProcessResult:
      original_path: str
      new_filename: str 
      parsed_info: ParsedInfo
      status: str           # "success", "error", "skipped"
      error_message: str
      timestamp: str        # apply時のみ
      actual_new_path: str  # apply時のみ (衝突回避後の実パス)
  ```
- I/O型定義:
  ```python
  # 入力
  InputArgs = argparse.Namespace  # CLI引数
  PDFPath = Union[str, Path]      # 単一ファイル or ディレクトリ
  
  # 出力TSV列定義
  PreviewTSV = ["original_path", "new_filename", "transaction_type", "property_name", "price_normalized", "status", "error_message"]
  ApplyTSV = PreviewTSV + ["timestamp", "actual_new_path"]  
  ErrorTSV = ["original_path", "error_type", "error_message", "timestamp"]
  RollbackTSV = ["old_path", "new_path", "timestamp"]
  ```
- CLI IF:
  - Entry Point: `mysoku-rename` (console_scripts)
  - 追加フラグ: `--ocr` (OCR機能有効化、デフォルト無効)
  - Exit Codes: 0=正常終了, 1=エラー終了(--strict時), 2=引数エラー

## 3. 例外/リトライ/ログ
- 例外戦略:
  - **継続可能エラー** (スキップ→errors.tsv記録): 
    - PDFReadError, FilePermissionError, UnicodeDecodeError
  - **即座終了エラー**: 
    - DiskFullError, SystemExit, KeyboardInterrupt
  - **strict mode**: `--strict` 指定時は全例外で非0終了
- ログ最小方針:
  - **INFO既定**: 処理件数、成功/失敗/スキップサマリのみ
  - **DEBUG追加** (--debug時): 各ファイル詳細、抽出内容、スタックトレース
  - **ファイル出力** (--logfile時): 上記ログをファイル保存
- エラーTSV出力: 
  - 継続可能エラーは errors.tsv に記録、個人情報除去

## 4. テスト戦略
- **単体テスト** (pytest):
  - `PropertyNameCleaner.clean()`: ノイズ語除去パターン20件
  - `PriceNormalizer.normalize()`: 価格正規化ロジック15件
  - `FileNamer.generate()`: 命名規則生成、エッジケース10件
- **結合テスト**:
  - `PDFProcessor.process()`: サンプルPDF 3種 (売買/賃貸/不明) での抽出精度
  - `FileManager`: 衝突回避、連番付与、権限エラー時の動作
- **受入テスト**:
  - AC1/AC2/AC3 各ケースでの end-to-end 動作確認
  - dry-run と apply の結果整合性 (件数/エラー/TSV列一致)

## 5. 移行/ロールバック
- データ移行: N/A (新規ツール)
- ロールバック仕組み:
  - **自動TSV記録**: apply実行時に `rollback_YYYYMMDD_HHMMSS.tsv` を自動生成
  - **TSVフォーマット**: `old_path,new_path,timestamp` (RollbackTSV型準拠)
  - **復元スクリプト**: `scripts/rollback_from_tsv.py --tsv <rollback_file.tsv> [--dry-run]`
  - **復元方式**: new_path → old_path への逆リネーム/移動

## 6. セキュリティ/権限
- 認可/秘密情報の扱い:
  - ファイルシステム権限に依存 (追加認証なし)
  - PDF内容はメモリ上のみ処理 (永続化しない)
  - ログに個人情報を含めない方針

## 7. OCR機能設計（オプション）
- **起動条件**:
  - `--ocr`フラグが指定されている かつ
  - pypdf抽出結果の`text_length < 200文字` かつ
  - `needs_ocr=True`判定
- **技術選択**:
  - **第一候補**: pytesseract + tesseract-ocr
    - 言語パック: jpn (横書き), jpn_vert (縦書き)
    - ローカル実行、外部通信なし
  - **代替案**: ocrmypdf（将来検討）
- **処理フロー**:
  1. PDF→画像変換 (Pillow, 300dpi)
  2. tesseract実行 (jpn+jpn_vert)
  3. OCRテキスト取得
  4. pypdf抽出テキストと結合
  5. 結合テキストで再解析
- **エラー処理**:
  - tesseract未インストール: 警告ログ、OCRスキップ
  - OCR失敗: 元のpypdf結果を使用
  - メモリ不足: OCRスキップ、継続処理
- **セキュリティ考慮**:
  - 画像データの外部送信禁止
  - 一時ファイル自動削除
  - OCR結果のログ出力制限（`--debug`時のみ）
