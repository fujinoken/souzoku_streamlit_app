# 相続関係説明図ジェネレーター Ver2.4

## Ver2.4 修正点

- 第三順位の兄弟姉妹が途中で切れる問題を修正
- 相続人が増えた場合にキャンバスの高さを自動拡張
- 画面プレビューで全体を縦スクロール表示
- PNGは全体サイズを動的に拡張して全員出力
- PDFはA4横1ページに全体を縮小して全員出力
- Ver2.3の法定相続分自動入力機能は継続

## 起動方法

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud

Main file path は `app.py` です。
