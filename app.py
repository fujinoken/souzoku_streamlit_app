
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


APP_TITLE = "相続関係説明図ジェネレーター Ver2.5"
DB_PATH = "souzoku_cases.db"
BG = "#FFF4CF"
LINE = "#222222"

st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded"
)

PERSON_COLS = ["続柄", "氏名", "状態", "生年月日", "死亡日", "最後の本籍", "住所", "相続状況", "相続分", "備考"]
DESC_COLS = ["親", "続柄", "氏名", "状態", "生年月日", "死亡日", "最後の本籍", "住所", "相続状況", "相続分", "備考"]


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
def normalize_people_df(df, columns=PERSON_COLS):
    df = df.copy().fillna("")
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    return df[columns]


def normalize_desc_df(df, columns=DESC_COLS):
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

    if "descendants_df" not in st.session_state:
        st.session_state.descendants_df = pd.DataFrame([
            {"親": "長男", "続柄": "孫", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "代襲相続", "相続分": "", "備考": ""},
            {"親": "長女", "続柄": "孫", "氏名": "", "状態": "ご存命", "生年月日": "", "死亡日": "", "最後の本籍": "", "住所": "", "相続状況": "代襲相続", "相続分": "", "備考": ""},
        ], columns=DESC_COLS)
    else:
        st.session_state.descendants_df = normalize_desc_df(st.session_state.descendants_df)

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
        return pd.DataFrame(columns=PERSON_COLS)
    df = normalize_people_df(df).fillna("")
    mask = df.apply(lambda r: any(str(v).strip() for v in r.values), axis=1)
    return df[mask].reset_index(drop=True)


def clean_desc(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=DESC_COLS)
    df = normalize_desc_df(df).fillna("")
    mask = df.apply(lambda r: any(str(v).strip() for v in r.values), axis=1)
    return df[mask].reset_index(drop=True)


def text_value(v):
    if v is None:
        return ""
    return str(v).strip()


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
    rows = []
    for idx, row in df.iterrows():
        if is_active_heir_row(row):
            rows.append(idx)
    return rows


def active_descendant_rows_for_parent(parent_relation):
    df = clean_desc(st.session_state.descendants_df)
    idxs = []
    for idx, row in df.iterrows():
        if text_value(row.get("親", "")) == text_value(parent_relation) and is_active_heir_row(row):
            idxs.append(idx)
    return idxs


def get_descendant_groups():
    df = clean_desc(st.session_state.descendants_df)
    groups = {}
    for idx, row in df.iterrows():
        parent = text_value(row.get("親", ""))
        if not parent:
            continue
        if parent not in groups:
            groups[parent] = []
        groups[parent].append((idx, row))
    return groups


