# 相続関係説明図ジェネレーター Ver3.2

## Ver3.2 修正点

- 相続人一覧PDF出力時の `NameError: getSampleStyleSheet` を修正
- ReportLab の必要 import を app.py 冒頭へ追加
- 相続人一覧PDF、遺産分割協議書PDF、関係図PDF、PNG、Excel出力に対応
- Ver3.1 の父母婚姻二重線・兄弟姉妹接続レイアウトを継続

## 修正対象

Streamlit Cloud で表示された以下のエラーを修正しています。

```text
NameError: name 'getSampleStyleSheet' is not defined
```

## 起動方法

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud

Main file path は `app.py` です。
