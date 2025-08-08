# mysoku-renamer Backend (FastAPI)

## 必要要件
- Python 3.11+
- Tesseract OCR / Poppler（pdf2image用）
  - macOS (Homebrew):
    ```bash
    brew install tesseract poppler
    ```
  - Linux (Debian/Ubuntu):
    ```bash
    sudo apt-get update && sudo apt-get install -y tesseract-ocr poppler-utils
    ```
- pip パッケージは `requirements.txt` に記載

## セットアップ
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Windowsは .venv\Scripts\activate
pip3 install -r requirements.txt
uvicorn main:app --reload --port 8000
```

- APIドキュメント（起動後）： http://localhost:8000/docs

## エンドポイント（MVP）
- `POST /api/upload` : PDF複数を受け取り、OCR→抽出→命名候補を生成
- `GET  /api/job/{job_id}` : 抽出結果の取得（プレビュー用）
- `POST /api/job/{job_id}/override` : プレビュー画面での手修正を反映
- `POST /api/job/{job_id}/finalize` : 命名を反映してZIP作成
- `GET  /api/job/{job_id}/download` : ZIPダウンロード

> 保存は行いません。`/tmp/mysoku_jobs` の一時領域に配置し、運用時はcron等で24h以上の古いジョブを削除してください。