def calc_default_legal_shares():
    """
    Ver2.5:
    子の代襲相続に対応。
    基本ルール：
    - 生存している子はその子本人が相続
    - 死亡している子に孫がいる場合、その子の取得分を孫で均等割
    - 配偶者＋子系統：配偶者1/2、子系統全体1/2
    - 配偶者なし子系統のみ：子系統全体で1
    ※兄弟姉妹側の代襲、再代襲、半血兄弟姉妹等は手動修正。
    """
    spouse_exists = has_spouse()
    children = clean_people(st.session_state.children_df)
    descendants = clean_desc(st.session_state.descendants_df)
    parent_idxs = active_rows(st.session_state.parents_df)
    sibling_idxs = active_rows(st.session_state.siblings_df)

    result = {
        "spouse": "",
        "children": {},
        "parents": {},
        "siblings": {},
        "descendants": {},
        "pattern": "",
        "note": "",
    }

    def frac(num, den):
        import math
        if den == 0:
            return ""
        g = math.gcd(num, den)
        num //= g
        den //= g
        return "1" if den == 1 else f"{num}/{den}"

    def split_share(total_num, total_den, count):
        if count <= 0:
            return ""
        return frac(total_num, total_den * count)

    # 子系統の計算：生存子または死亡子＋代襲者が1系統
    child_branches = []
    child_by_relation = {}
    for idx, row in children.iterrows():
        relation = text_value(row.get("続柄", ""))
        if not relation:
            continue
        child_by_relation[relation] = (idx, row)
        status = text_value(row.get("状態", ""))
        inheritance_status = text_value(row.get("相続状況", ""))
        name = text_value(row.get("氏名", ""))
        desc_idxs = active_descendant_rows_for_parent(relation)

        if status == "死亡" and desc_idxs:
            child_branches.append({"type": "descendant", "child_idx": idx, "relation": relation, "desc_idxs": desc_idxs})
        elif is_active_heir_row(row):
            child_branches.append({"type": "child", "child_idx": idx, "relation": relation, "desc_idxs": []})
        # 死亡かつ孫なし、相続放棄、対象外は系統から除外

    if spouse_exists and child_branches:
        result["spouse"] = "1/2"
        branch_share_num, branch_share_den = 1, 2 * len(child_branches)
        for branch in child_branches:
            if branch["type"] == "child":
                result["children"][branch["child_idx"]] = frac(branch_share_num, branch_share_den)
            else:
                # 死亡した子本人は相続しない。孫にその子の相続分を均等配分
                desc_count = len(branch["desc_idxs"])
                for didx in branch["desc_idxs"]:
                    result["descendants"][didx] = frac(branch_share_num, branch_share_den * desc_count)
                result["children"][branch["child_idx"]] = "代襲者へ"
        result["pattern"] = "配偶者＋子系統（代襲相続含む）"
        result["note"] = "配偶者1/2、子系統全体1/2。死亡した子の取得分を孫で均等割。"
        return result

    if child_branches:
        branch_share_num, branch_share_den = 1, len(child_branches)
        for branch in child_branches:
            if branch["type"] == "child":
                result["children"][branch["child_idx"]] = frac(branch_share_num, branch_share_den)
            else:
                desc_count = len(branch["desc_idxs"])
                for didx in branch["desc_idxs"]:
                    result["descendants"][didx] = frac(branch_share_num, branch_share_den * desc_count)
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

    def apply_people_df(df_key, share_map):
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

    def apply_desc_df(df_key, share_map):
        df = normalize_desc_df(st.session_state[df_key])
        for idx, share in share_map.items():
            if idx in df.index:
                if overwrite or not text_value(df.at[idx, "相続分"]):
                    df.at[idx, "相続分"] = share
                if not text_value(df.at[idx, "相続状況"]):
                    df.at[idx, "相続状況"] = "代襲相続"
        st.session_state[df_key] = df

    apply_people_df("children_df", shares["children"])
    apply_people_df("parents_df", shares["parents"])
    apply_people_df("siblings_df", shares["siblings"])
    apply_desc_df("descendants_df", shares["descendants"])
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
# レイアウト計算
# =============================
def make_layout():
    parents = clean_people(st.session_state.parents_df)
    children = clean_people(st.session_state.children_df)
    siblings = clean_people(st.session_state.siblings_df)
    descendants = clean_desc(st.session_state.descendants_df)

    boxes = []
    lines = []

    W = 2100
    box_h = 220

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
        760, 390,
        w=390, h=box_h,
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
            760, 100,
            w=420, h=box_h,
            fill=BG,
            title_color="#C98300"
        ))
        lines.append(("spouse", "decedent", "double"))

    # 父母
    px, py = 65, 265
    parent_gap = 270
    for i, row in parents.iterrows():
        boxes.append(person_to_box(
            row,
            f"第二順位　被相続人等の{row.get('続柄','')}",
            f"parent_{i}",
            px, py + i * parent_gap,
            w=450, h=box_h
        ))
        lines.append((f"parent_{i}", "decedent", "single"))

    # 子
    cx = 1250
    child_start_y = 115
    child_gap = 300
    child_positions = {}
    for i, row in children.iterrows():
        relation = text_value(row.get("続柄", ""))
        y = child_start_y + i * child_gap
        box_id = f"child_{i}"
        child_positions[relation] = (box_id, cx, y)
        boxes.append(person_to_box(
            row,
            "第一順位　被相続人等の子",
            box_id,
            cx, y,
            w=450, h=box_h
        ))
        lines.append(("decedent", box_id, "single"))

    # 孫・代襲相続人
    dx = 1700
    desc_gap = 235
    desc_groups = get_descendant_groups()
    desc_counter = 0
    for parent_relation, members in desc_groups.items():
        parent_box_id, parent_x, parent_y = child_positions.get(parent_relation, (None, cx, child_start_y + desc_counter * desc_gap))
        for j, (orig_idx, row) in enumerate(members):
            y = parent_y + j * desc_gap
            box_id = f"desc_{desc_counter}_{j}_{orig_idx}"
            title_relation = row.get("続柄", "孫")
            boxes.append(person_to_box(
                row,
                f"代襲相続人　被相続人等の{title_relation}",
                box_id,
                dx, y,
                w=390, h=box_h,
                fill="#FFF9E6",
                title_color="#B86F00"
            ))
            if parent_box_id:
                lines.append((parent_box_id, box_id, "single"))
            else:
                lines.append(("decedent", box_id, "single"))
        desc_counter += len(members)

    # 兄弟姉妹
    sx, sy = 760, 760
    sibling_gap = 245
    for i, row in siblings.iterrows():
        boxes.append(person_to_box(
            row,
            f"第三順位　被相続人等の{row.get('続柄','兄弟姉妹')}",
            f"sibling_{i}",
            sx, sy + i * sibling_gap,
            w=420, h=box_h
        ))
        lines.append(("decedent", f"sibling_{i}", "single"))

    max_bottom = max([b["y"] + b["h"] for b in boxes] + [900])
    H = max(1350, max_bottom + 170)

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
    footer_x = 1280
    footer_y = H - 90
    parts.append(f'<text x="{footer_x}" y="{footer_y}" font-size="18" fill="#111" font-family="sans-serif">作成日：{svg_escape(creator.get("作成日",""))}</text>')
    parts.append(f'<text x="{footer_x}" y="{footer_y+28}" font-size="18" fill="#111" font-family="sans-serif">作成者：{svg_escape(creator.get("作成者氏名",""))}</text>')
    parts.append(f'<text x="{footer_x}" y="{footer_y+56}" font-size="18" fill="#111" font-family="sans-serif">住所：{svg_escape(creator.get("作成者住所",""))}</text>')

    parts.append('</svg>')
    return "\n".join(parts)


