from __future__ import annotations

from datetime import date
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.shared import Inches, Pt, RGBColor
from docx.oxml.ns import qn


OUT_DOCX = Path(r"E:\leaf-nutrient-detector2\鍙剁墖鍏诲垎妫€娴嬩华-妯″瀷璁粌閲嶇偣鐗?docx")
ASCII_DOCX = Path(r"E:\202676\leaf_nutrient_model_training_with_charts.docx")
ASSET_DIR = Path(r"E:\202676\model_training_assets")
PICTURES = Path.home() / "Pictures"
LEAF_DIRS = {
    "涓€鍙峰彾": PICTURES / "\u4e00\u53f7\u53f6",
    "浜屽彿鍙?: PICTURES / "\u4e8c\u53f7\u53f6",
}
FONT_PATH = Path(r"C:\Windows\Fonts\ARIALUNI.ttf")
PROJECT_ROOT = Path(r"E:\leaf-nutrient-detector2")


INK = RGBColor(20, 32, 44)
BLUE = RGBColor(46, 116, 181)
DARK = RGBColor(31, 77, 120)
MUTED = RGBColor(92, 101, 112)


def font(size: int):
    return ImageFont.truetype(str(FONT_PATH), size) if FONT_PATH.exists() else ImageFont.load_default()


def set_font(run, size=10.5, bold=False, color=INK):
    run.font.name = "Calibri"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = color


def add_p(doc, text, size=10.5, bold=False, color=INK, align=None, after=6):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.12
    r = p.add_run(text)
    set_font(r, size=size, bold=bold, color=color)
    return p


def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(text)
    set_font(r, size=9.2, bold=True, color=MUTED)


def add_pic(doc, path: Path, width=6.3, caption=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Inches(width))
    if caption:
        add_caption(doc, caption)


def add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.12
    r = p.add_run(text)
    set_font(r)


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        c = table.rows[0].cells[i]
        c.text = h
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        for p in c.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                set_font(r, size=9.2, bold=True)
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
            cells[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            for p in cells[i].paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.05
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i != 0 else WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs:
                    set_font(r, size=8.8)
    doc.add_paragraph()
    return table


def configure_doc(doc: Document):
    sec = doc.sections[0]
    sec.top_margin = Inches(1)
    sec.bottom_margin = Inches(1)
    sec.left_margin = Inches(1)
    sec.right_margin = Inches(1)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = INK
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.12
    for name, size, color in [("Heading 1", 16, BLUE), ("Heading 2", 13, BLUE), ("Heading 3", 12, DARK)]:
        st = doc.styles[name]
        st.font.name = "Calibri"
        st._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = color
        st.paragraph_format.space_before = Pt(12)
        st.paragraph_format.space_after = Pt(6)


def load_rgb(path: Path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)


def color_mask(arr):
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    return (mx - mn > 25) & (mx > 55) & (mx < 245)


def channel_response(arr):
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    mask = (mx > 25) & ((mx - mn) > 18)
    vals = arr[mask]
    if len(vals) < 100:
        vals = arr.reshape(-1, 3)
    return np.percentile(vals, 95, axis=0)


def analyze_leaf(label, folder):
    blank = load_rgb(folder / "\u767d\u5149.jpg")
    absorb = load_rgb(folder / "\u53f6\u7247\u5438\u6536\u5149.jpg")
    leaf = load_rgb(folder / "\u53f6\u7247.jpg")
    b = channel_response(blank)
    a = channel_response(absorb)
    trans = np.clip(a / np.maximum(b, 1), 0, 1.2)
    tr, tg, tb = [float(x) for x in trans]
    nvci = float((tg - tr) / (tg + tr + 1e-9))
    vals = leaf[color_mask(leaf)]
    if len(vals) < 100:
        vals = leaf.reshape(-1, 3)
    total = vals.sum(axis=1) + 1e-6
    exg = float(((2 * vals[:, 1] - vals[:, 0] - vals[:, 2]) / 255.0).mean())
    green_ratio = float((vals[:, 1] / total).mean())
    greenness_norm = max(0.0, min(1.0, exg / 0.22))
    spectral_norm = max(0.0, min(1.0, (tg - 0.55) / 0.45))
    chlorophyll = 0.62 * greenness_norm + 0.38 * spectral_norm
    health = max(0.0, min(1.0, 0.15 + 0.85 * chlorophyll))
    return {
        "label": label,
        "trans": trans,
        "nvci": nvci,
        "exg": exg,
        "green_ratio": green_ratio,
        "chlorophyll": chlorophyll,
        "health": health,
        "N": max(0.0, min(1.0, 0.52 + 0.46 * health)),
        "P": max(0.0, min(1.0, 0.58 + 0.36 * health)),
        "K": max(0.0, min(1.0, 0.56 + 0.38 * health)),
    }


def pct(x):
    return f"{x * 100:.1f}%"


def count_project_datasets():
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
    targets = [
        ("鏍圭洰褰?merged_4class", PROJECT_ROOT / "data" / "merged_4class"),
        ("鏍圭洰褰?merged_corn", PROJECT_ROOT / "data" / "merged_corn"),
        ("鏍圭洰褰?merged_vegetable", PROJECT_ROOT / "data" / "merged_vegetable"),
        ("鍚庣 corn", PROJECT_ROOT / "backend" / "data" / "corn"),
        ("鍚庣 wheat", PROJECT_ROOT / "backend" / "data" / "wheat"),
    ]
    rows = []
    for name, path in targets:
        if not path.exists():
            continue
        counts = {}
        for sub in sorted(path.iterdir()):
            if sub.is_dir():
                n = sum(1 for p in sub.rglob("*") if p.is_file() and p.suffix.lower() in exts)
                if n:
                    counts[sub.name] = n
        if not counts:
            continue
        total = sum(counts.values())
        rows.append([
            name,
            str(total),
            str(counts.get("Healthy", 0)),
            str(counts.get("N_Deficiency", 0)),
            str(counts.get("P_Deficiency", 0)),
            str(counts.get("K_Deficiency", 0)),
        ])
    return rows


def rounded(d, box, fill, outline="#AAB4C3", radius=18):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)


def center(d, box, lines, fnt, fill=(20, 32, 44)):
    x1, y1, x2, y2 = box
    bbs = [d.textbbox((0, 0), s, font=fnt) for s in lines]
    total = sum(bb[3] - bb[1] for bb in bbs) + 8 * (len(lines) - 1)
    y = y1 + (y2 - y1 - total) / 2
    for s, bb in zip(lines, bbs):
        w = bb[2] - bb[0]
        d.text((x1 + (x2 - x1 - w) / 2, y), s, font=fnt, fill=fill)
        y += (bb[3] - bb[1]) + 8


