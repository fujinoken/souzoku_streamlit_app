
import streamlit as st
import pandas as pd
import sqlite3
import io
import os
import html
from datetime import datetime

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

from PIL import Image, ImageDraw, ImageFont


APP_TITLE = "相続関係説明図ジェネレーター Ver2.1"
DB_PATH = "souzoku_cases.db"
BG = "#FFF4CF"
LINE = "#222222"


# =============================
# 基本設定
# =============================
st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded"
)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_name TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT,
            decedent TEXT,
            spouse TEXT,
            parents TEXT,
            children TEXT,
            siblings TEXT
        )
    """)
    conn.commit()
    conn.close()


def df_to_json(df):
    return df.fillna("").to_json(orient="records", force_ascii=False)


def json_to_df(text, columns):
    if not text:
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_json(io.StringIO(text), orient="records")
        for c in columns:
            if c not in df.columns:
                df[c] = ""
        return df[columns]
    except Exception:
        return pd.DataFrame(columns=columns)


def json_to_series_dict(text):
    try:
        return pd.read_json(io.StringIO(text), typ="series").fillna("").to_dict()
    except Exception:
        return {}


def init_session():
    if "decedent" not in st.session_state:
        st.session_state.decedent = {
            "氏名": "",
            "死亡日": "",
            "生年月日": "",
            "最後の住所": "",
            "本籍": "",
            "備考": "",
        }

    if "spouse" not in st.session_state:
        st.session_state.spouse = {
            "氏名": "",
            "状態": "ご存命",
            "生年月日": "",
            "死亡日": "",
            "相続分": "",
            "住所": "",
            "備考": "",
        }

    person_cols = ["続柄", "氏名", "状態", "生年月日", "死亡日", "相続分", "住所", "備考"]

    if "parents_df" not in st.session_state:
        st.session_state.parents_df = pd.DataFrame([
            {"続柄": "父", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "相続分": "", "住所": "", "備考": ""},
            {"続柄": "母", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "相続分": "", "住所": "", "備考": ""},
        ], columns=person_cols)

    if "children_df" not in st.session_state:
        st.session_state.children_df = pd.DataFrame([
            {"続柄": "長男", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "相続分": "", "住所": "", "備考": ""},
            {"続柄": "長女", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "相続分": "", "住所": "", "備考": ""},
            {"続柄": "二男", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "相続分": "", "住所": "", "備考": ""},
        ], columns=person_cols)

    if "siblings_df" not in st.session_state:
        st.session_state.siblings_df = pd.DataFrame([
            {"続柄": "兄", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "相続分": "", "住所": "", "備考": ""},
            {"続柄": "姉", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "相続分": "", "住所": "", "備考": ""},
            {"続柄": "弟", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "相続分": "", "住所": "", "備考": ""},
        ], columns=person_cols)

    if "case_name" not in st.session_state:
        st.session_state.case_name = "新規案件"


init_db()
init_session()


# =============================
# 共通ユーティリティ
# =============================
def clean_people(df):
    if df is None or df.empty:
        return df
    df = df.fillna("")
    mask = df.apply(lambda r: any(str(v).strip() for v in r.values), axis=1)
    return df[mask].reset_index(drop=True)


def text_value(v):
    if v is None:
        return ""
    return str(v).strip()


def calc_font_size(text, base=24, min_size=13, max_chars=7):
    """
    氏名が長い場合に自動で文字サイズを下げる。
    例：佐藤二郎 → 24
        佐藤二郎三郎 → 19
        とても長い氏名 → 13
    """
    t = text_value(text)
    if not t:
        return base
    length = len(t)
    if length <= max_chars:
        return base
    return max(min_size, base - (length - max_chars) * 2)


def split_name_lines(name, max_chars=8):
    """
    氏名が長い場合は2行に分ける。
    """
    name = text_value(name)
    if len(name) <= max_chars:
        return [name] if name else [""]
    return [name[:max_chars], name[max_chars:max_chars * 2]]


def make_status_line(status, death):
    status = text_value(status)
    death = text_value(death)
    if death:
        return f"□{status}　{death}没"
    return f"□{status}　年頃没"


# =============================
# レイアウト計算
# =============================
def make_layout():
    parents = clean_people(st.session_state.parents_df)
    children = clean_people(st.session_state.children_df)
    siblings = clean_people(st.session_state.siblings_df)

    boxes = []
    lines = []

    W, H = 1600, 1050

    boxes.append({
        "id": "decedent",
        "group": "center",
        "title": "被相続人（亡くなった方）",
        "name": st.session_state.decedent.get("氏名", ""),
        "status": "死亡",
        "birth": st.session_state.decedent.get("生年月日", ""),
        "death": st.session_state.decedent.get("死亡日", ""),
        "share": "",
        "x": 640, "y": 330, "w": 320, "h": 145,
        "fill": "#FFFFFF",
        "title_color": "#111111",
    })

    spouse = st.session_state.spouse
    if any(text_value(spouse.get(k, "")) for k in spouse):
        boxes.append({
            "id": "spouse",
            "group": "spouse",
            "title": "必ず相続人　配偶者",
            "name": spouse.get("氏名", ""),
            "status": spouse.get("状態", ""),
            "birth": spouse.get("生年月日", ""),
            "death": spouse.get("死亡日", ""),
            "share": spouse.get("相続分", ""),
            "x": 640, "y": 90, "w": 360, "h": 155,
            "fill": BG,
            "title_color": "#C98300",
        })
        lines.append(("spouse", "decedent", "vertical"))

    # 父母
    px, py = 70, 220
    for i, row in parents.iterrows():
        boxes.append({
            "id": f"parent_{i}",
            "group": "parents",
            "title": f"第二順位　被相続人等の{row.get('続柄','')}",
            "name": row.get("氏名", ""),
            "status": row.get("状態", ""),
            "birth": row.get("生年月日", ""),
            "death": row.get("死亡日", ""),
            "share": row.get("相続分", ""),
            "x": px, "y": py + i * 200, "w": 360, "h": 155,
            "fill": BG,
            "title_color": "#D58A00",
        })
        lines.append((f"parent_{i}", "decedent", "horizontal"))

    # 子
    child_count = max(len(children), 1)
    start_y = 105
    gap = min(220, max(160, int((H - 180) / max(child_count, 1))))
    cx = 1130
    for i, row in children.iterrows():
        boxes.append({
            "id": f"child_{i}",
            "group": "children",
            "title": "第一順位　被相続人等の子",
            "name": row.get("氏名", ""),
            "status": row.get("状態", ""),
            "birth": row.get("生年月日", ""),
            "death": row.get("死亡日", ""),
            "share": row.get("相続分", ""),
            "x": cx, "y": start_y + i * gap, "w": 390, "h": 155,
            "fill": BG,
            "title_color": "#D58A00",
        })
        lines.append(("decedent", f"child_{i}", "horizontal"))

    # 兄弟姉妹
    sx, sy = 640, 560
    sgap = 190
    for i, row in siblings.iterrows():
        boxes.append({
            "id": f"sibling_{i}",
            "group": "siblings",
            "title": f"第三順位　被相続人等の{row.get('続柄','兄弟姉妹')}",
            "name": row.get("氏名", ""),
            "status": row.get("状態", ""),
            "birth": row.get("生年月日", ""),
            "death": row.get("死亡日", ""),
            "share": row.get("相続分", ""),
            "x": sx, "y": sy + i * sgap, "w": 360, "h": 155,
            "fill": BG,
            "title_color": "#D58A00",
        })
        lines.append(("decedent", f"sibling_{i}", "vertical"))

    return W, H, boxes, lines


# =============================
# SVGプレビュー
# =============================
def svg_escape(s):
    return html.escape(str(s or ""))


def render_svg():
    W, H, boxes, lines = make_layout()
    by_id = {b["id"]: b for b in boxes}

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    parts.append('<rect width="100%" height="100%" fill="white"/>')
    parts.append('<rect x="35" y="20" width="300" height="55" fill="none" stroke="black" stroke-width="4"/>')
    parts.append('<text x="48" y="58" font-size="32" font-weight="700" font-family="sans-serif">相続関係説明図</text>')

    # 線
    for a, b, _kind in lines:
        if a not in by_id or b not in by_id:
            continue
        A, B = by_id[a], by_id[b]
        x1, y1 = A["x"] + A["w"] / 2, A["y"] + A["h"] / 2
        x2, y2 = B["x"] + B["w"] / 2, B["y"] + B["h"] / 2
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE}" stroke-width="3"/>')

    for b in boxes:
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        name = text_value(b.get("name", ""))
        name_size = calc_font_size(name, base=25, min_size=15, max_chars=7)
        name_lines = split_name_lines(name, max_chars=8)

        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{b["fill"]}" stroke="{LINE}" stroke-width="3"/>')
        parts.append(f'<text x="{x+16}" y="{y+34}" font-size="23" fill="{b["title_color"]}" font-weight="700" font-family="sans-serif">{svg_escape(b["title"])}</text>')

        # 氏名欄：タイトルと下部情報にかぶらない位置に固定
        name_y = y + 70
        for idx, line in enumerate(name_lines[:2]):
            parts.append(
                f'<text x="{x+16}" y="{name_y + idx * (name_size + 4)}" '
                f'font-size="{name_size}" fill="#111" font-weight="700" font-family="sans-serif">{svg_escape(line)}</text>'
            )

        # 生年月日は氏名より下、下部ステータスより上に配置
        if text_value(b.get("birth", "")):
            parts.append(f'<text x="{x+16}" y="{y+h-48}" font-size="17" fill="#333" font-family="sans-serif">生年月日：{svg_escape(b.get("birth", ""))}</text>')

        parts.append(f'<text x="{x+16}" y="{y+h-22}" font-size="18" fill="#111" font-family="sans-serif">{svg_escape(make_status_line(b.get("status", ""), b.get("death", "")))}</text>')

        if text_value(b.get("share", "")):
            parts.append(f'<text x="{x+w-125}" y="{y+h-22}" font-size="17" fill="#333" font-family="sans-serif">相続分：{svg_escape(b.get("share"))}</text>')

    parts.append('</svg>')
    return "\n".join(parts)


# =============================
# PDF出力
# =============================
def draw_box_pdf(c, b, scale_x, scale_y, page_h, margin):
    x = margin + b["x"] * scale_x
    y = page_h - margin - (b["y"] + b["h"]) * scale_y
    w = b["w"] * scale_x
    h = b["h"] * scale_y

    c.setFillColor(colors.HexColor(b["fill"]))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(x, y, w, h, fill=1, stroke=1)

    c.setFont("HeiseiKakuGo-W5", 10.5)
    c.setFillColor(colors.HexColor(b["title_color"]))
    c.drawString(x + 7, y + h - 18, str(b["title"] or ""))

    # 氏名：自動縮小＋最大2行
    name = text_value(b.get("name", ""))
    name_size = calc_font_size(name, base=12, min_size=7, max_chars=7)
    c.setFont("HeiseiKakuGo-W5", name_size)
    c.setFillColor(colors.black)

    name_lines = split_name_lines(name, max_chars=8)
    base_y = y + h - 40
    line_gap = name_size + 3
    for idx, line in enumerate(name_lines[:2]):
        c.drawString(x + 7, base_y - idx * line_gap, line)

    c.setFont("HeiseiKakuGo-W5", 7.8)
    if text_value(b.get("birth", "")):
        c.drawString(x + 7, y + 26, f"生年月日：{b.get('birth')}")

    c.setFont("HeiseiKakuGo-W5", 8)
    c.drawString(x + 7, y + 11, make_status_line(b.get("status", ""), b.get("death", "")))

    if text_value(b.get("share", "")):
        c.drawRightString(x + w - 7, y + 11, f"相続分：{b.get('share')}")


def create_pdf():
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))

    buffer = io.BytesIO()
    page_size = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=page_size)
    page_w, page_h = page_size

    W, H, boxes, lines = make_layout()
    margin = 24
    scale_x = (page_w - margin * 2) / W
    scale_y = (page_h - margin * 2) / H

    def tx(x):
        return margin + x * scale_x

    def ty(y):
        return page_h - margin - y * scale_y

    c.setLineWidth(1.4)
    c.rect(tx(35), ty(75), 150, 28, fill=0, stroke=1)
    c.setFont("HeiseiKakuGo-W5", 15)
    c.drawString(tx(48), ty(55), "相続関係説明図")

    by_id = {b["id"]: b for b in boxes}

    c.setStrokeColor(colors.black)
    c.setLineWidth(0.9)
    for a, b, _kind in lines:
        if a not in by_id or b not in by_id:
            continue
        A, B = by_id[a], by_id[b]
        x1 = tx(A["x"] + A["w"] / 2)
        y1 = ty(A["y"] + A["h"] / 2)
        x2 = tx(B["x"] + B["w"] / 2)
        y2 = ty(B["y"] + B["h"] / 2)
        c.line(x1, y1, x2, y2)

    for b in boxes:
        draw_box_pdf(c, b, scale_x, scale_y, page_h, margin)

    c.setFont("HeiseiKakuGo-W5", 8)
    c.drawRightString(page_w - 30, 18, f"作成日：{datetime.now().strftime('%Y-%m-%d')}")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# =============================
# PNG出力
# =============================
def find_jp_font(size=24):
    candidates = [
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/AppleGothic.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def create_png():
    W, H, boxes, lines = make_layout()
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    font_title = find_jp_font(32)
    font_box_title = find_jp_font(23)
    font_small = find_jp_font(18)

    draw.rectangle([35, 20, 335, 75], outline="black", width=4)
    draw.text((48, 28), "相続関係説明図", fill="black", font=font_title)

    by_id = {b["id"]: b for b in boxes}

    for a, b, _kind in lines:
        if a not in by_id or b not in by_id:
            continue
        A, B = by_id[a], by_id[b]
        x1, y1 = A["x"] + A["w"] / 2, A["y"] + A["h"] / 2
        x2, y2 = B["x"] + B["w"] / 2, B["y"] + B["h"] / 2
        draw.line([x1, y1, x2, y2], fill=LINE, width=3)

    for b in boxes:
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        draw.rectangle([x, y, x + w, y + h], fill=b["fill"], outline=LINE, width=3)
        draw.text((x + 16, y + 14), str(b["title"] or ""), fill=b["title_color"], font=font_box_title)

        name = text_value(b.get("name", ""))
        name_size = calc_font_size(name, base=25, min_size=15, max_chars=7)
        font_name = find_jp_font(name_size)
        name_lines = split_name_lines(name, max_chars=8)

        name_y = y + 52
        for idx, line in enumerate(name_lines[:2]):
            draw.text((x + 16, name_y + idx * (name_size + 5)), line, fill="black", font=font_name)

        if text_value(b.get("birth", "")):
            draw.text((x + 16, y + h - 55), f"生年月日：{b.get('birth')}", fill="#333333", font=font_small)

        draw.text((x + 16, y + h - 28), make_status_line(b.get("status", ""), b.get("death", "")), fill="black", font=font_small)

        if text_value(b.get("share", "")):
            draw.text((x + w - 140, y + h - 28), f"相続分：{b.get('share')}", fill="#333333", font=font_small)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


# =============================
# SQLite 保存・読込
# =============================
def save_case(case_name):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cases
        (case_name, created_at, updated_at, decedent, spouse, parents, children, siblings)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        case_name,
        now,
        now,
        pd.Series(st.session_state.decedent).to_json(force_ascii=False),
        pd.Series(st.session_state.spouse).to_json(force_ascii=False),
        df_to_json(st.session_state.parents_df),
        df_to_json(st.session_state.children_df),
        df_to_json(st.session_state.siblings_df),
    ))
    conn.commit()
    conn.close()


def list_cases():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT id, case_name, created_at, updated_at FROM cases ORDER BY updated_at DESC, id DESC",
        conn
    )
    conn.close()
    return df


def load_case(case_id):
    person_cols = ["続柄", "氏名", "状態", "生年月日", "死亡日", "相続分", "住所", "備考"]
    conn = sqlite3.connect(DB_PATH)
    row = pd.read_sql_query("SELECT * FROM cases WHERE id = ?", conn, params=(case_id,))
    conn.close()

    if row.empty:
        return False

    r = row.iloc[0]
    st.session_state.case_name = r["case_name"]
    st.session_state.decedent = json_to_series_dict(r["decedent"])
    st.session_state.spouse = json_to_series_dict(r["spouse"])
    st.session_state.parents_df = json_to_df(r["parents"], person_cols)
    st.session_state.children_df = json_to_df(r["children"], person_cols)
    st.session_state.siblings_df = json_to_df(r["siblings"], person_cols)
    return True


def update_case(case_id, case_name):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE cases
        SET case_name=?, updated_at=?, decedent=?, spouse=?, parents=?, children=?, siblings=?
        WHERE id=?
    """, (
        case_name,
        now,
        pd.Series(st.session_state.decedent).to_json(force_ascii=False),
        pd.Series(st.session_state.spouse).to_json(force_ascii=False),
        df_to_json(st.session_state.parents_df),
        df_to_json(st.session_state.children_df),
        df_to_json(st.session_state.siblings_df),
        case_id
    ))
    conn.commit()
    conn.close()


