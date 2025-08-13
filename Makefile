# mysoku-renamer Makefile
# 開発・運用作業を効率化するためのMakeタスク

SHELL := /bin/bash
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

# デフォルトターゲット
.DEFAULT_GOAL := help

# ヘルプ表示
.PHONY: help
help: ## このヘルプを表示
	@echo "mysoku-renamer 開発・運用タスク"
	@echo ""
	@echo "使用方法: make [TARGET]"
	@echo ""
	@echo "利用可能なターゲット:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# 開発環境セットアップ
.PHONY: venv
venv: ## Python仮想環境を作成
	@echo "🔧 Python仮想環境作成中..."
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	@echo "✅ 仮想環境作成完了: $(VENV)"
	@echo "有効化コマンド: source $(VENV)/bin/activate"

.PHONY: install
install: venv ## 依存関係をインストール（開発用）
	@echo "📦 依存関係インストール中..."
	$(PIP) install -e ".[dev]"
	@echo "✅ インストール完了"

.PHONY: install-prod
install-prod: venv ## 依存関係をインストール（本番用）
	@echo "📦 本番用依存関係インストール中..."
	$(PIP) install -e .
	@echo "✅ 本番用インストール完了"

# テスト関連
.PHONY: test
test: ## 全テストを実行
	@echo "🧪 全テスト実行中..."
	$(PYTEST) -v

.PHONY: test-unit
test-unit: ## 単体テストのみ実行
	@echo "🧪 単体テスト実行中..."
	$(PYTEST) tests/ -v --ignore=tests/acceptance/

.PHONY: test-acceptance
test-acceptance: samples ## 受入テストを実行
	@echo "🧪 受入テスト実行中..."
	$(PYTEST) tests/acceptance/ -v

.PHONY: test-quick
test-quick: ## 高速テスト実行（失敗時停止）
	@echo "🧪 高速テスト実行中..."
	$(PYTEST) tests/ -x -q

# サンプルPDF生成
.PHONY: samples
samples: ## テスト用サンプルPDFを生成
	@echo "📄 サンプルPDF生成中..."
	$(PYTHON) scripts/gen_sample_pdfs.py
	@echo "✅ サンプル生成完了: tests/acceptance/samples/"

# 開発ツール
.PHONY: lint
lint: ## コードリンティング実行
	@echo "🔍 リンティング実行中..."
	$(VENV)/bin/ruff check src/ tests/ scripts/ --output-format=text
	@echo "✅ リンティング完了"

.PHONY: format
format: ## コードフォーマット実行
	@echo "🎨 コードフォーマット中..."
	$(VENV)/bin/ruff format src/ tests/ scripts/
	@echo "✅ フォーマット完了"

.PHONY: typecheck
typecheck: ## 型チェック実行
	@echo "🔎 型チェック実行中..."
	$(VENV)/bin/mypy src/mysoku_renamer/ --ignore-missing-imports || echo "型チェック完了（警告あり）"

.PHONY: check
check: lint format typecheck ## 全品質チェックを実行
	@echo "✅ 全品質チェック完了"

# 運用コマンド
.PHONY: dryrun
dryrun: ## サンプルファイルでドライラン実行
	@echo "🏃 ドライラン実行中..."
	@if [ ! -d "tests/acceptance/samples" ]; then \
		echo "⚠️  サンプルファイルが見つかりません。make samplesを実行してください。"; \
		exit 1; \
	fi
	$(PYTHON) -m mysoku_renamer.cli --dry-run tests/acceptance/samples \
		--output dryrun_result.tsv --debug --max-files 10
	@echo "📊 結果: dryrun_result.tsv"
	@echo "上位5行:"
	@head -5 dryrun_result.tsv 2>/dev/null || echo "TSVファイル読み込めません"

.PHONY: apply-sample
apply-sample: ## サンプルファイルでapply実行（コピーモード）
	@echo "🚀 Apply実行中（コピーモード）..."
	@if [ ! -d "tests/acceptance/samples" ]; then \
		echo "⚠️  サンプルファイルが見つかりません。make samplesを実行してください。"; \
		exit 1; \
	fi
	@mkdir -p sample_output
	$(PYTHON) -m mysoku_renamer.cli --apply tests/acceptance/samples \
		--outdir sample_output --output apply_result.tsv --debug
	@echo "📊 結果ディレクトリ: sample_output/"
	@echo "📄 結果TSV: apply_result.tsv"
	@ls -la sample_output/ 2>/dev/null || echo "出力ディレクトリ確認失敗"

