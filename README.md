# 相続関係説明図ジェネレーター Ver2.6

## Ver2.6 修正点

- アプリ起動時は入力項目を空欄スタート
- 「入力をクリア」ボタンを追加
- 保存データ管理で検索可能
  - 案件名
  - 被相続人名
  - ID
- 保存データの読込
- 保存データの案件名更新
- 現在の入力内容で上書き更新
- 削除確認つき削除
- Ver2.5の孫・代襲相続機能は継続

## 起動方法

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud

Main file path は `app.py` です。