def delete_case(case_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM cases WHERE id = ?", (case_id,))
    conn.commit()
    conn.close()


# =============================
# UI
# =============================
st.title(APP_TITLE)
st.caption("氏名の自動縮小・2行表示に対応。項目表示とかぶりにくいレイアウトへ修正しています。")

menu = st.sidebar.radio(
    "メニュー",
    ["新規作成・編集", "保存データ管理", "出力プレビュー"],
    index=0
)

person_cols = ["続柄", "氏名", "状態", "生年月日", "死亡日", "相続分", "住所", "備考"]
status_options = ["ご存命", "死亡", "相続放棄", "不明"]

if menu == "新規作成・編集":
    st.subheader("1. 案件名")
    st.session_state.case_name = st.text_input("案件名", st.session_state.case_name)

    st.subheader("2. 被相続人")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.session_state.decedent["氏名"] = st.text_input("被相続人 氏名", st.session_state.decedent.get("氏名", ""))
        st.session_state.decedent["死亡日"] = st.text_input("死亡日", st.session_state.decedent.get("死亡日", ""), placeholder="例：2026年5月1日")
    with c2:
        st.session_state.decedent["生年月日"] = st.text_input("被相続人 生年月日", st.session_state.decedent.get("生年月日", ""), placeholder="例：昭和20年1月1日")
        st.session_state.decedent["最後の住所"] = st.text_input("最後の住所", st.session_state.decedent.get("最後の住所", ""))
    with c3:
        st.session_state.decedent["本籍"] = st.text_input("本籍", st.session_state.decedent.get("本籍", ""))
        st.session_state.decedent["備考"] = st.text_input("備考", st.session_state.decedent.get("備考", ""))

    st.subheader("3. 配偶者")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.session_state.spouse["氏名"] = st.text_input("配偶者 氏名", st.session_state.spouse.get("氏名", ""))
    with c2:
        current_status = st.session_state.spouse.get("状態", "ご存命")
        st.session_state.spouse["状態"] = st.selectbox(
            "配偶者 状態",
            status_options,
            index=status_options.index(current_status) if current_status in status_options else 0
        )
    with c3:
        st.session_state.spouse["生年月日"] = st.text_input("配偶者 生年月日", st.session_state.spouse.get("生年月日", ""))
        st.session_state.spouse["死亡日"] = st.text_input("配偶者 死亡日", st.session_state.spouse.get("死亡日", ""))
    with c4:
        st.session_state.spouse["相続分"] = st.text_input("配偶者 相続分", st.session_state.spouse.get("相続分", ""))
        st.session_state.spouse["住所"] = st.text_input("配偶者 住所", st.session_state.spouse.get("住所", ""))

    st.subheader("4. 相続人入力")
    st.info("氏名が長い場合は、出力時に自動で文字サイズを下げ、必要に応じて2行表示します。")

    st.markdown("#### 第二順位：父母")
    st.session_state.parents_df = st.data_editor(
        st.session_state.parents_df,
        num_rows="dynamic",
        use_container_width=True,
        key="parents_editor",
        column_config={
            "状態": st.column_config.SelectboxColumn("状態", options=status_options),
        }
    )

    st.markdown("#### 第一順位：子")
    st.session_state.children_df = st.data_editor(
        st.session_state.children_df,
        num_rows="dynamic",
        use_container_width=True,
        key="children_editor",
        column_config={
            "状態": st.column_config.SelectboxColumn("状態", options=status_options),
        }
    )

    st.markdown("#### 第三順位：兄弟姉妹")
    st.session_state.siblings_df = st.data_editor(
        st.session_state.siblings_df,
        num_rows="dynamic",
        use_container_width=True,
        key="siblings_editor",
        column_config={
            "状態": st.column_config.SelectboxColumn("状態", options=status_options),
        }
    )

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("新規保存", type="primary"):
            save_case(st.session_state.case_name)
            st.success("SQLiteに保存しました。")
    with c2:
        st.download_button(
            "PDF出力",
            data=create_pdf(),
            file_name=f"{st.session_state.case_name}_相続関係説明図.pdf",
            mime="application/pdf"
        )
    with c3:
        st.download_button(
            "PNG出力",
            data=create_png(),
            file_name=f"{st.session_state.case_name}_相続関係説明図.png",
            mime="image/png"
        )

elif menu == "保存データ管理":
    st.subheader("保存データ管理")
    cases = list_cases()

    if cases.empty:
        st.info("保存データはまだありません。")
    else:
        st.dataframe(cases, use_container_width=True, hide_index=True)
        ids = cases["id"].tolist()
        selected = st.selectbox("操作するIDを選択", ids)

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("読込"):
                if load_case(selected):
                    st.success("読み込みました。左メニューから編集できます。")
        with c2:
            if st.button("現在の内容で上書き更新"):
                update_case(selected, st.session_state.case_name)
                st.success("更新しました。")
        with c3:
            if st.button("削除", type="secondary"):
                delete_case(selected)
                st.warning("削除しました。画面を再読み込みしてください。")

elif menu == "出力プレビュー":
    st.subheader("出力プレビュー")
    st.caption("SVGで表示しています。PDF／PNGも同じ文字サイズ調整ロジックを使います。")
    svg = render_svg()
    st.components.v1.html(svg, height=780, scrolling=True)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "PDFダウンロード",
            data=create_pdf(),
            file_name=f"{st.session_state.case_name}_相続関係説明図.pdf",
            mime="application/pdf"
        )
    with c2:
        st.download_button(
            "PNGダウンロード",
            data=create_png(),
            file_name=f"{st.session_state.case_name}_相続関係説明図.png",
            mime="image/png"
        )

st.sidebar.caption("Ver2.1：氏名フォント自動調整／2行表示／重なり軽減")
