
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


APP_TITLE = "相続関係説明図ジェネレーター Ver2.3"
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


# =============================
# DB
# =============================
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
            siblings TEXT,
            creator TEXT
        )
    """)

    cur.execute("PRAGMA table_info(cases)")
    cols = [r[1] for r in cur.fetchall()]
    if "creator" not in cols:
        cur.execute("ALTER TABLE cases ADD COLUMN creator TEXT")

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


# =============================
# session_state
# =============================
PERSON_COLS = ["続柄", "氏名", "状態", "生年月日", "死亡日", "最後の本籍", "住所", "相続状況", "相続分", "備考"]


def normalize_people_df(df, columns=PERSON_COLS):
    df = df.copy().fillna("")
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    return df[columns]


def init_session():
    if "decedent" not in st.session_state:
        st.session_state.decedent = {
            "氏名": "",
            "生年月日": "",
            "死亡日": "",
            "最後の本籍": "",
            "最後の住所": "",
            "備考": "",
        }

    if "本籍" in st.session_state.decedent and "最後の本籍" not in st.session_state.decedent:
        st.session_state.decedent["最後の本籍"] = st.session_state.decedent.get("本籍", "")
    if "最後の住所" not in st.session_state.decedent:
        st.session_state.decedent["最後の住所"] = ""

    if "spouse" not in st.session_state:
        st.session_state.spouse = {
            "氏名": "",
            "状態": "ご存命",
            "生年月日": "",
            "死亡日": "",
            "最後の本籍": "",
            "住所": "",
            "相続状況": "相続",
            "相続分": "",
            "備考": "",
        }

    for k in ["最後の本籍", "住所", "相続状況", "相続分", "備考"]:
        if k not in st.session_state.spouse:
            st.session_state.spouse[k] = ""

    if "parents_df" not in st.session_state:
        st.session_state.parents_df = pd.DataFrame([
            {"続柄": "父", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
            {"続柄": "母", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
        ], columns=PERSON_COLS)
    else:
        st.session_state.parents_df = normalize_people_df(st.session_state.parents_df)

    if "children_df" not in st.session_state:
        st.session_state.children_df = pd.DataFrame([
            {"続柄": "長男", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "相続", "相続分": "", "備考": ""},
            {"続柄": "長女", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "相続", "相続分": "", "備考": ""},
            {"続柄": "二男", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "相続", "相続分": "", "備考": ""},
        ], columns=PERSON_COLS)
    else:
        st.session_state.children_df = normalize_people_df(st.session_state.children_df)

    if "siblings_df" not in st.session_state:
        st.session_state.siblings_df = pd.DataFrame([
            {"続柄": "兄", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
            {"続柄": "姉", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
            {"続柄": "弟", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
        ], columns=PERSON_COLS)
    else:
        st.session_state.siblings_df = normalize_people_df(st.session_state.siblings_df)

    if "creator" not in st.session_state:
        st.session_state.creator = {
            "作成日": datetime.now().strftime("%Y-%m-%d"),
            "作成者氏名": "",
            "作成者住所": "",
        }

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
    df = normalize_people_df(df).fillna("")
    mask = df.apply(lambda r: any(str(v).strip() for v in r.values), axis=1)
    return df[mask].reset_index(drop=True)


def text_value(v):
    if v is None:
        return ""
    return str(v).strip()


def is_active_heir_row(row):
    """
    基本の法定相続分計算対象。
    氏名が空欄でも、続柄だけ入っている初期行を「入力済み相続人」とみなすと誤計算になりやすいため、
    氏名がある行、または相続状況が明示された行を対象にする。
    死亡・相続放棄・対象外は除外。
    """
    status = text_value(row.get("状態", ""))
    inheritance_status = text_value(row.get("相続状況", ""))
    name = text_value(row.get("氏名", ""))

    if not name and inheritance_status not in ["相続", "分割", "未定"]:
        return False

    if status in ["死亡", "相続放棄"]:
        return False

    if inheritance_status in ["相続放棄", "対象外"]:
        return False

    return True


def has_spouse():
    sp = st.session_state.spouse
    name = text_value(sp.get("氏名", ""))
    inheritance_status = text_value(sp.get("相続状況", ""))
    status = text_value(sp.get("状態", ""))

    if not name:
        return False
    if status in ["死亡", "相続放棄"]:
        return False
    if inheritance_status in ["相続放棄", "対象外"]:
        return False
    return True


def active_rows(df):
    df = clean_people(df)
    if df is None or df.empty:
        return []
    rows = []
    for idx, row in df.iterrows():
        if is_active_heir_row(row):
            rows.append(idx)
    return rows


def calc_default_legal_shares():
    """
    民法900条の基本パターンに基づく簡易計算。
    - 配偶者＋子：配偶者1/2、子全体1/2を人数で均等割
    - 配偶者＋直系尊属：配偶者2/3、直系尊属全体1/3を人数で均等割
    - 配偶者＋兄弟姉妹：配偶者3/4、兄弟姉妹全体1/4を人数で均等割
    - 配偶者のみ：1
    - 子のみ／直系尊属のみ／兄弟姉妹のみ：人数で均等割
    ※代襲相続、半血兄弟姉妹、養子制限、特別受益等は手動修正前提。
    """
    spouse_exists = has_spouse()

    child_idxs = active_rows(st.session_state.children_df)
    parent_idxs = active_rows(st.session_state.parents_df)
    sibling_idxs = active_rows(st.session_state.siblings_df)

    result = {
        "spouse": "",
        "children": {},
        "parents": {},
        "siblings": {},
        "pattern": "",
        "note": "",
    }

    def each(total_num, total_den, count):
        if count <= 0:
            return ""
        den = total_den * count
        num = total_num
        # 約分
        import math
        g = math.gcd(num, den)
        num //= g
        den //= g
        return "1" if den == 1 else f"{num}/{den}"

    if spouse_exists and child_idxs:
        result["spouse"] = "1/2"
        for idx in child_idxs:
            result["children"][idx] = each(1, 2, len(child_idxs))
        result["pattern"] = "配偶者＋子"
        result["note"] = "配偶者1/2、子全体1/2を人数で均等割"

    elif spouse_exists and parent_idxs:
        result["spouse"] = "2/3"
        for idx in parent_idxs:
            result["parents"][idx] = each(1, 3, len(parent_idxs))
        result["pattern"] = "配偶者＋直系尊属"
        result["note"] = "配偶者2/3、直系尊属全体1/3を人数で均等割"

    elif spouse_exists and sibling_idxs:
        result["spouse"] = "3/4"
        for idx in sibling_idxs:
            result["siblings"][idx] = each(1, 4, len(sibling_idxs))
        result["pattern"] = "配偶者＋兄弟姉妹"
        result["note"] = "配偶者3/4、兄弟姉妹全体1/4を人数で均等割"

    elif spouse_exists:
        result["spouse"] = "1"
        result["pattern"] = "配偶者のみ"
        result["note"] = "配偶者が全部相続"

    elif child_idxs:
        for idx in child_idxs:
            result["children"][idx] = each(1, 1, len(child_idxs))
        result["pattern"] = "子のみ"
        result["note"] = "子で均等割"

    elif parent_idxs:
        for idx in parent_idxs:
            result["parents"][idx] = each(1, 1, len(parent_idxs))
        result["pattern"] = "直系尊属のみ"
        result["note"] = "直系尊属で均等割"

    elif sibling_idxs:
        for idx in sibling_idxs:
            result["siblings"][idx] = each(1, 1, len(sibling_idxs))
        result["pattern"] = "兄弟姉妹のみ"
        result["note"] = "兄弟姉妹で均等割"

    else:
        result["pattern"] = "相続人未入力"
        result["note"] = "氏名または相続状況が入力された相続人がありません。"

    return result


def apply_default_legal_shares(overwrite=True):
    shares = calc_default_legal_shares()

    if overwrite or not text_value(st.session_state.spouse.get("相続分", "")):
        st.session_state.spouse["相続分"] = shares["spouse"]

    def apply_df(df_key, share_map):
        df = normalize_people_df(st.session_state[df_key])
        for idx, share in share_map.items():
            if idx in df.index:
                if overwrite or not text_value(df.at[idx, "相続分"]):
                    df.at[idx, "相続分"] = share
                if not text_value(df.at[idx, "相続状況"]):
                    df.at[idx, "相続状況"] = "相続"
        st.session_state[df_key] = df

    apply_df("children_df", shares["children"])
    apply_df("parents_df", shares["parents"])
    apply_df("siblings_df", shares["siblings"])

    return shares


def calc_font_size(text, base=24, min_size=12, max_chars=7):
    t = text_value(text)
    if not t:
        return base
    length = len(t)
    if length <= max_chars:
        return base
    return max(min_size, base - (length - max_chars) * 2)


def split_text_lines(text, max_chars=16, max_lines=2):
    text = text_value(text)
    if not text:
        return []
    lines = []
    for i in range(0, len(text), max_chars):
        lines.append(text[i:i + max_chars])
        if len(lines) >= max_lines:
            break
    return lines


def split_name_lines(name, max_chars=8):
    name = text_value(name)
    if len(name) <= max_chars:
        return [name] if name else [""]
    return [name[:max_chars], name[max_chars:max_chars * 2]]


def make_status_line(status, death):
    status = text_value(status)
    death = text_value(death)
    if death:
        return f"□{status}　死亡日：{death}"
    return f"□{status}"


def person_to_box(row, title, box_id, x, y, w=390, h=205, fill=BG, title_color="#D58A00"):
    return {
        "id": box_id,
        "title": title,
        "name": row.get("氏名", ""),
        "relation": row.get("続柄", ""),
        "status": row.get("状態", ""),
        "birth": row.get("生年月日", ""),
        "death": row.get("死亡日", ""),
        "honseki": row.get("最後の本籍", ""),
        "address": row.get("住所", ""),
        "inheritance_status": row.get("相続状況", ""),
        "share": row.get("相続分", ""),
        "note": row.get("備考", ""),
        "x": x, "y": y, "w": w, "h": h,
        "fill": fill,
        "title_color": title_color,
    }


# =============================
# レイアウト計算
# =============================
def make_layout():
    parents = clean_people(st.session_state.parents_df)
    children = clean_people(st.session_state.children_df)
    siblings = clean_people(st.session_state.siblings_df)

    boxes = []
    lines = []

    W, H = 1800, 1250

    decedent_row = {
        "氏名": st.session_state.decedent.get("氏名", ""),
        "続柄": "被相続人",
        "状態": "死亡",
        "生年月日": st.session_state.decedent.get("生年月日", ""),
        "死亡日": st.session_state.decedent.get("死亡日", ""),
        "最後の本籍": st.session_state.decedent.get("最後の本籍", ""),
        "住所": st.session_state.decedent.get("最後の住所", ""),
        "相続状況": "",
        "相続分": "",
        "備考": st.session_state.decedent.get("備考", ""),
    }

    boxes.append(person_to_box(
        decedent_row,
        "被相続人（亡くなった方）",
        "decedent",
        710, 390,
        w=390, h=220,
        fill="#FFFFFF",
        title_color="#111111"
    ))

    spouse = st.session_state.spouse
    if any(text_value(spouse.get(k, "")) for k in spouse):
        spouse_row = {
            "氏名": spouse.get("氏名", ""),
            "続柄": "配偶者",
            "状態": spouse.get("状態", ""),
            "生年月日": spouse.get("生年月日", ""),
            "死亡日": spouse.get("死亡日", ""),
            "最後の本籍": spouse.get("最後の本籍", ""),
            "住所": spouse.get("住所", ""),
            "相続状況": spouse.get("相続状況", ""),
            "相続分": spouse.get("相続分", ""),
            "備考": spouse.get("備考", ""),
        }
        boxes.append(person_to_box(
            spouse_row,
            "必ず相続人　配偶者",
            "spouse",
            710, 100,
            w=420, h=220,
            fill=BG,
            title_color="#C98300"
        ))
        lines.append(("spouse", "decedent", "double"))

    # 父母
    px, py = 65, 265
    for i, row in parents.iterrows():
        boxes.append(person_to_box(
            row,
            f"第二順位　被相続人等の{row.get('続柄','')}",
            f"parent_{i}",
            px, py + i * 270,
            w=450, h=220
        ))
        lines.append((f"parent_{i}", "decedent", "single"))

    # 子
    child_count = max(len(children), 1)
    start_y = 115
    gap = min(260, max(215, int((H - 210) / max(child_count, 1))))
    cx = 1280
    for i, row in children.iterrows():
        boxes.append(person_to_box(
            row,
            "第一順位　被相続人等の子",
            f"child_{i}",
            cx, start_y + i * gap,
            w=450, h=220
        ))
        lines.append(("decedent", f"child_{i}", "single"))

    # 兄弟姉妹
    sx, sy = 710, 700
    sgap = 245
    for i, row in siblings.iterrows():
        boxes.append(person_to_box(
            row,
            f"第三順位　被相続人等の{row.get('続柄','兄弟姉妹')}",
            f"sibling_{i}",
            sx, sy + i * sgap,
            w=420, h=220
        ))
        lines.append(("decedent", f"sibling_{i}", "single"))

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
    parts.append('<rect x="35" y="20" width="340" height="60" fill="none" stroke="black" stroke-width="4"/>')
    parts.append('<text x="48" y="61" font-size="34" font-weight="700" font-family="sans-serif">相続関係説明図</text>')

    for a, b, kind in lines:
        if a not in by_id or b not in by_id:
            continue
        A, B = by_id[a], by_id[b]
        x1, y1 = A["x"] + A["w"] / 2, A["y"] + A["h"] / 2
        x2, y2 = B["x"] + B["w"] / 2, B["y"] + B["h"] / 2

        if kind == "double":
            parts.append(f'<line x1="{x1-5}" y1="{y1}" x2="{x2-5}" y2="{y2}" stroke="{LINE}" stroke-width="3"/>')
            parts.append(f'<line x1="{x1+5}" y1="{y1}" x2="{x2+5}" y2="{y2}" stroke="{LINE}" stroke-width="3"/>')
        else:
            parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE}" stroke-width="3"/>')

    for b in boxes:
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        name = text_value(b.get("name", ""))
        name_size = calc_font_size(name, base=25, min_size=15, max_chars=7)
        name_lines = split_name_lines(name, max_chars=8)

        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{b["fill"]}" stroke="{LINE}" stroke-width="3"/>')
        parts.append(f'<text x="{x+16}" y="{y+34}" font-size="23" fill="{b["title_color"]}" font-weight="700" font-family="sans-serif">{svg_escape(b["title"])}</text>')

        name_y = y + 70
        for idx, line in enumerate(name_lines[:2]):
            parts.append(
                f'<text x="{x+16}" y="{name_y + idx * (name_size + 4)}" '
                f'font-size="{name_size}" fill="#111" font-weight="700" font-family="sans-serif">{svg_escape(line)}</text>'
            )

        line_y = y + 118
        rows = [
            f"続柄：{b.get('relation','')}",
            f"生年月日：{b.get('birth','')}",
            make_status_line(b.get("status", ""), b.get("death", "")),
        ]

        if text_value(b.get("inheritance_status", "")) or text_value(b.get("share", "")):
            rows.append(f"遺産分割：{b.get('inheritance_status','')}　相続分：{b.get('share','')}")

        honseki_lines = split_text_lines(f"本籍：{b.get('honseki','')}", max_chars=22, max_lines=1) if text_value(b.get("honseki", "")) else []
        address_lines = split_text_lines(f"住所：{b.get('address','')}", max_chars=22, max_lines=1) if text_value(b.get("address", "")) else []

        for row in rows:
            parts.append(f'<text x="{x+16}" y="{line_y}" font-size="17" fill="#111" font-family="sans-serif">{svg_escape(row)}</text>')
            line_y += 23

        for row in honseki_lines + address_lines:
            parts.append(f'<text x="{x+16}" y="{line_y}" font-size="15" fill="#333" font-family="sans-serif">{svg_escape(row)}</text>')
            line_y += 21

    creator = st.session_state.creator
    footer_x = 1180
    footer_y = 1160
    parts.append(f'<text x="{footer_x}" y="{footer_y}" font-size="18" fill="#111" font-family="sans-serif">作成日：{svg_escape(creator.get("作成日",""))}</text>')
    parts.append(f'<text x="{footer_x}" y="{footer_y+28}" font-size="18" fill="#111" font-family="sans-serif">作成者：{svg_escape(creator.get("作成者氏名",""))}</text>')
    parts.append(f'<text x="{footer_x}" y="{footer_y+56}" font-size="18" fill="#111" font-family="sans-serif">住所：{svg_escape(creator.get("作成者住所",""))}</text>')

    parts.append('</svg>')
    return "\n".join(parts)


# =============================
# PDF出力
# =============================
def draw_double_or_single_pdf(c, x1, y1, x2, y2, kind):
    if kind == "double":
        c.line(x1 - 2, y1, x2 - 2, y2)
        c.line(x1 + 2, y1, x2 + 2, y2)
    else:
        c.line(x1, y1, x2, y2)


def draw_box_pdf(c, b, scale_x, scale_y, page_h, margin):
    x = margin + b["x"] * scale_x
    y = page_h - margin - (b["y"] + b["h"]) * scale_y
    w = b["w"] * scale_x
    h = b["h"] * scale_y

    c.setFillColor(colors.HexColor(b["fill"]))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.1)
    c.rect(x, y, w, h, fill=1, stroke=1)

    c.setFont("HeiseiKakuGo-W5", 9.5)
    c.setFillColor(colors.HexColor(b["title_color"]))
    c.drawString(x + 7, y + h - 16, str(b["title"] or ""))

    name = text_value(b.get("name", ""))
    name_size = calc_font_size(name, base=11.5, min_size=7, max_chars=7)
    c.setFont("HeiseiKakuGo-W5", name_size)
    c.setFillColor(colors.black)

    name_lines = split_name_lines(name, max_chars=8)
    base_y = y + h - 36
    line_gap = name_size + 3
    for idx, line in enumerate(name_lines[:2]):
        c.drawString(x + 7, base_y - idx * line_gap, line)

    c.setFont("HeiseiKakuGo-W5", 6.7)
    current_y = y + h - 68

    rows = [
        f"続柄：{b.get('relation','')}",
        f"生年月日：{b.get('birth','')}",
        make_status_line(b.get("status", ""), b.get("death", "")),
    ]

    if text_value(b.get("inheritance_status", "")) or text_value(b.get("share", "")):
        rows.append(f"遺産分割：{b.get('inheritance_status','')}　相続分：{b.get('share','')}")

    if text_value(b.get("honseki", "")):
        rows.extend(split_text_lines(f"本籍：{b.get('honseki','')}", max_chars=30, max_lines=2))

    if text_value(b.get("address", "")):
        rows.extend(split_text_lines(f"住所：{b.get('address','')}", max_chars=30, max_lines=2))

    for row in rows[:8]:
        c.drawString(x + 7, current_y, row)
        current_y -= 9.2


def create_pdf():
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))

    buffer = io.BytesIO()
    page_size = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=page_size)
    page_w, page_h = page_size

    W, H, boxes, lines = make_layout()
    margin = 20
    scale_x = (page_w - margin * 2) / W
    scale_y = (page_h - margin * 2) / H

    def tx(x):
        return margin + x * scale_x

    def ty(y):
        return page_h - margin - y * scale_y

    c.setLineWidth(1.2)
    c.rect(tx(35), ty(80), 160, 28, fill=0, stroke=1)
    c.setFont("HeiseiKakuGo-W5", 14)
    c.drawString(tx(48), ty(58), "相続関係説明図")

    by_id = {b["id"]: b for b in boxes}

    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    for a, b, kind in lines:
        if a not in by_id or b not in by_id:
            continue
        A, B = by_id[a], by_id[b]
        x1 = tx(A["x"] + A["w"] / 2)
        y1 = ty(A["y"] + A["h"] / 2)
        x2 = tx(B["x"] + B["w"] / 2)
        y2 = ty(B["y"] + B["h"] / 2)
        draw_double_or_single_pdf(c, x1, y1, x2, y2, kind)

    for b in boxes:
        draw_box_pdf(c, b, scale_x, scale_y, page_h, margin)

    creator = st.session_state.creator
    c.setFont("HeiseiKakuGo-W5", 8)
    footer_y = 40
    c.drawString(page_w - 240, footer_y + 28, f"作成日：{creator.get('作成日','')}")
    c.drawString(page_w - 240, footer_y + 14, f"作成者：{creator.get('作成者氏名','')}")
    c.drawString(page_w - 240, footer_y, f"住所：{creator.get('作成者住所','')}")

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

    font_title = find_jp_font(34)
    font_box_title = find_jp_font(23)
    font_small = find_jp_font(17)
    font_tiny = find_jp_font(15)

    draw.rectangle([35, 20, 375, 80], outline="black", width=4)
    draw.text((48, 30), "相続関係説明図", fill="black", font=font_title)

    by_id = {b["id"]: b for b in boxes}

    for a, b, kind in lines:
        if a not in by_id or b not in by_id:
            continue
        A, B = by_id[a], by_id[b]
        x1, y1 = A["x"] + A["w"] / 2, A["y"] + A["h"] / 2
        x2, y2 = B["x"] + B["w"] / 2, B["y"] + B["h"] / 2

        if kind == "double":
            draw.line([x1 - 5, y1, x2 - 5, y2], fill=LINE, width=3)
            draw.line([x1 + 5, y1, x2 + 5, y2], fill=LINE, width=3)
        else:
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

        line_y = y + 110
        rows = [
            f"続柄：{b.get('relation','')}",
            f"生年月日：{b.get('birth','')}",
            make_status_line(b.get("status", ""), b.get("death", "")),
        ]

        if text_value(b.get("inheritance_status", "")) or text_value(b.get("share", "")):
            rows.append(f"遺産分割：{b.get('inheritance_status','')}　相続分：{b.get('share','')}")

        for row in rows:
            draw.text((x + 16, line_y), row, fill="black", font=font_small)
            line_y += 24

        if text_value(b.get("honseki", "")):
            for row in split_text_lines(f"本籍：{b.get('honseki','')}", max_chars=24, max_lines=1):
                draw.text((x + 16, line_y), row, fill="#333333", font=font_tiny)
                line_y += 22

        if text_value(b.get("address", "")):
            for row in split_text_lines(f"住所：{b.get('address','')}", max_chars=24, max_lines=1):
                draw.text((x + 16, line_y), row, fill="#333333", font=font_tiny)
                line_y += 22

    creator = st.session_state.creator
    footer_x = 1180
    footer_y = 1160
    draw.text((footer_x, footer_y), f"作成日：{creator.get('作成日','')}", fill="black", font=font_small)
    draw.text((footer_x, footer_y + 28), f"作成者：{creator.get('作成者氏名','')}", fill="black", font=font_small)
    draw.text((footer_x, footer_y + 56), f"住所：{creator.get('作成者住所','')}", fill="black", font=font_small)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


# =============================
# SQLite 操作
# =============================
def save_case(case_name):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cases
        (case_name, created_at, updated_at, decedent, spouse, parents, children, siblings, creator)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        case_name,
        now,
        now,
        pd.Series(st.session_state.decedent).to_json(force_ascii=False),
        pd.Series(st.session_state.spouse).to_json(force_ascii=False),
        df_to_json(st.session_state.parents_df),
        df_to_json(st.session_state.children_df),
        df_to_json(st.session_state.siblings_df),
        pd.Series(st.session_state.creator).to_json(force_ascii=False),
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
    conn = sqlite3.connect(DB_PATH)
    row = pd.read_sql_query("SELECT * FROM cases WHERE id = ?", conn, params=(case_id,))
    conn.close()

    if row.empty:
        return False

    r = row.iloc[0]
    st.session_state.case_name = r["case_name"]
    st.session_state.decedent = json_to_series_dict(r["decedent"])
    st.session_state.spouse = json_to_series_dict(r["spouse"])
    st.session_state.parents_df = json_to_df(r["parents"], PERSON_COLS)
    st.session_state.children_df = json_to_df(r["children"], PERSON_COLS)
    st.session_state.siblings_df = json_to_df(r["siblings"], PERSON_COLS)
    st.session_state.creator = json_to_series_dict(r.get("creator", "")) or {
        "作成日": datetime.now().strftime("%Y-%m-%d"),
        "作成者氏名": "",
        "作成者住所": "",
    }
    return True


def update_case(case_id, case_name):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE cases
        SET case_name=?, updated_at=?, decedent=?, spouse=?, parents=?, children=?, siblings=?, creator=?
        WHERE id=?
    """, (
        case_name,
        now,
        pd.Series(st.session_state.decedent).to_json(force_ascii=False),
        pd.Series(st.session_state.spouse).to_json(force_ascii=False),
        df_to_json(st.session_state.parents_df),
        df_to_json(st.session_state.children_df),
        df_to_json(st.session_state.siblings_df),
        pd.Series(st.session_state.creator).to_json(force_ascii=False),
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
st.caption("法定相続分の基本値を自動入力し、その後に任意で変更できます。")

menu = st.sidebar.radio(
    "メニュー",
    ["新規作成・編集", "保存データ管理", "出力プレビュー"],
    index=0
)

status_options = ["ご存命", "死亡", "相続放棄", "不明"]
inheritance_options = ["", "相続", "分割", "相続放棄", "対象外", "未定"]

if menu == "新規作成・編集":
    st.subheader("1. 案件名")
    st.session_state.case_name = st.text_input("案件名", st.session_state.case_name)

    st.subheader("2. 被相続人の情報")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.session_state.decedent["氏名"] = st.text_input("被相続人 氏名", st.session_state.decedent.get("氏名", ""))
        st.session_state.decedent["生年月日"] = st.text_input("被相続人 生年月日", st.session_state.decedent.get("生年月日", ""), placeholder="例：昭和20年1月1日")
    with c2:
        st.session_state.decedent["死亡日"] = st.text_input("死亡日", st.session_state.decedent.get("死亡日", ""), placeholder="例：令和6年5月1日")
        st.session_state.decedent["最後の本籍"] = st.text_input("最後の本籍", st.session_state.decedent.get("最後の本籍", ""))
    with c3:
        st.session_state.decedent["最後の住所"] = st.text_input("最後の住所", st.session_state.decedent.get("最後の住所", ""))
        st.session_state.decedent["備考"] = st.text_input("備考", st.session_state.decedent.get("備考", ""))

    st.subheader("3. 配偶者の情報")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.session_state.spouse["氏名"] = st.text_input("配偶者 氏名", st.session_state.spouse.get("氏名", ""))
        current_status = st.session_state.spouse.get("状態", "ご存命")
        st.session_state.spouse["状態"] = st.selectbox(
            "配偶者 状態",
            status_options,
            index=status_options.index(current_status) if current_status in status_options else 0
        )
    with c2:
        st.session_state.spouse["生年月日"] = st.text_input("配偶者 生年月日", st.session_state.spouse.get("生年月日", ""))
        st.session_state.spouse["死亡日"] = st.text_input("配偶者 死亡日", st.session_state.spouse.get("死亡日", ""))
    with c3:
        st.session_state.spouse["最後の本籍"] = st.text_input("配偶者 本籍", st.session_state.spouse.get("最後の本籍", ""))
        st.session_state.spouse["住所"] = st.text_input("配偶者 住所", st.session_state.spouse.get("住所", ""))
    with c4:
        current_inheritance = st.session_state.spouse.get("相続状況", "相続")
        st.session_state.spouse["相続状況"] = st.selectbox(
            "配偶者 遺産分割状況",
            inheritance_options,
            index=inheritance_options.index(current_inheritance) if current_inheritance in inheritance_options else 1
        )
        st.session_state.spouse["相続分"] = st.text_input("配偶者 相続分", st.session_state.spouse.get("相続分", ""))

    st.subheader("4. 相続人の情報")
    st.info("相続分は基本値を自動入力できます。入力後も各表の「相続分」欄で自由に変更できます。")

    st.markdown("#### 第二順位：父母")
    st.session_state.parents_df = st.data_editor(
        normalize_people_df(st.session_state.parents_df),
        num_rows="dynamic",
        use_container_width=True,
        key="parents_editor",
        column_config={
            "状態": st.column_config.SelectboxColumn("状態", options=status_options),
            "相続状況": st.column_config.SelectboxColumn("相続状況", options=inheritance_options),
        }
    )

    st.markdown("#### 第一順位：子")
    st.session_state.children_df = st.data_editor(
        normalize_people_df(st.session_state.children_df),
        num_rows="dynamic",
        use_container_width=True,
        key="children_editor",
        column_config={
            "状態": st.column_config.SelectboxColumn("状態", options=status_options),
            "相続状況": st.column_config.SelectboxColumn("相続状況", options=inheritance_options),
        }
    )

    st.markdown("#### 第三順位：兄弟姉妹")
    st.session_state.siblings_df = st.data_editor(
        normalize_people_df(st.session_state.siblings_df),
        num_rows="dynamic",
        use_container_width=True,
        key="siblings_editor",
        column_config={
            "状態": st.column_config.SelectboxColumn("状態", options=status_options),
            "相続状況": st.column_config.SelectboxColumn("相続状況", options=inheritance_options),
        }
    )

    st.subheader("5. 法定相続分の基本値")
    shares_preview = calc_default_legal_shares()
    st.caption(f"判定パターン：{shares_preview['pattern']} ／ {shares_preview['note']}")
    c_auto1, c_auto2 = st.columns(2)
    with c_auto1:
        if st.button("法定相続分の基本値を入力する（空欄のみ）"):
            applied = apply_default_legal_shares(overwrite=False)
            st.success(f"基本値を空欄へ入力しました：{applied['pattern']}")
            st.rerun()
    with c_auto2:
        if st.button("法定相続分の基本値で上書きする"):
            applied = apply_default_legal_shares(overwrite=True)
            st.warning(f"相続分を基本値で上書きしました：{applied['pattern']}")
            st.rerun()

    with st.expander("法定相続分の基本パターン表"):
        st.markdown("""
| 相続人の組み合わせ | 配偶者 | 子 | 直系尊属 | 兄弟姉妹 |
|---|---:|---:|---:|---:|
| 配偶者＋子 | 1/2 | 子全体で1/2 | - | - |
| 配偶者＋直系尊属 | 2/3 | - | 直系尊属全体で1/3 | - |
| 配偶者＋兄弟姉妹 | 3/4 | - | - | 兄弟姉妹全体で1/4 |
| 配偶者のみ | 1 | - | - | - |
| 子のみ | - | 均等割 | - | - |
| 直系尊属のみ | - | - | 均等割 | - |
| 兄弟姉妹のみ | - | - | - | 均等割 |
""")
        st.caption("※代襲相続、半血兄弟姉妹、養子、欠格・廃除、特別受益、寄与分などはこの簡易計算に含めず、手動修正してください。")

    st.subheader("6. 作成者情報")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.session_state.creator["作成日"] = st.text_input("作成日", st.session_state.creator.get("作成日", datetime.now().strftime("%Y-%m-%d")))
    with c2:
        st.session_state.creator["作成者氏名"] = st.text_input("作成者氏名", st.session_state.creator.get("作成者氏名", ""))
    with c3:
        st.session_state.creator["作成者住所"] = st.text_input("作成者住所", st.session_state.creator.get("作成者住所", ""))

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
    st.caption("配偶者との関係は二重線、その他の関係は一本線で表示します。")
    svg = render_svg()
    st.components.v1.html(svg, height=820, scrolling=True)

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

st.sidebar.caption("Ver2.3：法定相続分の基本値自動入力／任意修正対応")
