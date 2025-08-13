#!/usr/bin/env python3
"""
サンプルPDF生成スクリプト

受入テスト用に売買・賃貸・不明の3種類のPDFファイルを生成する。
pypdfを使用してテキスト埋め込みPDFを作成。
"""

from pathlib import Path
import sys
from pypdf import PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import io


def register_japanese_font():
    """日本語フォントの登録"""
    try:
        # CJK フォントを登録
        pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
        return 'HeiseiKakuGo-W5'
    except:
        try:
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMincho-W3'))
            return 'HeiseiMincho-W3'
        except:
            # フォールバック：システムフォント
            return 'Helvetica'


def create_sell_pdf(output_path: Path):
    """売買物件のサンプルPDF作成"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    font_name = register_japanese_font()
    
    # ページ1
    c.setFont(font_name, 16)
    c.drawString(50, height - 80, "不動産売買物件情報")
    
    c.setFont(font_name, 12)
    y_pos = height - 120
    
    content = [
        "物件名：グランドタワー渋谷",
        "所在地：東京都渋谷区渋谷1-2-3",
        "販売価格：1億2,300万円",
        "築年月：2020年3月",
        "構造：鉄筋コンクリート造",
        "間取り：3LDK",
        "専有面積：85.50㎡",
        "管理費：30,000円",
        "修繕積立金：15,000円",
        "売買物件のため、仲介手数料が発生します。"
    ]
    
    for line in content:
        c.drawString(50, y_pos, line)
        y_pos -= 25
    
    c.showPage()
    c.save()
    
    # PDFとして保存
    buffer.seek(0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('wb') as f:
        f.write(buffer.getvalue())
    
    print(f"売買サンプルPDF作成: {output_path}")


def create_rent_pdf(output_path: Path):
    """賃貸物件のサンプルPDF作成"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    font_name = register_japanese_font()
    
    # ページ1
    c.setFont(font_name, 16)
    c.drawString(50, height - 80, "賃貸物件情報")
    
    c.setFont(font_name, 12)
    y_pos = height - 120
    
    content = [
        "物件名：レジデンス恵比寿",
        "所在地：東京都渋谷区恵比寿2-3-4", 
        "賃料：180,000円",
        "管理費：12,000円",
        "敷金：2ヶ月分",
        "礼金：1ヶ月分",
        "築年月：2018年6月",
        "構造：鉄骨造",
        "間取り：1LDK",
        "専有面積：45.80㎡",
        "家賃180,000円での賃貸募集中です。"
    ]
    
    for line in content:
        c.drawString(50, y_pos, line)
        y_pos -= 25
    
    c.showPage()
    c.save()
    
    # PDFとして保存
    buffer.seek(0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('wb') as f:
        f.write(buffer.getvalue())
    
    print(f"賃貸サンプルPDF作成: {output_path}")


def create_unknown_pdf(output_path: Path):
    """不明物件のサンプルPDF作成"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    font_name = register_japanese_font()
    
    # ページ1
    c.setFont(font_name, 16)
    c.drawString(50, height - 80, "物件資料")
    
    c.setFont(font_name, 12)
    y_pos = height - 120
    
    content = [
        "高級マンション",
        "立地：都心部",
        "設備：充実",
        "築年：新築",
        "構造：RC造",
        "その他詳細についてはお問い合わせください",
        "※価格等の詳細情報は別途ご案内いたします",
        "連絡先：03-1234-5678",
        "営業時間：9:00-18:00",
        "定休日：水曜日・日曜日"
    ]
    
    for line in content:
        c.drawString(50, y_pos, line)
        y_pos -= 25
    
    c.showPage()
    c.save()
    
    # PDFとして保存
    buffer.seek(0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('wb') as f:
        f.write(buffer.getvalue())
    
    print(f"不明サンプルPDF作成: {output_path}")


def main():
    """メイン処理"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    output_dir = project_root / "tests" / "acceptance" / "samples"
    
    print("受入テスト用サンプルPDF生成開始...")
    
    try:
        # 3種類のサンプルPDF作成
        create_sell_pdf(output_dir / "sell_sample.pdf")
        create_rent_pdf(output_dir / "rent_sample.pdf") 
        create_unknown_pdf(output_dir / "unknown_sample.pdf")
        
        print("\n✅ サンプルPDF生成完了")
        print(f"出力ディレクトリ: {output_dir}")
        
        # 生成したファイルの確認
        for pdf_file in output_dir.glob("*.pdf"):
            file_size = pdf_file.stat().st_size
            print(f"  - {pdf_file.name}: {file_size} bytes")
            
    except ImportError as e:
        print(f"❌ 必要なライブラリが不足しています: {e}")
        print("以下のコマンドでインストールしてください：")
        print("pip install reportlab")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ PDF生成エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()