# TASKS

## マイソクPDF自動リネーム
- T1: 基盤構築・パッケージ化
  - Done: pyproject.toml設定、console_scripts: mysoku-rename
  - Done: 基本CLI引数解析 (--dry-run/--apply/--outdir/--strict/--debug/--logfile/--max-files)
  - Test: CLI起動、引数バリデーション、exit codes確認

- T2: PDF処理・テキスト抽出
  - Done: pypdf による基本テキスト抽出
  - Done: 抽出テキスト長 < 200文字時のOCR判定フラグ（T5準備）
  - Test: テキスト埋込PDFでの抽出動作、空/短文PDF検知

- T3: 物件情報解析・正規化
  - Done: 売買/賃貸判定ロジック
  - Done: 物件名抽出（優先順: ①「物件名」欄 → ②最大フォント行 → ③ノイズ最少候補）
  - Done: ノイズ語除去（号室/階数/部屋番号/掲載用/チラシ/新着/価格改定/更新日/No.、括弧付きマーク）
  - Done: 価格正規化（売買: N.X億円/N,NNN万円、賃貸: N,NNN円）
  - Test: 多様な価格表記、ノイズ語パターンでの単体テスト

- T4: 命名・ファイル管理
  - Done: 命名規則適用 (【売買】/【賃貸】/【その他】 prefix)
  - Done: ファイル衝突回避（連番 -1, -2...）
  - Done: 同ディレクトリリネーム vs --outdir コピー処理
  - Test: 重複ファイル、権限エラー時の動作確認

- T5: エラーハンドリング・ログ
  - Done: スキップ継続 vs --strict 即座終了
  - Done: errors.tsv 出力（抽出失敗ケース記録）
  - Done: INFO/DEBUG ログレベル、--logfile 対応
  - Test: 各種エラーパターンでの動作、ログ出力確認

- T6: ロールバック・TSV記録
  - Done: apply時の rollback_YYYYMMDD_HHMMSS.tsv 自動生成
  - Done: scripts/rollback_from_tsv.py 復元スクリプト
  - Test: ロールバックTSV形式、復元手順の動作確認

- T7: OCR統合（オプション・許可制）
  - Done: --ocr フラグでの tesseract (jpn,jpn_vert) 統合
  - Done: 抽出テキスト < 200文字時のフォールバック
  - Test: 画像PDFでの最低限精度、OCR無効時との比較

- T8: 受入テスト・最終検証
  - Done: 代表サンプル3種（売買/賃貸/不明）での end-to-end テスト
  - Done: dry-run と apply の結果整合性確認
  - Done: 最大500ファイル制限、進捗表示の動作確認
  - Test: 全受入条件の最終チェック
