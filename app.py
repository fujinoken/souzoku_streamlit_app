import json
from io import BytesIO
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

APP_TITLE = "相続関係説明図ジェネレーター Ver1.0"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CASE_FILE = DATA_DIR / "cases.json"

BG = "#FFF4CE"
LINE = "#222222"
RED = "#D84A3A"


def load_font(size=22, bold=False):
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def safe(v):
    return "" if v is None else str(v)


def normalize_people(people):
    out = []
    for p in people:
        if any(safe(p.get(k)).strip() for k in ["name", "relation", "birth", "death", "address", "note"]):
            out.append(p)
    return out


def load_cases():
    if CASE_FILE.exists():
        try:
            return json.loads(CASE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_cases(cases):
    CASE_FILE.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")


def text(draw, xy, s, font, fill=LINE):
    draw.text(xy, safe(s), font=font, fill=fill)


def box(draw, x, y, w, h, title, name="", sub="", label_color=LINE):
    draw.rectangle([x, y, x+w, y+h], fill=BG, outline=LINE, width=3)
    f_label = load_font(24, True)
    f_name = load_font(25, True)
    f_small = load_font(18)
    text(draw, (x+14, y+10), title, f_label, label_color)
    text(draw, (x+14, y+45), name, f_name, LINE)
    if sub:
        text(draw, (x+14, y+h-32), sub, f_small, LINE)


def person_sub(p):
    living = "ご存命" if p.get("living", True) else "死亡"
    birth = safe(p.get("birth"))
    death = safe(p.get("death"))
    parts = [living]
    if birth:
        parts.append(f"生:{birth}")
    if death:
        parts.append(f"没:{death}")
    if p.get("share"):
        parts.append(f"相続分:{p.get('share')}")
    return "　".join(parts)


def make_diagram(case):
    W, H = 1600, 1120
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f_title = load_font(36, True)
    f_mid = load_font(24, True)
    f_small = load_font(18)

    # Title
    d.rectangle([40, 35, 335, 95], outline=LINE, width=4)
    text(d, (55, 48), "相続関係説明図", f_title, LINE)

    dec = case.get("decedent", {})
    spouse = case.get("spouse", {})
    parents = normalize_people(case.get("parents", []))
    children = normalize_people(case.get("children", []))
    siblings = normalize_people(case.get("siblings", []))

    # Decedent center
    d.rectangle([610, 260, 990, 375], fill="white", outline=LINE, width=4)
    text(d, (635, 278), "被相続人（亡くなった方）", f_mid, LINE)
    text(d, (715, 320), dec.get("name", ""), load_font(26, True), LINE)
    death_line = f"死亡日：{safe(dec.get('death'))}" if dec.get("death") else ""
    text(d, (635, 348), death_line, f_small, LINE)

    # Spouse
    box(d, 610, 80, 420, 130, "必ず相続人", spouse.get("name", ""), person_sub(spouse), RED)
    text(d, (625, 118), "配偶者", load_font(26, True), LINE)
    d.line([800, 210, 800, 260], fill=LINE, width=3)

    # children right
    child_x = 1080
    child_y0 = 70
    child_h = 130
    gap = 105
    d.line([1000, 320, 1070, 320], fill=LINE, width=3)
    if children:
        d.line([1070, child_y0+70, 1070, min(child_y0+(len(children)-1)*(child_h+gap)+70, 1020)], fill=LINE, width=3)
    for i, ch in enumerate(children[:5]):
        y = child_y0 + i*(child_h+gap)
        box(d, child_x, y, 430, child_h, "第一順位", ch.get("name", ""), person_sub(ch), RED)
        text(d, (child_x+14, y+43), ch.get("relation", "被相続人等の子"), load_font(23, True), LINE)
        d.line([1070, y+70, child_x, y+70], fill=LINE, width=3)

    # parents left
    par_x = 80
    par_y = 190
    d.line([500, 320, 610, 320], fill=LINE, width=3)
    if parents:
        d.line([500, par_y+70, 500, par_y+70+(len(parents)-1)*150], fill=LINE, width=3)
    for i, p in enumerate(parents[:2]):
        y = par_y + i*150
        label = "第二順位" if i == 0 else ""
        relation = p.get("relation", "被相続人等の父母")
        box(d, par_x, y, 410, 125, label, p.get("name", ""), person_sub(p), RED if label else LINE)
        text(d, (par_x+14, y+42), relation, load_font(23, True), LINE)
        d.line([par_x+410, y+70, 500, y+70], fill=LINE, width=3)

    # siblings below center
    sib_x = 610
    sib_y0 = 560
    d.line([690, 375, 690, 1000], fill=LINE, width=3)
    for i, s in enumerate(siblings[:4]):
        y = sib_y0 + i*155
        box(d, sib_x, y, 420, 125, "第三順位" if i == 0 else "", s.get("name", ""), person_sub(s), RED if i == 0 else LINE)
        text(d, (sib_x+14, y+42), s.get("relation", "被相続人等の兄弟姉妹"), load_font(22, True), LINE)
        d.line([690, y+60, sib_x, y+60], fill=LINE, width=3)

    # Details and footer
    details = []
    if dec.get("birth"): details.append(f"被相続人生年月日：{dec.get('birth')}")
    if dec.get("last_address"): details.append(f"最後の住所：{dec.get('last_address')}")
    if dec.get("honseki"): details.append(f"本籍：{dec.get('honseki')}")
    if case.get("memo"): details.append(f"備考：{case.get('memo')}")
    y = 1000
    for line in details[:3]:
        text(d, (55, y), line, f_small, LINE)
        y += 28
    text(d, (1210, 1065), "※戸籍等の確認資料に基づき作成", f_small, LINE)
    return img


def image_to_pdf_bytes(img):
    buffer = BytesIO()
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    w, h = landscape(A4)
    img_buf = BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(img_buf), 20, 20, width=w-40, height=h-40, preserveAspectRatio=True, anchor="c")
    c.setFont("HeiseiKakuGo-W5", 8)
    c.drawRightString(w-20, 10, "相続関係説明図ジェネレーター Ver1.0")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def to_excel_bytes(case):
    bio = BytesIO()
    dec = case.get("decedent", {})
    summary = pd.DataFrame([
        {"区分":"被相続人", **dec},
        {"区分":"配偶者", **case.get("spouse", {})},
    ])
    people = []
    for category in ["parents", "children", "siblings"]:
        for p in normalize_people(case.get(category, [])):
            people.append({"分類": category, **p})
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        summary.to_excel(writer, index=False, sheet_name="基本情報")
        pd.DataFrame(people).to_excel(writer, index=False, sheet_name="相続人一覧")
    bio.seek(0)
    return bio.getvalue()


