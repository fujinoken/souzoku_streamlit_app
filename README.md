# 相続関係説明図ジェネレーター Ver2.0

## 起動方法

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud 設定

- Repository: このファイル一式をアップロードしたGitHubリポジトリ
- Branch: main
- Main file path: app.py

## 主な機能

- session_state完全化
- 相続人入力の即時反映
- PDF正式出力
- PNG出力
- SQLite保存
- 保存データの読込・更新・削除
- 父母、配偶者、子、兄弟姉妹の自動レイアウト

## 注意

このアプリは相続関係説明図の作成補助ツールです。
法的判断、相続人確定、戸籍調査の代替ではありません。
実務使用時は戸籍等の確認資料と照合してください。
