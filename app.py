
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


APP_TITLE = "相続関係説明図ジェネレーター Ver2.6"
DB_PATH = "souzoku_cases.db"
BG = "#FFF4CF"
LINE = "#222222"

PERSON_COLS = ["続柄", "氏名", "状態", "生年月日", "死亡日", "最後の本籍", "住所", "相続状況", "相続分", "備考"]
DESC_COLS = ["親", "続柄", "氏名", "状態", "生年月日", "死亡日", "最後の本籍", "住所", "相続状況", "相続分", "備考"]

st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")


# =============================
# 初期データ
# =============================
def blank_decedent():
    return {"氏名": "", "生年月日": "", "死亡日": "", "最後の本籍": "", "最後の住所": "", "備考": ""}


def blank_spouse():
    return {
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


def default_people_df(kind):
    if kind == "parents":
        rows = [
            {"続柄": "父", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
            {"続柄": "母", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
        ]
    elif kind == "children":
        rows = [
            {"続柄": "長男", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
            {"続柄": "長女", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
            {"続柄": "二男", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
        ]
    else:
        rows = [
            {"続柄": "兄", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
            {"続柄": "姉", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
            {"続柄": "弟", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "", "相続分": "", "備考": ""},
        ]
    return pd.DataFrame(rows, columns=PERSON_COLS)


def default_desc_df():
    return pd.DataFrame([
        {"親": "", "続柄": "孫", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "代襲相続", "相続分": "", "備考": ""},
    ], columns=DESC_COLS)


def reset_input_state():
    st.session_state.case_id = None
    st.session_state.case_name = ""
    st.session_state.decedent = blank_decedent()
    st.session_state.spouse = blank_spouse()
    st.session_state.parents_df = default_people_df("parents")
    st.session_state.children_df = default_people_df("children")
    st.session_state.siblings_df = default_people_df("siblings")
    st.session_state.descendants_df = default_desc_df()
    st.session_state.creator = {"作成日": datetime.now().strftime("%Y-%m-%d"), "作成者氏名": "", "作成者住所": ""}


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
            descendants TEXT,
            creator TEXT
        )
    """)
    cur.execute("PRAGMA table_info(cases)")
    cols = [r[1] for r in cur.fetchall()]
    for col in ["creator", "descendants"]:
        if col not in cols:
            cur.execute(f"ALTER TABLE cases ADD COLUMN {col} TEXT")
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
        return df[columns].fillna("")
    except Exception:
        return pd.DataFrame(columns=columns)


def json_to_series_dict(text, default):
    try:
        d = pd.read_json(io.StringIO(text), typ="series").fillna("").to_dict()
        out = default.copy()
        out.update(d)
        return out
    except Exception:
        return default.copy()


def normalize_people_df(df):
    df = df.copy().fillna("")
    for c in PERSON_COLS:
        if c not in df.columns:
            df[c] = ""
    return df[PERSON_COLS]


def normalize_desc_df(df):
    df = df.copy().fillna("")
    for c in DESC_COLS:
        if c not in df.columns:
            df[c] = ""
    return df[DESC_COLS]


init_db()

# アプリ起動時は必ず空の入力状態から開始
if "app_initialized_v26" not in st.session_state:
    reset_input_state()
    st.session_state.app_initialized_v26 = True


# =============================
# 共通
# =============================
def text_value(v):
    return "" if v is None else str(v).strip()


def clean_people(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=PERSON_COLS)
    df = normalize_people_df(df)
    mask = df.apply(lambda r: any(text_value(v) for v in r.values), axis=1)
    return df[mask].reset_index(drop=True)


def clean_desc(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=DESC_COLS)
    df = normalize_desc_df(df)
    mask = df.apply(lambda r: any(text_value(v) for v in r.values), axis=1)
    return df[mask].reset_index(drop=True)


def is_active_heir_row(row):
    status = text_value(row.get("状態", ""))
    inheritance_status = text_value(row.get("相続状況", ""))
    name = text_value(row.get("氏名", ""))
    if not name and inheritance_status not in ["相続", "分割", "未定", "代襲相続"]:
        return False
    if status in ["死亡", "相続放棄"]:
        return False
    if inheritance_status in ["相続放棄", "対象外"]:
        return False
    return True


def has_spouse():
    sp = st.session_state.spouse
    if not text_value(sp.get("氏名", "")):
        return False
    if text_value(sp.get("状態", "")) in ["死亡", "相続放棄"]:
        return False
    if text_value(sp.get("相続状況", "")) in ["相続放棄", "対象外"]:
        return False
    return True


def active_rows(df):
    df = clean_people(df)
    return [idx for idx, row in df.iterrows() if is_active_heir_row(row)]


def active_descendant_rows_for_parent(parent_relation):
    df = clean_desc(st.session_state.descendants_df)
    return [idx for idx, row in df.iterrows() if text_value(row.get("親", "")) == text_value(parent_relation) and is_active_heir_row(row)]


def get_descendant_groups():
    df = clean_desc(st.session_state.descendants_df)
    groups = {}
    for idx, row in df.iterrows():
        parent = text_value(row.get("親", ""))
        if not parent:
            continue
        groups.setdefault(parent, []).append((idx, row))
    return groups


def calc_default_legal_shares():
    spouse_exists = has_spouse()
    children = clean_people(st.session_state.children_df)
    parent_idxs = active_rows(st.session_state.parents_df)
    sibling_idxs = active_rows(st.session_state.siblings_df)

    result = {"spouse": "", "children": {}, "parents": {}, "siblings": {}, "descendants": {}, "pattern": "", "note": ""}

    def frac(num, den):
        import math
        if den == 0:
            return ""
        g = math.gcd(num, den)
        num //= g
        den //= g
        return "1" if den == 1 else f"{num}/{den}"

    def split_share(total_num, total_den, count):
        return "" if count <= 0 else frac(total_num, total_den * count)

    child_branches = []
    for idx, row in children.iterrows():
        relation = text_value(row.get("続柄", ""))
        if not relation:
            continue
        status = text_value(row.get("状態", ""))
        desc_idxs = active_descendant_rows_for_parent(relation)
        if status == "死亡" and desc_idxs:
            child_branches.append({"type": "descendant", "child_idx": idx, "relation": relation, "desc_idxs": desc_idxs})
        elif is_active_heir_row(row):
            child_branches.append({"type": "child", "child_idx": idx, "relation": relation, "desc_idxs": []})

    if spouse_exists and child_branches:
        result["spouse"] = "1/2"
        branch_den = 2 * len(child_branches)
        for branch in child_branches:
            if branch["type"] == "child":
                result["children"][branch["child_idx"]] = frac(1, branch_den)
            else:
                for didx in branch["desc_idxs"]:
                    result["descendants"][didx] = frac(1, branch_den * len(branch["desc_idxs"]))
                result["children"][branch["child_idx"]] = "代襲者へ"
        result["pattern"] = "配偶者＋子系統（代襲相続含む）"
        result["note"] = "配偶者1/2、子系統全体1/2。死亡した子の取得分を孫で均等割。"
        return result

    if child_branches:
        branch_den = len(child_branches)
        for branch in child_branches:
            if branch["type"] == "child":
                result["children"][branch["child_idx"]] = frac(1, branch_den)
            else:
                for didx in branch["desc_idxs"]:
                    result["descendants"][didx] = frac(1, branch_den * len(branch["desc_idxs"]))
                result["children"][branch["child_idx"]] = "代襲者へ"
        result["pattern"] = "子系統のみ（代襲相続含む）"
        result["note"] = "子系統で均等割。死亡した子の取得分を孫で均等割。"
        return result

    if spouse_exists and parent_idxs:
        result["spouse"] = "2/3"
        for idx in parent_idxs:
            result["parents"][idx] = split_share(1, 3, len(parent_idxs))
        result["pattern"] = "配偶者＋直系尊属"
        result["note"] = "配偶者2/3、直系尊属全体1/3を人数で均等割"
        return result

    if spouse_exists and sibling_idxs:
        result["spouse"] = "3/4"
        for idx in sibling_idxs:
            result["siblings"][idx] = split_share(1, 4, len(sibling_idxs))
        result["pattern"] = "配偶者＋兄弟姉妹"
        result["note"] = "配偶者3/4、兄弟姉妹全体1/4を人数で均等割"
        return result

    if spouse_exists:
        result["spouse"] = "1"
        result["pattern"] = "配偶者のみ"
        result["note"] = "配偶者が全部相続"
        return result

    if parent_idxs:
        for idx in parent_idxs:
            result["parents"][idx] = split_share(1, 1, len(parent_idxs))
        result["pattern"] = "直系尊属のみ"
        result["note"] = "直系尊属で均等割"
        return result

    if sibling_idxs:
        for idx in sibling_idxs:
            result["siblings"][idx] = split_share(1, 1, len(sibling_idxs))
        result["pattern"] = "兄弟姉妹のみ"
        result["note"] = "兄弟姉妹で均等割"
        return result

    result["pattern"] = "相続人未入力"
    result["note"] = "氏名または相続状況が入力された相続人がありません。"
    return result


def apply_default_legal_shares(overwrite=True):
    shares = calc_default_legal_shares()
    if overwrite or not text_value(st.session_state.spouse.get("相続分", "")):
        st.session_state.spouse["相続分"] = shares["spouse"]

    def apply_people(df_key, share_map):
        df = normalize_people_df(st.session_state[df_key])
        for idx, share in share_map.items():
            if idx in df.index:
                if overwrite or not text_value(df.at[idx, "相続分"]):
                    df.at[idx, "相続分"] = share
                if share == "代襲者へ":
                    df.at[idx, "相続状況"] = "代襲者へ"
                elif not text_value(df.at[idx, "相続状況"]):
                    df.at[idx, "相続状況"] = "相続"
        st.session_state[df_key] = df

    def apply_desc(df_key, share_map):
        df = normalize_desc_df(st.session_state[df_key])
        for idx, share in share_map.items():
            if idx in df.index:
                if overwrite or not text_value(df.at[idx, "相続分"]):
                    df.at[idx, "相続分"] = share
                if not text_value(df.at[idx, "相続状況"]):
                    df.at[idx, "相続状況"] = "代襲相続"
        st.session_state[df_key] = df

    apply_people("children_df", shares["children"])
    apply_people("parents_df", shares["parents"])
    apply_people("siblings_df", shares["siblings"])
    apply_desc("descendants_df", shares["descendants"])
    return shares


def calc_font_size(text, base=24, min_size=12, max_chars=7):
    t = text_value(text)
    if not t:
        return base
    return base if len(t) <= max_chars else max(min_size, base - (len(t) - max_chars) * 2)


def split_text_lines(text, max_chars=16, max_lines=2):
    text = text_value(text)
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)][:max_lines] if text else []


def split_name_lines(name, max_chars=8):
    name = text_value(name)
    if len(name) <= max_chars:
        return [name] if name else [""]
    return [name[:max_chars], name[max_chars:max_chars * 2]]


def make_status_line(status, death):
    status = text_value(status)
    death = text_value(death)
    return f"□{status}　死亡日：{death}" if death else f"□{status}"


def person_to_box(row, title, box_id, x, y, w=390, h=220, fill=BG, title_color="#D58A00"):
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
# レイアウト・描画
# =============================
def make_layout():
    parents = clean_people(st.session_state.parents_df)
    children = clean_people(st.session_state.children_df)
    siblings = clean_people(st.session_state.siblings_df)
    descendants = clean_desc(st.session_state.descendants_df)

    boxes, lines = [], []
    W, box_h = 2100, 220

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
    boxes.append(person_to_box(decedent_row, "被相続人（亡くなった方）", "decedent", 760, 390, 390, box_h, "#FFFFFF", "#111111"))

    sp = st.session_state.spouse
    if any(text_value(sp.get(k, "")) for k in sp):
        spouse_row = {
            "氏名": sp.get("氏名", ""),
            "続柄": "配偶者",
            "状態": sp.get("状態", ""),
            "生年月日": sp.get("生年月日", ""),
            "死亡日": sp.get("死亡日", ""),
            "最後の本籍": sp.get("最後の本籍", ""),
            "住所": sp.get("住所", ""),
            "相続状況": sp.get("相続状況", ""),
            "相続分": sp.get("相続分", ""),
            "備考": sp.get("備考", ""),
        }
        boxes.append(person_to_box(spouse_row, "必ず相続人　配偶者", "spouse", 760, 100, 420, box_h, BG, "#C98300"))
        lines.append(("spouse", "decedent", "double"))

    for i, row in parents.iterrows():
        boxes.append(person_to_box(row, f"第二順位　被相続人等の{row.get('続柄','')}", f"parent_{i}", 65, 265 + i * 270, 450, box_h))
        lines.append((f"parent_{i}", "decedent", "single"))

    child_positions = {}
    for i, row in children.iterrows():
        relation = text_value(row.get("続柄", ""))
        y = 115 + i * 300
        box_id = f"child_{i}"
        child_positions[relation] = (box_id, 1250, y)
        boxes.append(person_to_box(row, "第一順位　被相続人等の子", box_id, 1250, y, 450, box_h))
        lines.append(("decedent", box_id, "single"))

    desc_groups = get_descendant_groups()
    for parent_relation, members in desc_groups.items():
        parent_box_id, parent_x, parent_y = child_positions.get(parent_relation, (None, 1250, 115))
        for j, (orig_idx, row) in enumerate(members):
            y = parent_y + j * 235
            box_id = f"desc_{parent_relation}_{j}_{orig_idx}"
            boxes.append(person_to_box(row, f"代襲相続人　被相続人等の{row.get('続柄','孫')}", box_id, 1700, y, 390, box_h, "#FFF9E6", "#B86F00"))
            lines.append((parent_box_id if parent_box_id else "decedent", box_id, "single"))

    for i, row in siblings.iterrows():
        boxes.append(person_to_box(row, f"第三順位　被相続人等の{row.get('続柄','兄弟姉妹')}", f"sibling_{i}", 760, 760 + i * 245, 420, box_h))
        lines.append(("decedent", f"sibling_{i}", "single"))

    max_bottom = max([b["y"] + b["h"] for b in boxes] + [900])
    H = max(1350, max_bottom + 170)
    return W, H, boxes, lines


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
        name_size = calc_font_size(b.get("name", ""), 25, 15, 7)
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{b["fill"]}" stroke="{LINE}" stroke-width="3"/>')
        parts.append(f'<text x="{x+16}" y="{y+34}" font-size="23" fill="{b["title_color"]}" font-weight="700" font-family="sans-serif">{svg_escape(b["title"])}</text>')
        for idx, line in enumerate(split_name_lines(b.get("name", ""), 8)[:2]):
            parts.append(f'<text x="{x+16}" y="{y+70 + idx*(name_size+4)}" font-size="{name_size}" fill="#111" font-weight="700" font-family="sans-serif">{svg_escape(line)}</text>')

        rows = [
            f"続柄：{b.get('relation','')}",
            f"生年月日：{b.get('birth','')}",
            make_status_line(b.get("status", ""), b.get("death", "")),
        ]
        if text_value(b.get("inheritance_status", "")) or text_value(b.get("share", "")):
            rows.append(f"遺産分割：{b.get('inheritance_status','')}　相続分：{b.get('share','')}")
        if text_value(b.get("honseki", "")):
            rows += split_text_lines(f"本籍：{b.get('honseki','')}", 22, 1)
        if text_value(b.get("address", "")):
            rows += split_text_lines(f"住所：{b.get('address','')}", 22, 1)

        line_y = y + 118
        for row in rows:
            size = 17 if line_y < y + 205 else 15
            parts.append(f'<text x="{x+16}" y="{line_y}" font-size="{size}" fill="#111" font-family="sans-serif">{svg_escape(row)}</text>')
            line_y += 23

    creator = st.session_state.creator
    footer_x, footer_y = 1280, H - 90
    parts.append(f'<text x="{footer_x}" y="{footer_y}" font-size="18" fill="#111" font-family="sans-serif">作成日：{svg_escape(creator.get("作成日",""))}</text>')
    parts.append(f'<text x="{footer_x}" y="{footer_y+28}" font-size="18" fill="#111" font-family="sans-serif">作成者：{svg_escape(creator.get("作成者氏名",""))}</text>')
    parts.append(f'<text x="{footer_x}" y="{footer_y+56}" font-size="18" fill="#111" font-family="sans-serif">住所：{svg_escape(creator.get("作成者住所",""))}</text>')
    parts.append('</svg>')
    return "\n".join(parts)


def draw_double_or_single_pdf(c, x1, y1, x2, y2, kind, scale=1):
    if kind == "double":
        offset = 2 * scale
        c.line(x1 - offset, y1, x2 - offset, y2)
        c.line(x1 + offset, y1, x2 + offset, y2)
    else:
        c.line(x1, y1, x2, y2)


def draw_box_pdf(c, b, scale, offset_x, offset_y, original_h):
    x = offset_x + b["x"] * scale
    y = offset_y + (original_h - b["y"] - b["h"]) * scale
    w = b["w"] * scale
    h = b["h"] * scale

    c.setFillColor(colors.HexColor(b["fill"]))
    c.setStrokeColor(colors.black)
    c.setLineWidth(max(0.6, 1.1 * scale))
    c.rect(x, y, w, h, fill=1, stroke=1)

    c.setFont("HeiseiKakuGo-W5", max(5.8, 9.5 * scale))
    c.setFillColor(colors.HexColor(b["title_color"]))
    c.drawString(x + 7 * scale, y + h - 16 * scale, str(b["title"] or ""))

    name_size = max(5.5, calc_font_size(b.get("name", ""), 11.5, 7, 7) * scale)
    c.setFont("HeiseiKakuGo-W5", name_size)
    c.setFillColor(colors.black)
    for idx, line in enumerate(split_name_lines(b.get("name", ""), 8)[:2]):
        c.drawString(x + 7 * scale, y + h - 36 * scale - idx * (name_size + 3 * scale), line)

    c.setFont("HeiseiKakuGo-W5", max(4.8, 6.7 * scale))
    current_y = y + h - 68 * scale
    rows = [
        f"続柄：{b.get('relation','')}",
        f"生年月日：{b.get('birth','')}",
        make_status_line(b.get("status", ""), b.get("death", "")),
    ]
    if text_value(b.get("inheritance_status", "")) or text_value(b.get("share", "")):
        rows.append(f"遺産分割：{b.get('inheritance_status','')}　相続分：{b.get('share','')}")
    if text_value(b.get("honseki", "")):
        rows.extend(split_text_lines(f"本籍：{b.get('honseki','')}", 30, 2))
    if text_value(b.get("address", "")):
        rows.extend(split_text_lines(f"住所：{b.get('address','')}", 30, 2))
    for row in rows[:8]:
        c.drawString(x + 7 * scale, current_y, row)
        current_y -= 9.2 * scale


def create_pdf():
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    buffer = io.BytesIO()
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    W, H, boxes, lines = make_layout()
    margin = 18
    scale = min((page_w - margin * 2) / W, (page_h - margin * 2) / H)
    offset_x = (page_w - W * scale) / 2
    offset_y = (page_h - H * scale) / 2

    def tx(x): return offset_x + x * scale
    def ty(y): return offset_y + (H - y) * scale

    c.setLineWidth(max(0.7, 1.2 * scale))
    c.rect(tx(35), ty(80), 160 * scale, 28 * scale, fill=0, stroke=1)
    c.setFont("HeiseiKakuGo-W5", max(7, 14 * scale))
    c.drawString(tx(48), ty(58), "相続関係説明図")

    by_id = {b["id"]: b for b in boxes}
    c.setStrokeColor(colors.black)
    c.setLineWidth(max(0.4, 0.8 * scale))
    for a, b, kind in lines:
        if a in by_id and b in by_id:
            A, B = by_id[a], by_id[b]
            draw_double_or_single_pdf(c, tx(A["x"] + A["w"]/2), ty(A["y"] + A["h"]/2), tx(B["x"] + B["w"]/2), ty(B["y"] + B["h"]/2), kind, scale)

    for b in boxes:
        draw_box_pdf(c, b, scale, offset_x, offset_y, H)

    creator = st.session_state.creator
    c.setFont("HeiseiKakuGo-W5", max(5, 8 * scale))
    c.drawString(tx(1280), ty(H - 40) + 28 * scale, f"作成日：{creator.get('作成日','')}")
    c.drawString(tx(1280), ty(H - 40) + 14 * scale, f"作成者：{creator.get('作成者氏名','')}")
    c.drawString(tx(1280), ty(H - 40), f"住所：{creator.get('作成者住所','')}")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


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
    font_title, font_box_title, font_small, font_tiny = find_jp_font(34), find_jp_font(23), find_jp_font(17), find_jp_font(15)

    draw.rectangle([35, 20, 375, 80], outline="black", width=4)
    draw.text((48, 30), "相続関係説明図", fill="black", font=font_title)
    by_id = {b["id"]: b for b in boxes}

    for a, b, kind in lines:
        if a in by_id and b in by_id:
            A, B = by_id[a], by_id[b]
            x1, y1 = A["x"] + A["w"]/2, A["y"] + A["h"]/2
            x2, y2 = B["x"] + B["w"]/2, B["y"] + B["h"]/2
            if kind == "double":
                draw.line([x1 - 5, y1, x2 - 5, y2], fill=LINE, width=3)
                draw.line([x1 + 5, y1, x2 + 5, y2], fill=LINE, width=3)
            else:
                draw.line([x1, y1, x2, y2], fill=LINE, width=3)

    for b in boxes:
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        draw.rectangle([x, y, x+w, y+h], fill=b["fill"], outline=LINE, width=3)
        draw.text((x+16, y+14), str(b["title"] or ""), fill=b["title_color"], font=font_box_title)
        name_size = calc_font_size(b.get("name", ""), 25, 15, 7)
        font_name = find_jp_font(name_size)
        for idx, line in enumerate(split_name_lines(b.get("name", ""), 8)[:2]):
            draw.text((x+16, y+52 + idx*(name_size+5)), line, fill="black", font=font_name)

        line_y = y + 110
        rows = [
            f"続柄：{b.get('relation','')}",
            f"生年月日：{b.get('birth','')}",
            make_status_line(b.get("status", ""), b.get("death", "")),
        ]
        if text_value(b.get("inheritance_status", "")) or text_value(b.get("share", "")):
            rows.append(f"遺産分割：{b.get('inheritance_status','')}　相続分：{b.get('share','')}")
        for row in rows:
            draw.text((x+16, line_y), row, fill="black", font=font_small)
            line_y += 24
        if text_value(b.get("honseki", "")):
            for row in split_text_lines(f"本籍：{b.get('honseki','')}", 24, 1):
                draw.text((x+16, line_y), row, fill="#333333", font=font_tiny)
                line_y += 22
        if text_value(b.get("address", "")):
            for row in split_text_lines(f"住所：{b.get('address','')}", 24, 1):
                draw.text((x+16, line_y), row, fill="#333333", font=font_tiny)
                line_y += 22

    creator = st.session_state.creator
    draw.text((1280, H-90), f"作成日：{creator.get('作成日','')}", fill="black", font=font_small)
    draw.text((1280, H-62), f"作成者：{creator.get('作成者氏名','')}", fill="black", font=font_small)
    draw.text((1280, H-34), f"住所：{creator.get('作成者住所','')}", fill="black", font=font_small)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


# =============================
# SQLite 操作
# =============================
def save_case(case_name):
    name = text_value(case_name) or "無題案件"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cases
        (case_name, created_at, updated_at, decedent, spouse, parents, children, siblings, descendants, creator)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name, now, now,
        pd.Series(st.session_state.decedent).to_json(force_ascii=False),
        pd.Series(st.session_state.spouse).to_json(force_ascii=False),
        df_to_json(st.session_state.parents_df),
        df_to_json(st.session_state.children_df),
        df_to_json(st.session_state.siblings_df),
        df_to_json(st.session_state.descendants_df),
        pd.Series(st.session_state.creator).to_json(force_ascii=False),
    ))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    st.session_state.case_id = new_id
    st.session_state.case_name = name
    return new_id


def update_case(case_id, case_name):
    if not case_id:
        return save_case(case_name)
    name = text_value(case_name) or "無題案件"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE cases
        SET case_name=?, updated_at=?, decedent=?, spouse=?, parents=?, children=?, siblings=?, descendants=?, creator=?
        WHERE id=?
    """, (
        name, now,
        pd.Series(st.session_state.decedent).to_json(force_ascii=False),
        pd.Series(st.session_state.spouse).to_json(force_ascii=False),
        df_to_json(st.session_state.parents_df),
        df_to_json(st.session_state.children_df),
        df_to_json(st.session_state.siblings_df),
        df_to_json(st.session_state.descendants_df),
        pd.Series(st.session_state.creator).to_json(force_ascii=False),
        case_id
    ))
    conn.commit()
    conn.close()
    st.session_state.case_name = name
    return case_id


def list_cases(keyword=""):
    conn = sqlite3.connect(DB_PATH)
    q = """
        SELECT id, case_name, created_at, updated_at, decedent
        FROM cases
        ORDER BY updated_at DESC, id DESC
    """
    df = pd.read_sql_query(q, conn)
    conn.close()

    if df.empty:
        return df

    def decedent_name(js):
        d = json_to_series_dict(js, blank_decedent())
        return d.get("氏名", "")

    df["被相続人"] = df["decedent"].apply(decedent_name)
    df = df.drop(columns=["decedent"])

    kw = text_value(keyword)
    if kw:
        mask = (
            df["case_name"].astype(str).str.contains(kw, case=False, na=False) |
            df["被相続人"].astype(str).str.contains(kw, case=False, na=False) |
            df["id"].astype(str).str.contains(kw, case=False, na=False)
        )
        df = df[mask]

    return df.reset_index(drop=True)


def load_case(case_id):
    conn = sqlite3.connect(DB_PATH)
    row = pd.read_sql_query("SELECT * FROM cases WHERE id = ?", conn, params=(case_id,))
    conn.close()
    if row.empty:
        return False

    r = row.iloc[0]
    st.session_state.case_id = int(r["id"])
    st.session_state.case_name = r["case_name"]
    st.session_state.decedent = json_to_series_dict(r["decedent"], blank_decedent())
    st.session_state.spouse = json_to_series_dict(r["spouse"], blank_spouse())
    st.session_state.parents_df = json_to_df(r["parents"], PERSON_COLS)
    st.session_state.children_df = json_to_df(r["children"], PERSON_COLS)
    st.session_state.siblings_df = json_to_df(r["siblings"], PERSON_COLS)
    desc_text = r["descendants"] if "descendants" in r and pd.notna(r["descendants"]) else ""
    st.session_state.descendants_df = json_to_df(desc_text, DESC_COLS)
    st.session_state.creator = json_to_series_dict(r.get("creator", ""), {"作成日": datetime.now().strftime("%Y-%m-%d"), "作成者氏名": "", "作成者住所": ""})
    return True


def delete_case(case_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM cases WHERE id = ?", (case_id,))
    conn.commit()
    conn.close()
    if st.session_state.get("case_id") == case_id:
        reset_input_state()


# =============================
# UI
# =============================
st.title(APP_TITLE)
st.caption("起動時は空欄スタート。保存データは検索・読込・更新・削除できます。")

menu = st.sidebar.radio("メニュー", ["新規作成・編集", "保存データ管理", "出力プレビュー"], index=0)
status_options = ["ご存命", "死亡", "相続放棄", "不明"]
inheritance_options = ["", "相続", "分割", "代襲相続", "代襲者へ", "相続放棄", "対象外", "未定"]

if menu == "新規作成・編集":
    st.subheader("1. 案件名")
    c_case1, c_case2 = st.columns([4, 1])
    with c_case1:
        st.session_state.case_name = st.text_input("案件名", st.session_state.case_name)
    with c_case2:
        if st.button("入力をクリア"):
            reset_input_state()
            st.rerun()

    if st.session_state.get("case_id"):
        st.info(f"編集中の保存ID：{st.session_state.case_id}")

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
        cur = st.session_state.spouse.get("状態", "ご存命")
        st.session_state.spouse["状態"] = st.selectbox("配偶者 状態", status_options, index=status_options.index(cur) if cur in status_options else 0)
    with c2:
        st.session_state.spouse["生年月日"] = st.text_input("配偶者 生年月日", st.session_state.spouse.get("生年月日", ""))
        st.session_state.spouse["死亡日"] = st.text_input("配偶者 死亡日", st.session_state.spouse.get("死亡日", ""))
    with c3:
        st.session_state.spouse["最後の本籍"] = st.text_input("配偶者 本籍", st.session_state.spouse.get("最後の本籍", ""))
        st.session_state.spouse["住所"] = st.text_input("配偶者 住所", st.session_state.spouse.get("住所", ""))
    with c4:
        cur = st.session_state.spouse.get("相続状況", "相続")
        st.session_state.spouse["相続状況"] = st.selectbox("配偶者 遺産分割状況", inheritance_options, index=inheritance_options.index(cur) if cur in inheritance_options else 1)
        st.session_state.spouse["相続分"] = st.text_input("配偶者 相続分", st.session_state.spouse.get("相続分", ""))

    st.subheader("4. 相続人の情報")
    st.info("代襲相続は、死亡した子の状態を「死亡」にし、孫・代襲相続人の「親」にその子の続柄を選びます。")

    st.markdown("#### 第二順位：父母")
    st.session_state.parents_df = st.data_editor(
        normalize_people_df(st.session_state.parents_df),
        num_rows="dynamic",
        use_container_width=True,
        key="parents_editor",
        column_config={"状態": st.column_config.SelectboxColumn("状態", options=status_options), "相続状況": st.column_config.SelectboxColumn("相続状況", options=inheritance_options)}
    )

    st.markdown("#### 第一順位：子")
    st.session_state.children_df = st.data_editor(
        normalize_people_df(st.session_state.children_df),
        num_rows="dynamic",
        use_container_width=True,
        key="children_editor",
        column_config={"状態": st.column_config.SelectboxColumn("状態", options=status_options), "相続状況": st.column_config.SelectboxColumn("相続状況", options=inheritance_options)}
    )

    st.markdown("#### 孫・代襲相続人")
    child_relations = [""] + [text_value(v) for v in normalize_people_df(st.session_state.children_df)["続柄"].tolist() if text_value(v)]
    st.session_state.descendants_df = st.data_editor(
        normalize_desc_df(st.session_state.descendants_df),
        num_rows="dynamic",
        use_container_width=True,
        key="descendants_editor",
        column_config={"親": st.column_config.SelectboxColumn("親", options=child_relations), "状態": st.column_config.SelectboxColumn("状態", options=status_options), "相続状況": st.column_config.SelectboxColumn("相続状況", options=inheritance_options)}
    )

    st.markdown("#### 第三順位：兄弟姉妹")
    st.session_state.siblings_df = st.data_editor(
        normalize_people_df(st.session_state.siblings_df),
        num_rows="dynamic",
        use_container_width=True,
        key="siblings_editor",
        column_config={"状態": st.column_config.SelectboxColumn("状態", options=status_options), "相続状況": st.column_config.SelectboxColumn("相続状況", options=inheritance_options)}
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

    st.subheader("6. 作成者情報")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.session_state.creator["作成日"] = st.text_input("作成日", st.session_state.creator.get("作成日", datetime.now().strftime("%Y-%m-%d")))
    with c2:
        st.session_state.creator["作成者氏名"] = st.text_input("作成者氏名", st.session_state.creator.get("作成者氏名", ""))
    with c3:
        st.session_state.creator["作成者住所"] = st.text_input("作成者住所", st.session_state.creator.get("作成者住所", ""))

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("新規保存", type="primary"):
            save_case(st.session_state.case_name)
            st.success("新規保存しました。")
    with c2:
        if st.button("上書き更新"):
            update_case(st.session_state.get("case_id"), st.session_state.case_name)
            st.success("更新しました。")
    with c3:
        st.download_button("PDF出力", data=create_pdf(), file_name=f"{st.session_state.case_name or '無題案件'}_相続関係説明図.pdf", mime="application/pdf")
    with c4:
        st.download_button("PNG出力", data=create_png(), file_name=f"{st.session_state.case_name or '無題案件'}_相続関係説明図.png", mime="image/png")

elif menu == "保存データ管理":
    st.subheader("保存データ管理")
    keyword = st.text_input("検索（案件名・被相続人名・ID）", "")
    cases = list_cases(keyword)

    if cases.empty:
        st.info("該当する保存データはありません。")
    else:
        st.dataframe(cases, use_container_width=True, hide_index=True)
        selected = st.selectbox("操作するIDを選択", cases["id"].tolist())
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("読込して編集"):
                if load_case(selected):
                    st.success("読み込みました。左メニューの新規作成・編集で編集できます。")
        with c2:
            new_name = st.text_input("案件名変更", "")
            if st.button("案件名のみ更新"):
                if text_value(new_name):
                    load_case(selected)
                    st.session_state.case_name = new_name
                    update_case(selected, new_name)
                    st.success("案件名を更新しました。")
        with c3:
            if st.button("現在の入力内容で上書き"):
                update_case(selected, st.session_state.case_name)
                st.success("選択IDを現在の入力内容で上書きしました。")
        with c4:
            confirm = st.checkbox("削除確認")
            if st.button("削除"):
                if confirm:
                    delete_case(selected)
                    st.warning("削除しました。")
                    st.rerun()
                else:
                    st.error("削除する場合は、削除確認にチェックしてください。")

elif menu == "出力プレビュー":
    st.subheader("出力プレビュー")
    W, H, _, _ = make_layout()
    st.components.v1.html(render_svg(), height=min(max(820, int(H * 0.65)), 1200), scrolling=True)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("PDFダウンロード", data=create_pdf(), file_name=f"{st.session_state.case_name or '無題案件'}_相続関係説明図.pdf", mime="application/pdf")
    with c2:
        st.download_button("PNGダウンロード", data=create_png(), file_name=f"{st.session_state.case_name or '無題案件'}_相続関係説明図.png", mime="image/png")

st.sidebar.caption("Ver2.6：起動時クリア／保存データ検索・更新・削除対応")