st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("被相続人・配偶者・相続人を入力し、A4横の相続関係説明図をPNG/PDF/Excelで出力します。")

with st.sidebar:
    st.header("メニュー")
    mode = st.radio("操作", ["新規作成", "保存データ管理"])
    st.info("Ver1.0：配偶者・子・父母・兄弟姉妹の基本形に対応")

if mode == "保存データ管理":
    cases = load_cases()
    st.subheader("保存データ管理")
    if not cases:
        st.warning("保存データはまだありません。")
    else:
        labels = [f"{i+1}. {c.get('case_name','無題')} / {c.get('decedent',{}).get('name','')}" for i,c in enumerate(cases)]
        idx = st.selectbox("確認するデータ", range(len(cases)), format_func=lambda i: labels[i])
        st.json(cases[idx], expanded=False)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("このデータを削除", type="secondary"):
                cases.pop(idx)
                save_cases(cases)
                st.success("削除しました。画面を再読み込みしてください。")
        with col2:
            st.download_button("JSONバックアップをダウンロード", json.dumps(cases, ensure_ascii=False, indent=2), "souzoku_cases_backup.json", "application/json")
    st.stop()

st.subheader("1. 基本情報")
case_name = st.text_input("案件名", value="相続関係説明図")
col1, col2, col3 = st.columns(3)
with col1:
    dec_name = st.text_input("被相続人 氏名", value="")
    dec_birth = st.text_input("被相続人 生年月日", value="")
with col2:
    dec_death = st.text_input("死亡日", value="")
    last_address = st.text_input("最後の住所", value="")
with col3:
    honseki = st.text_input("本籍", value="")
    memo = st.text_input("備考", value="")

st.subheader("2. 配偶者")
sp_cols = st.columns(5)
with sp_cols[0]: sp_name = st.text_input("配偶者 氏名", value="")
with sp_cols[1]: sp_living = st.selectbox("配偶者 状態", ["ご存命", "死亡"], index=0)
with sp_cols[2]: sp_birth = st.text_input("配偶者 生年月日", value="")
with sp_cols[3]: sp_death = st.text_input("配偶者 死亡日", value="")
with sp_cols[4]: sp_share = st.text_input("配偶者 相続分", value="")

st.subheader("3. 相続人入力")
st.caption("空欄の行は出力されません。")

def people_editor(title, default_relations, key):
    rows = [{"relation": r, "name":"", "living": True, "birth":"", "death":"", "share":"", "address":"", "note":""} for r in default_relations]
    return st.data_editor(
        pd.DataFrame(rows),
        num_rows="dynamic",
        use_container_width=True,
        key=key,
        column_config={
            "relation": st.column_config.TextColumn("間柄"),
            "name": st.column_config.TextColumn("氏名"),
            "living": st.column_config.CheckboxColumn("ご存命", default=True),
            "birth": st.column_config.TextColumn("生年月日"),
            "death": st.column_config.TextColumn("死亡日"),
            "share": st.column_config.TextColumn("相続分"),
            "address": st.column_config.TextColumn("住所"),
            "note": st.column_config.TextColumn("備考"),
        }
    ).to_dict("records")

parents = people_editor("父母", ["父", "母"], "parents")
children = people_editor("子", ["長男", "長女", "二男"], "children")
siblings = people_editor("兄弟姉妹", ["兄", "姉", "弟"], "siblings")

case = {
    "case_name": case_name,
    "created_at": date.today().isoformat(),
    "decedent": {"name": dec_name, "birth": dec_birth, "death": dec_death, "last_address": last_address, "honseki": honseki},
    "spouse": {"relation":"配偶者", "name": sp_name, "living": sp_living == "ご存命", "birth": sp_birth, "death": sp_death, "share": sp_share},
    "parents": parents,
    "children": children,
    "siblings": siblings,
    "memo": memo,
}

st.subheader("4. 出力プレビュー")
img = make_diagram(case)
st.image(img, use_container_width=True)

png_buf = BytesIO(); img.save(png_buf, format="PNG"); png_bytes = png_buf.getvalue()
pdf_bytes = image_to_pdf_bytes(img)
xlsx_bytes = to_excel_bytes(case)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.download_button("PNG出力", png_bytes, "相続関係説明図.png", "image/png")
with c2:
    st.download_button("PDF出力", pdf_bytes, "相続関係説明図.pdf", "application/pdf")
with c3:
    st.download_button("Excel出力", xlsx_bytes, "相続関係説明図_入力データ.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with c4:
    if st.button("この案件を保存"):
        cases = load_cases()
        cases.append(case)
        save_cases(cases)
        st.success("保存しました。")

st.divider()
st.warning("注意：このアプリは説明図作成補助です。実際の相続人確定は戸籍等の確認に基づき、必要に応じて専門家判断を行ってください。")