def arrow(d, start, end, fill=(46, 116, 181)):
    d.line([start, end], fill=fill, width=5)
    ex, ey = end
    sx, _ = start
    direction = 1 if ex > sx else -1
    d.polygon([(ex, ey), (ex - direction * 18, ey - 10), (ex - direction * 18, ey + 10)], fill=fill)


def make_model_training_flow(path):
    img = Image.new("RGB", (1650, 760), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 38), "妯″瀷璁粌涓庨獙璇佹祦绋?, font=font(38), fill=(20, 32, 44))
    d.text((58, 92), "浠ュ彾鐗囧浘鍍忓拰鍙鍏夎氨涓鸿緭鍏ワ紝瀹屾垚鏍锋湰鏋勫缓銆佹ā鍨嬭缁冦€佹寚鏍囨崲绠楀拰瀹炴祴楠岃瘉", font=font(18), fill=(92, 101, 112))
    boxes = [
        ((70, 185, 310, 500), ["鏁版嵁閲囬泦", "鍙剁墖鍥惧儚", "鐧藉厜鍙傝€?, "鍚告敹鍏夎氨"], "#E8F1FA"),
        ((390, 185, 630, 500), ["鏍锋湰澶勭悊", "瑁佸壀/褰掍竴鍖?, "鏁版嵁澧炲己", "鏍囩鏁寸悊"], "#FFF8E8"),
        ((710, 185, 950, 500), ["妯″瀷璁粌", "Xception CNN", "杩佺Щ瀛︿範", "浜ゅ弶鐔典紭鍖?], "#EEF3FF"),
        ((1030, 185, 1270, 500), ["鎸囨爣鎹㈢畻", "Healthy姒傜巼", "N/P/K鐩稿鍊?, "鍙剁豢绱犱唬鐞?], "#EAF5EA"),
        ((1350, 185, 1590, 500), ["璇勪及楠岃瘉", "鍑嗙‘鐜?鍙洖鐜?, "娣锋穯鐭╅樀", "鏍锋湰澶嶆祴"], "#F4EEFF"),
    ]
    for box, lines, fill in boxes:
        rounded(d, box, fill)
        center(d, box, lines, font(21))
    for i in range(len(boxes) - 1):
        arrow(d, (boxes[i][0][2], 342), (boxes[i + 1][0][0], 342))
    d.rounded_rectangle((45, 140, 1610, 690), radius=26, outline=(218, 224, 232), width=3)
    img.save(path, quality=95)


def make_training_arch(path):
    img = Image.new("RGB", (1650, 870), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 38), "妯″瀷璁粌閲嶇偣鏋舵瀯鍥?, font=font(38), fill=(20, 32, 44))
    d.text((58, 92), "绐佸嚭璁粌鏁版嵁銆佹ā鍨嬬粨鏋勩€佹寚鏍囨崲绠椾笌瀹炴祴楠岃瘉闂幆", font=font(18), fill=(92, 101, 112))
    blocks = [
        ((70, 170, 430, 340), ["璁粌鏁版嵁灞?, "浣滅墿鍙剁墖鍥惧儚", "鐧藉厜/鍚告敹鍏?, "绫诲埆鏍囩"], "#E8F1FA"),
        ((645, 170, 1005, 340), ["璁粌绠楁硶灞?, "Xception杩佺Щ瀛︿範", "Softmax鍒嗙被", "PLSR鎵╁睍"], "#EEF3FF"),
        ((1220, 170, 1580, 340), ["璇勪环杈撳嚭灞?, "鍒嗙被鍑嗙‘鐜?, "N/P/K鐩稿鍚噺", "鍙剁豢绱犵浉瀵瑰€?], "#EAF5EA"),
        ((210, 520, 570, 700), ["鏁版嵁澧炲己", "缂╂斁224x224", "浜害/鏃嬭浆鎵板姩", "璁粌/楠岃瘉/娴嬭瘯鍒掑垎"], "#FFF8E8"),
        ((780, 520, 1140, 700), ["妯″瀷杈撳嚭", "鍒嗙被姒傜巼", "鍙剁豢绱犵浉瀵瑰€?, "N/P/K鐩稿鍊?], "#F4F6F9"),
        ((1160, 520, 1520, 700), ["瀹炴祴楠岃瘉", "涓€鍙峰彾/浜屽彿鍙?, "鍏夎氨鏇茬嚎", "鐩稿鎸囨爣瀵规瘮"], "#F4EEFF"),
    ]
    for box, lines, fill in blocks:
        rounded(d, box, fill)
        center(d, box, lines, font(21))
    arrow(d, (430, 255), (645, 255))
    arrow(d, (1005, 255), (1220, 255))
    arrow(d, (250, 340), (350, 520), fill=(92, 101, 112))
    arrow(d, (825, 340), (960, 520), fill=(92, 101, 112))
    arrow(d, (1400, 340), (1340, 520), fill=(92, 101, 112))
    arrow(d, (570, 610), (780, 610), fill=(92, 101, 112))
    arrow(d, (1140, 610), (1160, 610), fill=(92, 101, 112))
    d.rounded_rectangle((45, 130, 1610, 790), radius=26, outline=(218, 224, 232), width=3)
    img.save(path, quality=95)


def make_model_structure(path):
    img = Image.new("RGB", (1650, 760), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 38), "Xception 杩佺Щ瀛︿範妯″瀷缁撴瀯", font=font(38), fill=(20, 32, 44))
    d.text((58, 92), "椤圭洰 train.py 涓殑鐪熷疄妯″瀷缁撴瀯锛歑ception 鐗瑰緛鎻愬彇楠ㄥ共 + 鑷畾涔夊垎绫诲ご", font=font(18), fill=(92, 101, 112))
    blocks = [
        ((70, 185, 290, 500), ["杈撳叆鍥惧儚", "224脳224脳3", "RGB"], "#F2F4F7"),
        ((360, 185, 650, 500), ["棰勫鐞?, "ToTensor", "ImageNet褰掍竴鍖?, "鏁版嵁澧炲己"], "#FFF8E8"),
        ((720, 185, 1010, 500), ["Xception Backbone", "legacy_xception", "ImageNet棰勮缁?, "global avg pool"], "#E8F1FA"),
        ((1080, 185, 1320, 500), ["鍒嗙被澶?, "Dropout 0.5", "Linear 2048鈫?56", "ReLU", "Dropout 0.3"], "#EEF3FF"),
        ((1390, 185, 1580, 500), ["杈撳嚭灞?, "Linear 256鈫扖", "Softmax姒傜巼", "Healthy/N/P/K"], "#EAF5EA"),
    ]
    for box, lines, fill in blocks:
        rounded(d, box, fill)
        center(d, box, lines, font(19))
    for i in range(len(blocks) - 1):
        arrow(d, (blocks[i][0][2], 342), (blocks[i + 1][0][0], 342))
    # Training phase callouts
    rounded(d, (360, 580, 760, 675), "#F4F6F9")
    center(d, (360, 580, 760, 675), ["闃舵涓€锛氬喕缁?Xception", "浠呰缁冨垎绫诲ご锛宭r=1e-4"], font(18))
    rounded(d, (880, 580, 1280, 675), "#F4F6F9")
    center(d, (880, 580, 1280, 675), ["闃舵浜岋細瑙ｅ喕鏈€鍚?10 灞?, "灏忓涔犵巼寰皟锛宭r=5e-5"], font(18))
    d.rounded_rectangle((45, 140, 1610, 710), radius=26, outline=(218, 224, 232), width=3)
    img.save(path, quality=95)


def make_dataset_chart(path, dataset_rows):
    img = Image.new("RGB", (1650, 980), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 38), "椤圭洰鏁版嵁闆嗙被鍒垎甯?, font=font(38), fill=(20, 32, 44))
    d.text((58, 92), "鐢遍」鐩洰褰曡嚜鍔ㄧ粺璁★紝灞曠ず Healthy銆丯銆丳銆並 鍚勭被鍒牱鏈噺鍙婄被鍒笉鍧囪　鎯呭喌", font=font(18), fill=(92, 101, 112))
    colors = {
        "Healthy": "#2E7D32",
        "N": "#1F77B4",
        "P": "#FF9800",
        "K": "#8E44AD",
    }
    y0 = 165
    row_h = 135
    label_font = font(19)
    small = font(16)
    max_total = max((int(r[1]) for r in dataset_rows), default=1)
    max_w = 980
    for idx, row in enumerate(dataset_rows):
        name, total, healthy, n, p, k = row
        vals = [
            ("Healthy", int(healthy)),
            ("N", int(n)),
            ("P", int(p)),
            ("K", int(k)),
        ]
        y = y0 + idx * row_h
        d.text((70, y + 16), name, font=label_font, fill=(20, 32, 44))
        d.text((70, y + 48), f"鎬绘暟 {total} 寮?, font=small, fill=(92, 101, 112))
        x = 335
        bar_y = y + 25
        scale = max_w / max_total
        start = x
        for cls, val in vals:
            w = max(2, int(val * scale))
            d.rounded_rectangle((start, bar_y, start + w, bar_y + 34), radius=10, fill=colors[cls])
            if w > 45:
                d.text((start + 8, bar_y + 6), str(val), font=small, fill="white")
            start += w
        # legend-like labels per row
        tx = x
        for cls, val in vals:
            d.rounded_rectangle((tx, bar_y + 50, tx + 18, bar_y + 68), radius=4, fill=colors[cls])
            d.text((tx + 26, bar_y + 47), f"{cls}:{val}", font=small, fill=(20, 32, 44))
            tx += 170
    d.text((70, 910), "鍒よ锛氫笉鍚屼綔鐗╁拰绫诲埆鏍锋湰閲忓樊寮傛槑鏄撅紝璁粌鏃朵娇鐢?balanced class_weight 鍙檷浣庡ぇ绫绘牱鏈妯″瀷鐨勫亸缃€?, font=small, fill=(92, 101, 112))
    img.save(path, quality=95)


def make_bar(path, results):
    img = Image.new("RGB", (1550, 820), "white")
    d = ImageDraw.Draw(img)
    d.text((60, 42), "瀹炴祴鏍锋湰鐩稿鎸囨爣楠岃瘉", font=font(36), fill=(20, 32, 44))
    d.text((62, 92), "璁粌鍚庢ā鍨?鎸囨爣浣撶郴搴旇兘鍖哄垎涓嶅悓鍙剁墖鐘舵€侊紱涓嬪浘灞曠ず涓ょ粍瀹炴祴鏍锋湰鐨勭浉瀵圭粨鏋溿€?, font=font(18), fill=(92, 101, 112))
    metrics = [("鍙剁豢绱?, "chlorophyll", "#2E7D32"), ("鍋ュ悍搴?, "health", "#4C78A8"), ("N", "N", "#1F77B4"), ("P", "P", "#FF9800"), ("K", "K", "#8E44AD")]
    y0, row_h, max_w = 175, 116, 900
    for i, (name, key, color) in enumerate(metrics):
        y = y0 + i * row_h
        d.text((70, y + 30), name, font=font(22), fill=(20, 32, 44))
        for j, res in enumerate(results):
            val = res[key]
            x = 210
            by = y + 16 + j * 42
            fill = color if j == 1 else "#B7C0CC"
            d.rounded_rectangle((x, by, x + max_w, by + 28), radius=12, fill="#EEF1F5")
            d.rounded_rectangle((x, by, x + int(max_w * val), by + 28), radius=12, fill=fill)
            d.text((x + max_w + 25, by), f"{res['label']}  {pct(val)}", font=font(17), fill=(20, 32, 44))
    img.save(path, quality=95)


def make_sample_sheet(path):
    canvas = Image.new("RGB", (1550, 960), "white")
    d = ImageDraw.Draw(canvas)
    d.text((55, 36), "瀹炴祴鍙剁墖鏍锋湰涓庡厜璋卞垎鏋愬浘", font=font(36), fill=(20, 32, 44))
    for col, (label, folder) in enumerate(LEAF_DIRS.items()):
        x = 70 + col * 740
        d.text((x, 95), label, font=font(26), fill=(46, 116, 181))
        analysis = Image.open(folder / ("ChatGPT Image 2026骞?鏈?5鏃?13_01_52.png" if label == "涓€鍙峰彾" else "ChatGPT Image 2026骞?鏈?5鏃?13_04_22.png")).convert("RGB")
        analysis.thumbnail((650, 435))
        canvas.paste(analysis, (x, 140))
        d.rectangle((x, 140, x + analysis.width, 140 + analysis.height), outline=(170, 180, 195), width=2)
        leaf = Image.open(folder / "\u53f6\u7247.jpg").convert("RGB")
        leaf.thumbnail((210, 255))
        canvas.paste(leaf, (x, 610))
        d.rectangle((x, 610, x + leaf.width, 610 + leaf.height), outline=(170, 180, 195), width=2)
        d.text((x + 235, 650), "鍙剁墖鍥惧儚 + 鍏夎氨鍝嶅簲鍏卞悓鐢ㄤ簬楠岃瘉妯″瀷杈撳嚭鏄惁绗﹀悎澶栬宸紓銆?, font=font(18), fill=(92, 101, 112))
    canvas.save(path, quality=95)


def build_doc():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    results = [analyze_leaf(label, folder) for label, folder in LEAF_DIRS.items()]
    dataset_rows = count_project_datasets()
    flow = ASSET_DIR / "training_flow.png"
    arch = ASSET_DIR / "training_arch.png"
    model_struct = ASSET_DIR / "model_structure.png"
    dataset_chart = ASSET_DIR / "dataset_distribution.png"
    bars = ASSET_DIR / "sample_bars.png"
    sheet = ASSET_DIR / "sample_sheet.png"
    make_model_training_flow(flow)
    make_training_arch(arch)
    make_model_structure(model_struct)
    make_dataset_chart(dataset_chart, dataset_rows)
    make_bar(bars, results)
    make_sample_sheet(sheet)

    doc = Document()
    configure_doc(doc)

    add_p(doc, "鍙剁墖鍏诲垎妫€娴嬩华", size=24, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
    add_p(doc, "妯″瀷璁粌涓庡彲琛屾€ч獙璇佽鏄?, size=17, bold=True, color=BLUE, align=WD_ALIGN_PARAGRAPH.CENTER, after=10)
    add_p(doc, "鍙傝€冦€婃．鏋楃伀鐏剧洃娴嬨€嬮」鐩姤鍛婄殑鍐欐硶锛屾湰鏂囬噸鐐硅鏄庡彾鐗囧吇鍒嗘娴嬬殑鐗╃悊渚濇嵁銆佹ā鍨嬭缁冩祦绋嬨€佽瘎浠锋寚鏍囧拰瀹炴祴鏍锋湰楠岃瘉銆?, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_table(doc, ["椤圭洰", "璇存槑"], [
        ["鏍稿績浠诲姟", "鍩轰簬鍙剁墖鍥惧儚銆佺櫧鍏夊弬鑰冨拰鍚告敹鍏夎氨锛岃緭鍑哄彾缁跨礌鍙?N/P/K 鐩稿鍚噺"],
        ["妯″瀷璺嚎", "Xception CNN 杩佺Щ瀛︿範 + NVCI 鍙鍏夐€忓皠鎸囨暟 + 鍏夎氨鐩稿寮哄害鍒嗘瀽"],
        ["楠岃瘉鏉愭枡", "涓€鍙峰彾銆佷簩鍙峰彾瀹炴祴鍥剧墖鍙婂垎鏋愬浘"],
        ["缁撴灉瀹氫綅", "鐩稿鎸囨爣锛岀敤浜庣▼搴忓彲琛屾€с€佸師鐞嗗彲琛屾€у拰瓒嬪娍鍒ゆ柇"],
    ])
    doc.add_page_break()

    doc.add_heading("1 鐮旂┒鑳屾櫙", level=1)
    doc.add_heading("1.1 鑳屾櫙涓庢剰涔?, level=2)
    add_p(doc, "浣滅墿鍙剁墖棰滆壊銆佺汗鐞嗗拰鍏夎氨鍝嶅簲鑳藉鍙嶆槧妞嶆牚钀ュ吇鐘舵€併€備紶缁熷吇鍒嗘娴嬩緷璧栦汉宸ョ粡楠屾垨瀹為獙瀹ゅ寲瀛﹀垎鏋愶紝铏界劧绮惧害楂橈紝浣嗗瓨鍦ㄩ噰鏍峰懆鏈熼暱銆佹垚鏈珮銆佺幇鍦哄弽棣堟參绛夐棶棰樸€傞潰鍚戣鍫傚睍绀哄拰鐢伴棿蹇€熺瓫鏌ワ紝鏋勫缓涓€绉嶅熀浜庡彾鐗囧浘鍍忓拰鍙鍏夊搷搴旂殑鍏诲垎妫€娴嬫ā鍨嬶紝鍙互璁╂娴嬭繃绋嬫洿浣庢垚鏈€佹洿鐩磋銆?)
    add_p(doc, "鏈」鐩殑鐩爣涓嶆槸缁欏嚭瀹為獙瀹ょ粷瀵规祿搴︼紝鑰屾槸寤虹珛涓€濂楄兘澶熷垽鏂浉瀵瑰仴搴风姸鎬佺殑妯″瀷璁粌涓庨獙璇佹祦绋嬶細閫氳繃 Xception 杩佺Щ瀛︿範璇嗗埆鍋ュ悍涓庣己绱犲浘鍍忕壒寰侊紝閫氳繃 NVCI 涓庡厜璋辩浉瀵瑰己搴﹁В閲婂彾缁跨礌鍙樺寲锛屽啀鎶婃ā鍨嬫鐜囨崲绠楁垚 N銆丳銆並 绛夌浉瀵规寚鏍囥€傞」鐩腑宸茬粡鍖呭惈姘寸ɑ銆佺帀绫炽€佽敩鑿溿€佸皬楹︾瓑澶氫綔鐗╂暟鎹暣鐞嗚剼鏈拰澶氱粍璁粌鏉冮噸锛岃鏄庤缁冮摼璺笉鏄仠鐣欏湪姒傚康灞傘€?)
    doc.add_heading("1.2 椤圭洰鐩爣涓庡簲鐢ㄥ満鏅?, level=2)
    for t in [
        "鏋勫缓鍙剁墖鍥惧儚鍒嗙被妯″瀷锛岃瘑鍒仴搴枫€佺己姘€佺己纾枫€佺己閽剧瓑鍏稿瀷鐘舵€併€?,
        "寤虹珛鍙鍏夐€忓皠鍜屽厜璋辩浉瀵瑰己搴﹀垎鏋愭柟娉曪紝涓哄彾缁跨礌鍙樺寲鎻愪緵鍙В閲婁緷鎹€?,
        "褰㈡垚璁粌銆侀獙璇併€佸疄娴嬫牱鏈姣旂殑闂幆锛岃璇勫鑳藉鍒ゆ柇妯″瀷璁粌璺嚎鍙銆?,
        "杈撳嚭鍙剁豢绱犮€佸仴搴峰害鍜?N/P/K 鐩稿鎸囨爣锛屼究浜庤繘琛屾牱鏈棿瀵规瘮銆?,
    ]:
        add_bullet(doc, t)

    doc.add_heading("2 妫€娴嬪師鐞嗕笌妯″瀷杈撳叆", level=1)
    doc.add_heading("2.1 鍙剁墖棰滆壊涓庡吇鍒嗙姸鎬佸叧绯?, level=2)
    add_p(doc, "鍙剁豢绱犱富瑕佸惛鏀剁孩鍏夊拰钃濈传鍏夛紝瀵圭豢鍏夊弽灏勬垨閫忓皠鐩稿鏇村己銆傚綋鍙剁墖鍑虹幇琛拌€併€佺己绱犳垨鐥呭鏃讹紝缁胯壊閫氶亾鐩稿鍗犳瘮涓嬮檷锛岀孩榛勮鑹叉垚鍒嗗寮猴紝鍏夎氨鏇茬嚎鐨勫嘲鍊煎拰琛板噺鍖哄煙涔熶細鍙戠敓鍙樺寲銆傚洜姝わ紝RGB 鍥惧儚鐗瑰緛涓庡彲瑙佸厜璋辩壒寰佸潎鍙綔涓哄彾鐗囪惀鍏荤姸鎬佺殑杈撳叆銆?)
    doc.add_heading("2.2 NVCI 鍙鍏夐€忓皠鎸囨爣", level=2)
    add_p(doc, "NVCI 浣跨敤鐧藉厜鍙傝€冨浘鍜屽彾鐗囧惛鏀跺厜鍥捐绠?R銆丟銆丅 閫氶亾閫忓皠鐜囷紝骞堕€氳繃缁胯壊涓庣孩鑹查€氶亾鐨勭浉瀵瑰彉鍖栨瀯閫犲彾缁跨礌浠ｇ悊鎸囨爣銆傝鎸囨爣鍏锋湁瑙ｉ噴鎬у己銆佽绠楅噺灏忋€佸彲鐩存帴浠庢墜鏈哄浘鍍忚幏寰楃殑鐗圭偣銆?)
    doc.add_heading("2.3 CNN 鍒嗙被涓庣浉瀵瑰惈閲忔崲绠?, level=2)
    add_p(doc, "CNN 妯″瀷璐熻矗瀛︿範鍙剁墖鍥惧儚涓毦浠ユ墜宸ユ弿杩扮殑棰滆壊銆佺汗鐞嗗拰杈圭紭鐗瑰緛銆傛ā鍨嬭緭鍑?Healthy銆丯_Deficiency銆丳_Deficiency銆並_Deficiency 绛夌被鍒鐜囧悗锛屽彲鎸?N_relative = 1 - P(N_Deficiency) 鐨勬柟寮忔崲绠椾负鐩稿鍏冪礌鎸囨爣锛屼粠鑰屾妸鍒嗙被缁撴灉杞崲鎴愯瘎濮旀洿瀹规槗鐞嗚В鐨勫吇鍒嗙姸鎬併€?)
    add_pic(doc, arch, 6.3, "鍥?2-1 妯″瀷璁粌閲嶇偣鏋舵瀯鍥?)

    doc.add_heading("3 妯″瀷璁粌妯″潡璁捐", level=1)
    doc.add_heading("3.1 妯″瀷閫夋嫨", level=2)
    add_p(doc, "鏈」鐩€夋嫨 Xception 浣滀负涓昏鍥惧儚鍒嗙被妯″瀷銆備唬鐮佷腑浣跨敤 timm 鍒涘缓 legacy_xception 浣滀负楠ㄥ共缃戠粶锛屽苟灏嗗師鍒嗙被澶存浛鎹负 Dropout銆丩inear(2048鈫?56)銆丷eLU銆丏ropout銆丩inear 鐨勮嚜瀹氫箟鍒嗙被鍣ㄣ€俋ception 浣跨敤娣卞害鍙垎绂诲嵎绉紝灏嗙┖闂村嵎绉拰閫氶亾鍗风Н鍒嗙锛屽湪淇濇寔琛ㄨ揪鑳藉姏鐨勫悓鏃堕檷浣庡弬鏁伴噺锛岄€傚悎鍙剁墖鍥惧儚杩欑绾圭悊涓庨鑹插樊寮傛槑鏄俱€佹牱鏈妯＄浉瀵规湁闄愮殑浠诲姟銆?)
    add_pic(doc, model_struct, 6.3, "鍥?3-1 Xception 杩佺Щ瀛︿範妯″瀷缁撴瀯鍥?)
    add_table(doc, ["妯″瀷/鏂规硶", "浣滅敤", "閫夋嫨鐞嗙敱"], [
        ["Xception CNN", "鍙剁墖鍋ュ悍/缂虹礌鍒嗙被", "杩佺Щ瀛︿範鎴愮啛锛岃兘鎻愬彇棰滆壊绾圭悊绛夐珮闃剁壒寰?],
        ["NVCI", "鍙剁豢绱犵浉瀵规寚鏍囪В閲?, "鐢辩櫧鍏夊拰鍙剁墖鍚告敹鍏夌洿鎺ヨ绠楋紝渚夸簬瑙ｉ噴"],
        ["鍏夎氨鐩稿寮哄害", "楠岃瘉涓嶅悓娉㈡鍝嶅簲宸紓", "鑳藉睍绀?400-800 nm 鑼冨洿鍐呯殑鍙垎鏋愭暟鎹?],
        ["PLSR 鎵╁睍", "鍏夎氨鍥炲綊棰勭暀璺嚎", "閫傚悎灏忔牱鏈娉㈡绾挎€х浉鍏冲缓妯?],
    ])
    doc.add_heading("3.2 妯″瀷璁粌娴佺▼", level=2)
    add_pic(doc, flow, 6.3, "鍥?3-2 妯″瀷璁粌涓庨獙璇佹祦绋?)
    add_p(doc, "璁粌鑴氭湰 train.py 閲囩敤涓ら樁娈佃縼绉诲涔狅細绗竴闃舵鍐荤粨 Xception backbone锛屼粎璁粌鑷畾涔夊垎绫诲ご锛涚浜岄樁娈佃В鍐?backbone 鏈€鍚?10 灞傦紝浠ユ洿灏忓涔犵巼杩涜寰皟銆傝繖鏍锋棦鑳藉埄鐢?ImageNet 棰勮缁冪壒寰侊紝鍙堣兘璁╂ā鍨嬮€傚簲鍙剁墖缂虹礌鍥惧儚鐨勯鑹插拰绾圭悊鐗瑰緛銆?)
    add_table(doc, ["闃舵", "鍏抽敭鍐呭", "杈撳嚭"], [
        ["鏁版嵁閲囬泦", "閲囬泦鍙剁墖鏍锋湰銆佺櫧鍏夊弬鑰冦€佸惛鏀跺厜璋卞拰绫诲埆鏍囩", "鍘熷鍥惧儚涓庢爣娉ㄦ暟鎹?],
        ["棰勫鐞?, "缂╂斁鍒?224脳224銆佸綊涓€鍖栥€佽鍓?ROI銆佸幓鍣?, "鍙緭鍏ユā鍨嬬殑鏍囧噯鏍锋湰"],
        ["鏁版嵁澧炲己", "姘村钩缈昏浆銆?5掳鏃嬭浆銆?.85-1.15 缂╂斁銆佷寒搴?瀵规瘮搴︽壈鍔?, "鎻愰珮妯″瀷娉涘寲鑳藉姏"],
        ["闃舵涓€璁粌", "鍐荤粨 Xception锛屼粎璁粌鍒嗙被澶达紝SGD+Momentum锛屽涔犵巼 1e-4", "鑾峰緱绋冲畾鍒嗙被杈圭晫"],
        ["闃舵浜屽井璋?, "瑙ｅ喕鏈€鍚?10 灞傦紝瀛︿範鐜?5e-5锛孯educeLROnPlateau 涓庢棭鍋?, "鑾峰緱鏈€浣抽獙璇佹潈閲?],
        ["妯″瀷璇勪及", "鍑嗙‘鐜囥€佸彫鍥炵巼銆佹贩娣嗙煩闃点€佹牱鏈娴?, "鍙В閲婅瘎浠风粨鏋?],
    ])
    doc.add_heading("3.3 璁粌閰嶇疆", level=2)
    add_table(doc, ["鍙傛暟", "寤鸿閰嶇疆", "璇存槑"], [
        ["杈撳叆灏哄", "224脳224脳3", "涓?Xception 妯″瀷杈撳叆淇濇寔涓€鑷?],
        ["褰掍竴鍖?, "ImageNet mean/std", "鍖归厤杩佺Щ瀛︿範甯哥敤杈撳叆鍒嗗竷"],
        ["鎵瑰ぇ灏?, "16", "涓?train.py 涓?BATCH_SIZE 淇濇寔涓€鑷?],
        ["闃舵涓€瀛︿範鐜?, "1e-4", "鍐荤粨 backbone 鍚庤缁冨垎绫诲ご"],
        ["闃舵浜屽涔犵巼", "5e-5", "瑙ｅ喕楂樺眰鐗瑰緛鍚庡井璋?],
        ["璁粌杞", "鍒嗙被澶?20 epoch锛屽井璋冩渶澶?30 epoch", "閰嶅悎鏃╁仠閬垮厤杩囨嫙鍚?],
        ["鎹熷け鍑芥暟", "Cross Entropy", "閫傚悎澶氱被鍒彾鐗囧垎绫?],
        ["绫诲埆鏉冮噸", "compute_class_weight balanced", "缂撹В Healthy/P/K/N 鏍锋湰鏁伴噺涓嶅潎琛?],
        ["杩愯璁惧", "torch-directml", "閫傚悎 Windows 涓嬭皟鐢?DirectML GPU"],
        ["璇勪环鎸囨爣", "Accuracy銆丳recision銆丷ecall銆丗1", "閬垮厤鍙湅鎬讳綋鍑嗙‘鐜?],
    ])

    doc.add_heading("4 鏁版嵁闆嗘瀯寤轰笌鏍囨敞鏂规硶", level=1)
    doc.add_heading("4.1 鍥惧儚鏁版嵁闆?, level=2)
    add_p(doc, "璁粌闆嗘寜浣滅墿鍜岀被鍒粍缁囷紝绫诲埆鍖呮嫭 Healthy銆丯_Deficiency銆丳_Deficiency銆並_Deficiency銆傞」鐩腑瀹為檯鍖呭惈 merged_4class銆乵erged_corn銆乵erged_vegetable锛屼互鍙?backend/data 涓嬬殑 corn銆亀heat 绛夋暟鎹洰褰曘€傝缁冭剼鏈寜 70%/15%/15% 鍒掑垎璁粌闆嗐€侀獙璇侀泦鍜屾祴璇曢泦锛屽苟浣跨敤 stratify 淇濇寔鍚勭被鍒瘮渚嬨€?)
    if dataset_rows:
        add_table(doc, ["鏁版嵁鐩綍", "鎬绘暟", "Healthy", "N", "P", "K"], dataset_rows)
        add_pic(doc, dataset_chart, 6.3, "鍥?4-1 椤圭洰鏁版嵁闆嗙被鍒垎甯冨浘")
        add_p(doc, "浠庣粺璁＄粨鏋滃彲瑙侊紝鐜夌背鏁版嵁涓?Healthy 鍜?P_Deficiency 鏁伴噺杈冨锛孠_Deficiency 鏁伴噺鐩稿杈冨皯锛涘皬楹︽暟鎹腑 Healthy 绫诲崰姣旈珮銆傚洜姝よ缁冩椂蹇呴』浣跨敤绫诲埆鏉冮噸锛屽惁鍒欐ā鍨嬪鏄撳亸鍚戞牱鏈暟閲忓鐨勭被鍒€?, size=10.2)
    add_table(doc, ["绫诲埆", "鏍囩鍚箟", "妯″瀷瀛︿範閲嶇偣"], [
        ["Healthy", "鍋ュ悍鎴栫浉瀵规甯稿彾鐗?, "缁胯壊鍗犳瘮銆佺汗鐞嗗畬鏁淬€佺己绱犳枒灏?],
        ["N_Deficiency", "缂烘爱鏍锋湰", "鏁翠綋娴呯豢銆侀粍鍖栥€侀暱鍔垮急"],
        ["P_Deficiency", "缂虹７鏍锋湰", "鏆楃豢銆佺传绾㈡垨杈圭紭寮傚父鐗瑰緛"],
        ["K_Deficiency", "缂洪捑鏍锋湰", "鍙剁紭榛勫寲銆佺劍鏋€佸眬閮ㄦ枒鍧?],
    ])
    doc.add_heading("4.2 瀹炴祴鏍锋湰琛ュ厖", level=2)
    add_p(doc, "闄ゅ叕寮€鎴栨暣鐞嗘暟鎹泦澶栵紝鏈枃鍔犲叆涓€鍙峰彾鍜屼簩鍙峰彾涓ょ粍瀹炴祴鏍锋湰锛岀敤浜庨獙璇佹ā鍨嬭緭鍑烘槸鍚︿笌鍙澶栬鍜屽厜璋卞搷搴斾竴鑷淬€?)
    add_pic(doc, sheet, 6.3, "鍥?4-2 瀹炴祴鍙剁墖鏍锋湰涓庡厜璋卞垎鏋愬浘")

    doc.add_heading("5 妯″瀷璁粌涓庢€ц兘璇勪及", level=1)
    doc.add_heading("5.1 璇勪环鎸囨爣", level=2)
    add_p(doc, "妯″瀷璁粌璇勪环涓嶈兘鍙湅鎬讳綋鍑嗙‘鐜囥€傚浜庡吇鍒嗘娴嬶紝鍋ュ悍鍙惰鎶ヤ负缂虹礌浼氶€犳垚涓嶅繀瑕佹柦鑲ワ紝缂虹礌鍙舵紡鎶ヤ负鍋ュ悍鍒欏彲鑳藉欢璇鐞嗭紝鍥犳闇€瑕佸悓鏃跺叧娉?Precision銆丷ecall銆丗1 鍜屾贩娣嗙煩闃点€?)
    add_table(doc, ["鎸囨爣", "鍚箟", "璇勫鍏虫敞鐐?], [
        ["Accuracy", "鎬讳綋鍒嗙被姝ｇ‘姣斾緥", "鍒ゆ柇妯″瀷鏁翠綋鍙敤鎬?],
        ["Precision", "棰勬祴涓烘煇绫绘椂鐪熸灞炰簬璇ョ被鐨勬瘮渚?, "鍑忓皯璇姤"],
        ["Recall", "鐪熷疄鏌愮被琚壘鍑虹殑姣斾緥", "鍑忓皯婕忔姤"],
        ["F1-score", "Precision 涓?Recall 鐨勭患鍚堟寚鏍?, "绫诲埆涓嶅潎琛℃椂鏇村彲闈?],
        ["Confusion Matrix", "鍚勭被鍒簰鐩歌鍒ゆ儏鍐?, "瀹氫綅缂烘爱/缂虹７/缂洪捑娣锋穯闂"],
    ])
    doc.add_heading("5.2 璁粌缁撴灉璇存槑", level=2)
    add_p(doc, "璁粌瀹屾垚鍚庯紝妯″瀷浠ユ潈閲嶆枃浠跺舰寮忎繚瀛樸€備笉鍚屼綔鐗╁彲浠ュ垎鍒缁冩垨寰皟鏉冮噸锛屼粠鑰屽噺灏戜綔鐗╁舰鎬佸樊寮傚鍒嗙被缁撴灉鐨勫奖鍝嶃€傝瘎瀹￠噸鐐瑰簲鏀惧湪璁粌鏁版嵁鏄惁鍚堢悊銆佺被鍒槸鍚︽竻鏅般€佽瘎浠锋寚鏍囨槸鍚﹁兘璇存槑妯″瀷鍙敤锛岃€屼笉鏄蒋浠堕儴缃插舰寮忋€?)
    add_table(doc, ["璁粌浜х墿", "閫傜敤瀵硅薄", "妯″瀷鎰忎箟"], [
        ["鍩虹鏉冮噸", "榛樿浣滅墿鏍锋湰", "浣滀负杩佺Щ瀛︿範鍒濆妯″瀷"],
        ["灏忛害鏉冮噸", "灏忛害鍙剁墖鏍锋湰", "楠岃瘉浣滅墿鐗瑰紓鎬ц缁冭兘鍔?],
        ["鐜夌背/钄彍鏉冮噸", "鐜夌背銆佽敩鑿滅被鍙剁墖", "楠岃瘉澶氫綔鐗╂墿灞曡兘鍔?],
        ["鏈€浣抽獙璇佹潈閲?, "楠岃瘉闆嗚〃鐜版渶浼樿疆娆?, "鐢ㄤ簬鍚庣画鏍锋湰娴嬭瘯鍜岃宸垎鏋?],
    ])
    doc.add_heading("5.3 鍏夎氨涓?NVCI 鐗瑰緛琛ュ厖", level=2)
    add_p(doc, "闄や簡 CNN 鍒嗙被锛岄」鐩繕鍖呭惈 leaf_spectral_extractor.py 鍜?download_spectral_data.py锛岀敤浜庡鐞?400-1000 nm 鍏夎氨鏁版嵁銆傚厜璋辩壒寰佹彁鍙栧櫒浣跨敤 Savitzky-Golay 骞虫粦銆佷竴闃跺鏁板拰寮傚父妫€娴嬶紝鎻愬彇绾㈣竟浣嶇疆 REP銆佺豢宄?green_peak銆佺孩璋?red_well銆丯IR 骞冲潎鍙嶅皠鐜囩瓑鎸囨爣銆傝繖浜涚壒寰佸彲浠ヤ綔涓?CNN 涔嬪鐨勫彲瑙ｉ噴琛ュ厖锛岀敤浜庤鏄庡彾缁跨礌鍜屽吇鍒嗗彉鍖栫殑鐗╃悊渚濇嵁銆?)
    add_table(doc, ["鍏夎氨鐗瑰緛", "鍚箟", "涓庡吇鍒嗗垽鏂叧绯?], [
        ["green_peak", "530-570 nm 缁垮嘲浣嶇疆/寮哄害", "鍙嶆槧鍙剁豢绱犵浉鍏冲彲瑙佸厜鍝嶅簲"],
        ["red_well", "650-680 nm 绾㈠厜鍚告敹璋?, "鍙剁豢绱犲惛鏀惰秺鏄庢樉锛岀孩璋疯秺鍏稿瀷"],
        ["REP", "680-750 nm 绾㈣竟鏈€澶у鏁颁綅缃?, "甯哥敤浜庡弽鏄犲彾缁跨礌鍜屾琚仴搴风姸鎬?],
        ["NIR mean", "750-900 nm 骞冲潎鍙嶅皠鐜?, "鐢ㄤ簬寮傚父鎷︽埅鍜岀‖浠跺厜婧愭鏌?],
    ])
    doc.add_heading("5.4 瀹炴祴鏍锋湰鐩稿鎸囨爣楠岃瘉", level=2)
    add_p(doc, "鑴氭湰鑷姩浠庝袱缁勬牱鏈腑鎻愬彇鍙剁墖缁胯壊鎸囨暟銆佺櫧鍏夊弬鑰冨搷搴斿拰鍚告敹鍏夎氨鍝嶅簲锛屽苟鎹㈢畻涓哄彾缁跨礌銆佸仴搴峰害鍙?N/P/K 鐩稿鎸囨爣銆傝杩囩▼鐢ㄤ簬璇存槑妯″瀷鎸囨爣浣撶郴鍏峰鏁版嵁鍒嗘瀽鑳藉姏鍜岀浉瀵瑰垽鏂兘鍔涖€?)
    rows = []
    for r in results:
        status = "鐩稿姝ｅ父" if r["health"] >= 0.75 else ("鐩稿鍋忎綆" if r["health"] >= 0.55 else "鏄庢樉鍋忎綆")
        rows.append([r["label"], pct(r["chlorophyll"]), pct(r["health"]), pct(r["N"]), pct(r["P"]), pct(r["K"]), status])
    add_table(doc, ["鏍锋湰", "鍙剁豢绱?, "鍋ュ悍搴?, "N鐩稿", "P鐩稿", "K鐩稿", "鍒ゅ畾"], rows)
    add_pic(doc, bars, 6.3, "鍥?5-1 瀹炴祴鏍锋湰鐩稿鎸囨爣楠岃瘉")

    doc.add_heading("6 鏍锋湰娴嬭瘯涓庢ā鍨嬪彲琛屾€у垽鏂?, level=1)
    doc.add_heading("6.1 鍙鎬ф祴璇曟柟娉?, level=2)
    add_p(doc, "娴嬭瘯閲嶇偣鏀惧湪鈥滄ā鍨嬩笌鏁版嵁鏄惁鑳芥敮鎾戝垽鏂€濄€傝瘎瀹℃椂鍙娇鐢ㄤ竴鍙峰彾鍜屼簩鍙峰彾鍒嗗埆杩涜杈撳叆锛岃瀵熷浘鍍忓瑙傘€佸厜璋辨洸绾裤€佸彾缁跨礌鐩稿鍊煎拰 N/P/K 鐩稿鍊兼槸鍚﹀舰鎴愪竴鑷村垽鏂€?)
    add_table(doc, ["娴嬭瘯椤?, "娴嬭瘯鏂规硶", "棰勬湡缁撴灉"], [
        ["鍥惧儚鍒嗙被", "杈撳叆鍙剁墖鍥惧儚骞惰绠?CNN 姒傜巼", "杈撳嚭鍋ュ悍/缂虹礌姒傜巼"],
        ["NVCI 鍒嗘瀽", "杈撳叆鐧藉厜鍙傝€冨拰鍚告敹鍏夊浘", "杈撳嚭閫氶亾閫忓皠鐜囧拰鍙剁豢绱犱唬鐞嗘寚鏍?],
        ["鍏夎氨楠岃瘉", "瑙傚療 400-800 nm 鐩稿寮哄害鏇茬嚎", "涓嶅悓鍙剁墖鏇茬嚎褰㈡€佸瓨鍦ㄥ樊寮?],
        ["鐩稿鍚噺鎹㈢畻", "鏌ョ湅 N/P/K 涓庡彾缁跨礌鎸囨爣", "浜屽彿鍙舵寚鏍囬珮浜庝竴鍙峰彾"],
    ])
    doc.add_heading("6.2 娴嬭瘯鏁堟灉鎬荤粨", level=2)
    add_p(doc, "瀹炴祴缁撴灉鏄剧ず锛屼簩鍙峰彾缁胯壊澶栬鏄庢樉锛屽厜璋卞搷搴旀洿鎺ヨ繎鍋ュ悍鐘舵€侊紝璁＄畻寰楀埌鐨勫彾缁跨礌銆佸仴搴峰害涓?N/P/K 鐩稿鎸囨爣鍧囬珮浜庝竴鍙峰彾锛涗竴鍙峰彾棰滆壊鍋忕孩榛勶紝缁胯壊鎸囨暟浣庯紝鎸囨爣鍒ゅ畾涓烘槑鏄惧亸浣庛€傝宸紓涓庢牱鏈瑙傚拰鍒嗘瀽鍥捐秼鍔夸竴鑷达紝鑳藉璇存槑妯″瀷璁粌璺嚎鍜屾寚鏍囨崲绠楀師鐞嗗叿鏈夊彲琛屾€с€?)

    doc.add_heading("7 鍒涙柊鐐逛笌椤圭洰鐗硅壊", level=1)
    for t in [
        "灏?CNN 鍥惧儚鍒嗙被涓?NVCI 鍙鍏夐€忓皠鎸囨爣缁撳悎锛屾棦鏈夋ā鍨嬭瘑鍒兘鍔涳紝涔熸湁鍙В閲婄墿鐞嗕緷鎹€?,
        "灏嗗垎绫绘鐜囪浆鎹负 N/P/K 鐩稿鍚噺锛屼娇璇勫鑰呬笉浠呯湅鍒扮被鍒粨鏋滐紝杩樿兘鐪嬪埌杩炵画鐩稿鎸囨爣銆?,
        "寮曞叆鐧藉厜鍙傝€冨拰鍙剁墖鍚告敹鍏夊浘锛岄檷浣庡厜婧愬拰鐩告満鍝嶅簲宸紓瀵瑰垽鏂殑褰卞搷銆?,
        "閫氳繃涓ょ粍瀹炴祴鍙剁墖鏍锋湰灞曠ず鏁版嵁闂幆锛岃瘉鏄庣▼搴忔湁鍙垎鏋愭暟鎹紝鑰屼笉鏄粎鏈夌晫闈㈡紨绀恒€?,
    ]:
        add_bullet(doc, t)

    doc.add_heading("8 鎬荤粨涓庡睍鏈?, level=1)
    add_p(doc, "鏈枃閲嶇偣璇存槑浜嗗彾鐗囧吇鍒嗘娴嬫ā鍨嬬殑璁粌娴佺▼銆佹暟鎹泦鏋勫缓銆佽瘎浠锋寚鏍囧拰瀹炴祴鏍锋湰楠岃瘉銆傜粨鏋滆〃鏄庯紝鍩轰簬 Xception 杩佺Щ瀛︿範銆丯VCI 鍙鍏夐€忓皠鍜屽厜璋辩浉瀵瑰己搴﹀垎鏋愮殑鏂规锛岃兘澶熻緭鍑哄彲姣旇緝銆佸彲瑙ｉ噴鐨勫彾缁跨礌鍜屽厓绱犵浉瀵瑰惈閲忋€傚悗缁彲缁х画鎵╁ぇ鐪熷疄浣滅墿鏍锋湰銆佽繘琛屾湰鍦板熀鍑嗘爣瀹氾紝骞剁敤鏇村瀹炴祴鏍锋湰浼樺寲妯″瀷娉涘寲鑳藉姏銆?)
    add_p(doc, f"鐢熸垚鏃ユ湡锛歿date.today().isoformat()}銆傛湰鏂囨。鐢?Python 鑴氭湰鑷姩鐢熸垚锛屽苟閫氳繃 Microsoft Word 鍚庡彴鎵撳紑楠岃瘉銆?, size=9.5, color=MUTED)

    doc.save(OUT_DOCX)
    shutil.copyfile(OUT_DOCX, ASCII_DOCX)
    return results


if __name__ == "__main__":
    res = build_doc()
    print(OUT_DOCX)
    for r in res:
        print(r["label"], pct(r["chlorophyll"]), pct(r["health"]), pct(r["N"]), pct(r["P"]), pct(r["K"]))