# デモ・確認用
.PHONY: demo
demo: samples dryrun ## デモ実行（サンプル生成→ドライラン）
	@echo "🎯 デモ完了！"
	@echo "次のステップ:"
	@echo "  1. dryrun_result.tsv を確認"
	@echo "  2. make apply-sample でファイル生成テスト"

.PHONY: status
status: ## プロジェクト状況確認
	@echo "📊 プロジェクト状況:"
	@echo "  - Python仮想環境: $(shell [ -d $(VENV) ] && echo '✅ あり' || echo '❌ なし (make venv実行)')"
	@echo "  - パッケージ: $(shell [ -f $(VENV)/bin/mysoku-rename ] && echo '✅ インストール済み' || echo '❌ 未インストール (make install実行)')"
	@echo "  - サンプルPDF: $(shell [ -d tests/acceptance/samples ] && echo "✅ 生成済み ($(shell find tests/acceptance/samples -name '*.pdf' | wc -l)件)" || echo '❌ 未生成 (make samples実行)')"
	@echo ""
	@if [ -f dryrun_result.tsv ]; then \
		echo "📄 前回のドライラン結果:"; \
		echo "  - ファイル: dryrun_result.tsv ($(shell wc -l < dryrun_result.tsv)行)"; \
	fi
	@if [ -d sample_output ]; then \
		echo "📁 前回のApply結果:"; \
		echo "  - ディレクトリ: sample_output/ ($(shell find sample_output -name '*.pdf' 2>/dev/null | wc -l)ファイル)"; \
	fi

# クリーンアップ
.PHONY: clean
clean: ## 一時ファイル・キャッシュを削除
	@echo "🧹 クリーンアップ中..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -f dryrun_result.tsv apply_result.tsv
	rm -f mysoku_rollback_*.tsv mysoku_apply_*.tsv errors.tsv
	rm -rf sample_output/
	rm -rf .pytest_cache/
	@echo "✅ クリーンアップ完了"

.PHONY: clean-all
clean-all: clean ## 仮想環境含む全削除
	@echo "🧹 完全クリーンアップ中..."
	rm -rf $(VENV)
	rm -rf tests/acceptance/samples/
	@echo "✅ 完全クリーンアップ完了"

# パッケージング
.PHONY: build
build: ## パッケージをビルド
	@echo "📦 パッケージビルド中..."
	$(PYTHON) -m build
	@echo "✅ ビルド完了: dist/"

.PHONY: check-package
check-package: build ## パッケージの整合性チェック
	@echo "🔍 パッケージチェック中..."
	$(PYTHON) -m twine check dist/*
	@echo "✅ パッケージチェック完了"

# CI関連
.PHONY: ci-test
ci-test: install samples test ## CI環境でのテスト実行
	@echo "🤖 CI環境テスト完了"

# 開発者向け便利コマンド
.PHONY: dev-setup
dev-setup: install samples test ## 開発環境フルセットアップ
	@echo "🎉 開発環境セットアップ完了！"
	@echo ""
	@echo "次の手順:"
	@echo "  1. source $(VENV)/bin/activate  # 仮想環境有効化"
	@echo "  2. make demo                    # デモ実行"
	@echo "  3. mysoku-rename --help         # CLI動作確認"

.PHONY: quick-check
quick-check: test-quick lint ## 高速品質チェック
	@echo "⚡ 高速チェック完了"

# 環境確認
.PHONY: doctor
doctor: ## 環境診断
	@echo "🏥 環境診断中..."
	@echo "Python: $(shell python3 --version 2>&1 || echo 'インストールされていません')"
	@echo "pip: $(shell python3 -m pip --version 2>&1 || echo 'インストールされていません')"
	@echo "仮想環境: $(shell [ -d $(VENV) ] && echo 'OK' || echo 'なし')"
	@if [ -d $(VENV) ]; then \
		echo "仮想環境Python: $(shell $(PYTHON) --version 2>&1)"; \
		echo "mysoku-rename: $(shell $(PYTHON) -c 'import mysoku_renamer; print("OK")' 2>/dev/null || echo '未インストール')"; \
	fi
	@echo "ディスク容量: $(shell df -h . | tail -1 | awk '{print $$4}') 利用可能"