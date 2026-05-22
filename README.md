# 相続関係説明図ジェネレーター Ver2.9

## Ver2.9 修正点

- 相続関係説明図のExcel出力に対応
- Excelブック内に以下のシートを作成
  - 相続関係説明図
  - 相続人一覧
  - 被相続人情報
  - 財産一覧
- 相続関係説明図シートには、現在の関係図を画像として貼り付け
- 印刷時にA4横1ページに収まる設定
- PDF／PNG／相続人一覧／遺産分割協議書機能は継続

## 起動方法

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud

Main file path は `app.py` です。