# =============================
# PDF出力
# =============================
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

    name = text_value(b.get("name", ""))
    name_size = calc_font_size(name, base=11.5, min_size=7, max_chars=7) * scale
    name_size = max(5.5, name_size)
    c.setFont("HeiseiKakuGo-W5", name_size)
    c.setFillColor(colors.black)

    name_lines = split_name_lines(name, max_chars=8)
    base_y = y + h - 36 * scale
    line_gap = name_size + 3 * scale
    for idx, line in enumerate(name_lines[:2]):
        c.drawString(x + 7 * scale, base_y - idx * line_gap, line)

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
        rows.extend(split_text_lines(f"本籍：{b.get('honseki','')}", max_chars=30, max_lines=2))

    if text_value(b.get("address", "")):
        rows.extend(split_text_lines(f"住所：{b.get('address','')}", max_chars=30, max_lines=2))

    for row in rows[:8]:
        c.drawString(x + 7 * scale, current_y, row)
        current_y -= 9.2 * scale


def create_pdf():
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))

    buffer = io.BytesIO()
    page_size = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=page_size)
    page_w, page_h = page_size

    W, H, boxes, lines = make_layout()
    margin = 18
    scale = min((page_w - margin * 2) / W, (page_h - margin * 2) / H)
    rendered_w = W * scale
    rendered_h = H * scale
    offset_x = (page_w - rendered_w) / 2
    offset_y = (page_h - rendered_h) / 2

    def tx(x):
        return offset_x + x * scale

    def ty(y):
        return offset_y + (H - y) * scale

    c.setLineWidth(max(0.7, 1.2 * scale))
    c.rect(tx(35), ty(80), 160 * scale, 28 * scale, fill=0, stroke=1)
    c.setFont("HeiseiKakuGo-W5", max(7, 14 * scale))
    c.drawString(tx(48), ty(58), "相続関係説明図")

    by_id = {b["id"]: b for b in boxes}
    c.setStrokeColor(colors.black)
    c.setLineWidth(max(0.4, 0.8 * scale))
    for a, b, kind in lines:
        if a not in by_id or b not in by_id:
            continue
        A, B = by_id[a], by_id[b]
        x1 = tx(A["x"] + A["w"] / 2)
        y1 = ty(A["y"] + A["h"] / 2)
        x2 = tx(B["x"] + B["w"] / 2)
        y2 = ty(B["y"] + B["h"] / 2)
        draw_double_or_single_pdf(c, x1, y1, x2, y2, kind, scale)

    for b in boxes:
        draw_box_pdf(c, b, scale, offset_x, offset_y, H)

    creator = st.session_state.creator
    footer_x = tx(1280)
    footer_y = ty(H - 40)
    c.setFont("HeiseiKakuGo-W5", max(5, 8 * scale))
    c.drawString(footer_x, footer_y + 28 * scale, f"作成日：{creator.get('作成日','')}")
    c.drawString(footer_x, footer_y + 14 * scale, f"作成者：{creator.get('作成者氏名','')}")
    c.drawString(footer_x, footer_y, f"住所：{creator.get('作成者住所','')}")

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
    footer_x = 1280
    footer_y = H - 90
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
        (case_name, created_at, updated_at, decedent, spouse, parents, children, siblings, descendants, creator)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        case_name,
        now,
        now,
        pd.Series(st.session_state.decedent).to_json(force_ascii=False),
        pd.Series(st.session_state.spouse).to_json(force_ascii=False),
        df_to_json(st.session_state.parents_df),
        df_to_json(st.session_state.children_df),
        df_to_json(st.session_state.siblings_df),
        df_to_json(st.session_state.descendants_df),
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

    desc_text = r["descendants"] if "descendants" in r and pd.notna(r["descendants"]) else ""
    st.session_state.descendants_df = json_to_df(desc_text, DESC_COLS)

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
        SET case_name=?, updated_at=?, decedent=?, spouse=?, parents=?, children=?, siblings=?, descendants=?, creator=?
        WHERE id=?
    """, (
        case_name,
        now,
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
st.caption("孫の代まで表示し、子の代襲相続を基本計算に組み込みました。")

menu = st.sidebar.radio(
    "メニュー",
    ["新規作成・編集", "保存データ管理", "出力プレビュー"],
    index=0
)

status_options = ["ご存命", "死亡", "相続放棄", "不明"]
inheritance_options = ["", "相続", "分割", "代襲相続", "代襲者へ", "相続放棄", "対象外", "未定"]

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
    st.info("代襲相続を使う場合は、死亡した子の状態を「死亡」にし、孫・代襲相続人の表で「親」にその子の続柄（例：長男）を入力してください。")

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

    st.markdown("#### 孫・代襲相続人")
    st.caption("親欄には、上の子の続柄と同じ文字を入れてください。例：長男、長女、二男。")
    child_relations = [""] + [text_value(v) for v in normalize_people_df(st.session_state.children_df)["続柄"].tolist() if text_value(v)]
    st.session_state.descendants_df = st.data_editor(
        normalize_desc_df(st.session_state.descendants_df),
        num_rows="dynamic",
        use_container_width=True,
        key="descendants_editor",
        column_config={
            "親": st.column_config.SelectboxColumn("親", options=child_relations),
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

    with st.expander("法定相続分・代襲相続の基本メモ"):
        st.markdown("""
| 相続人の組み合わせ | 配偶者 | 子・代襲相続人 | 直系尊属 | 兄弟姉妹 |
|---|---:|---:|---:|---:|
| 配偶者＋子系統 | 1/2 | 子系統全体で1/2 | - | - |
| 子系統のみ | - | 子系統で均等割 | - | - |
| 配偶者＋直系尊属 | 2/3 | - | 直系尊属全体で1/3 | - |
| 配偶者＋兄弟姉妹 | 3/4 | - | - | 兄弟姉妹全体で1/4 |
| 配偶者のみ | 1 | - | - | - |
""")
        st.caption("※子が死亡している場合、その子の取得分を孫が均等に代襲します。兄弟姉妹側の代襲、再代襲、半血兄弟姉妹、養子、欠格・廃除、特別受益、寄与分などは手動修正してください。")

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
    st.caption("孫・代襲相続人は、該当する子の右側に表示します。PDF／PNGでも出力されます。")
    W, H, _, _ = make_layout()
    svg = render_svg()
    preview_height = min(max(820, int(H * 0.65)), 1200)
    st.components.v1.html(svg, height=preview_height, scrolling=True)

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

st.sidebar.caption("Ver2.5：孫の代／子の代襲相続対応")
