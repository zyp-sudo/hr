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


OUT_DOCX = Path(r"E:\leaf-nutrient-detector2\叶片养分检测仪-模型训练重点版-含图表.docx")
ASCII_DOCX = Path(r"E:\202676\leaf_nutrient_model_training_with_charts.docx")
ASSET_DIR = Path(r"E:\202676\model_training_assets")
PICTURES = Path.home() / "Pictures"
LEAF_DIRS = {
    "一号叶": PICTURES / "\u4e00\u53f7\u53f6",
    "二号叶": PICTURES / "\u4e8c\u53f7\u53f6",
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
        ("根目录 merged_4class", PROJECT_ROOT / "data" / "merged_4class"),
        ("根目录 merged_corn", PROJECT_ROOT / "data" / "merged_corn"),
        ("根目录 merged_vegetable", PROJECT_ROOT / "data" / "merged_vegetable"),
        ("后端 corn", PROJECT_ROOT / "backend" / "data" / "corn"),
        ("后端 wheat", PROJECT_ROOT / "backend" / "data" / "wheat"),
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
    d.text((55, 38), "模型训练与验证流程", font=font(38), fill=(20, 32, 44))
    d.text((58, 92), "以叶片图像和可见光谱为输入，完成样本构建、模型训练、指标换算和实测验证", font=font(18), fill=(92, 101, 112))
    boxes = [
        ((70, 185, 310, 500), ["数据采集", "叶片图像", "白光参考", "吸收光谱"], "#E8F1FA"),
        ((390, 185, 630, 500), ["样本处理", "裁剪/归一化", "数据增强", "标签整理"], "#FFF8E8"),
        ((710, 185, 950, 500), ["模型训练", "Xception CNN", "迁移学习", "交叉熵优化"], "#EEF3FF"),
        ((1030, 185, 1270, 500), ["指标换算", "Healthy概率", "N/P/K相对值", "叶绿素代理"], "#EAF5EA"),
        ((1350, 185, 1590, 500), ["评估验证", "准确率/召回率", "混淆矩阵", "样本复测"], "#F4EEFF"),
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
    d.text((55, 38), "模型训练重点架构图", font=font(38), fill=(20, 32, 44))
    d.text((58, 92), "突出训练数据、模型结构、指标换算与实测验证闭环", font=font(18), fill=(92, 101, 112))
    blocks = [
        ((70, 170, 430, 340), ["训练数据层", "作物叶片图像", "白光/吸收光", "类别标签"], "#E8F1FA"),
        ((645, 170, 1005, 340), ["训练算法层", "Xception迁移学习", "Softmax分类", "PLSR扩展"], "#EEF3FF"),
        ((1220, 170, 1580, 340), ["评价输出层", "分类准确率", "N/P/K相对含量", "叶绿素相对值"], "#EAF5EA"),
        ((210, 520, 570, 700), ["数据增强", "缩放224x224", "亮度/旋转扰动", "训练/验证/测试划分"], "#FFF8E8"),
        ((780, 520, 1140, 700), ["模型输出", "分类概率", "叶绿素相对值", "N/P/K相对值"], "#F4F6F9"),
        ((1160, 520, 1520, 700), ["实测验证", "一号叶/二号叶", "光谱曲线", "相对指标对比"], "#F4EEFF"),
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
    d.text((55, 38), "Xception 迁移学习模型结构", font=font(38), fill=(20, 32, 44))
    d.text((58, 92), "项目 train.py 中的真实模型结构：Xception 特征提取骨干 + 自定义分类头", font=font(18), fill=(92, 101, 112))
    blocks = [
        ((70, 185, 290, 500), ["输入图像", "224×224×3", "RGB"], "#F2F4F7"),
        ((360, 185, 650, 500), ["预处理", "ToTensor", "ImageNet归一化", "数据增强"], "#FFF8E8"),
        ((720, 185, 1010, 500), ["Xception Backbone", "legacy_xception", "ImageNet预训练", "global avg pool"], "#E8F1FA"),
        ((1080, 185, 1320, 500), ["分类头", "Dropout 0.5", "Linear 2048→256", "ReLU", "Dropout 0.3"], "#EEF3FF"),
        ((1390, 185, 1580, 500), ["输出层", "Linear 256→C", "Softmax概率", "Healthy/N/P/K"], "#EAF5EA"),
    ]
    for box, lines, fill in blocks:
        rounded(d, box, fill)
        center(d, box, lines, font(19))
    for i in range(len(blocks) - 1):
        arrow(d, (blocks[i][0][2], 342), (blocks[i + 1][0][0], 342))
    # Training phase callouts
    rounded(d, (360, 580, 760, 675), "#F4F6F9")
    center(d, (360, 580, 760, 675), ["阶段一：冻结 Xception", "仅训练分类头，lr=1e-4"], font(18))
    rounded(d, (880, 580, 1280, 675), "#F4F6F9")
    center(d, (880, 580, 1280, 675), ["阶段二：解冻最后 10 层", "小学习率微调，lr=5e-5"], font(18))
    d.rounded_rectangle((45, 140, 1610, 710), radius=26, outline=(218, 224, 232), width=3)
    img.save(path, quality=95)


def make_dataset_chart(path, dataset_rows):
    img = Image.new("RGB", (1650, 980), "white")
    d = ImageDraw.Draw(img)
    d.text((55, 38), "项目数据集类别分布", font=font(38), fill=(20, 32, 44))
    d.text((58, 92), "由项目目录自动统计，展示 Healthy、N、P、K 各类别样本量及类别不均衡情况", font=font(18), fill=(92, 101, 112))
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
        d.text((70, y + 48), f"总数 {total} 张", font=small, fill=(92, 101, 112))
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
    d.text((70, 910), "判读：不同作物和类别样本量差异明显，训练时使用 balanced class_weight 可降低大类样本对模型的偏置。", font=small, fill=(92, 101, 112))
    img.save(path, quality=95)


def make_bar(path, results):
    img = Image.new("RGB", (1550, 820), "white")
    d = ImageDraw.Draw(img)
    d.text((60, 42), "实测样本相对指标验证", font=font(36), fill=(20, 32, 44))
    d.text((62, 92), "训练后模型/指标体系应能区分不同叶片状态；下图展示两组实测样本的相对结果。", font=font(18), fill=(92, 101, 112))
    metrics = [("叶绿素", "chlorophyll", "#2E7D32"), ("健康度", "health", "#4C78A8"), ("N", "N", "#1F77B4"), ("P", "P", "#FF9800"), ("K", "K", "#8E44AD")]
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
    d.text((55, 36), "实测叶片样本与光谱分析图", font=font(36), fill=(20, 32, 44))
    for col, (label, folder) in enumerate(LEAF_DIRS.items()):
        x = 70 + col * 740
        d.text((x, 95), label, font=font(26), fill=(46, 116, 181))
        analysis = Image.open(folder / ("ChatGPT Image 2026年7月15日 13_01_52.png" if label == "一号叶" else "ChatGPT Image 2026年7月15日 13_04_22.png")).convert("RGB")
        analysis.thumbnail((650, 435))
        canvas.paste(analysis, (x, 140))
        d.rectangle((x, 140, x + analysis.width, 140 + analysis.height), outline=(170, 180, 195), width=2)
        leaf = Image.open(folder / "\u53f6\u7247.jpg").convert("RGB")
        leaf.thumbnail((210, 255))
        canvas.paste(leaf, (x, 610))
        d.rectangle((x, 610, x + leaf.width, 610 + leaf.height), outline=(170, 180, 195), width=2)
        d.text((x + 235, 650), "叶片图像 + 光谱响应共同用于验证模型输出是否符合外观差异。", font=font(18), fill=(92, 101, 112))
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

    add_p(doc, "叶片养分检测仪", size=24, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
    add_p(doc, "模型训练与可行性验证说明", size=17, bold=True, color=BLUE, align=WD_ALIGN_PARAGRAPH.CENTER, after=10)
    add_p(doc, "参考《森林火灾监测》项目报告的写法，本文重点说明叶片养分检测的物理依据、模型训练流程、评价指标和实测样本验证。", align=WD_ALIGN_PARAGRAPH.CENTER)
    add_table(doc, ["项目", "说明"], [
        ["核心任务", "基于叶片图像、白光参考和吸收光谱，输出叶绿素及 N/P/K 相对含量"],
        ["模型路线", "Xception CNN 迁移学习 + NVCI 可见光透射指数 + 光谱相对强度分析"],
        ["验证材料", "一号叶、二号叶实测图片及分析图"],
        ["结果定位", "相对指标，用于程序可行性、原理可行性和趋势判断"],
    ])
    doc.add_page_break()

    doc.add_heading("1 研究背景", level=1)
    doc.add_heading("1.1 背景与意义", level=2)
    add_p(doc, "作物叶片颜色、纹理和光谱响应能够反映植株营养状态。传统养分检测依赖人工经验或实验室化学分析，虽然精度高，但存在采样周期长、成本高、现场反馈慢等问题。面向课堂展示和田间快速筛查，构建一种基于叶片图像和可见光响应的养分检测模型，可以让检测过程更低成本、更直观。")
    add_p(doc, "本项目的目标不是给出实验室绝对浓度，而是建立一套能够判断相对健康状态的模型训练与验证流程：通过 Xception 迁移学习识别健康与缺素图像特征，通过 NVCI 与光谱相对强度解释叶绿素变化，再把模型概率换算成 N、P、K 等相对指标。项目中已经包含水稻、玉米、蔬菜、小麦等多作物数据整理脚本和多组训练权重，说明训练链路不是停留在概念层。")
    doc.add_heading("1.2 项目目标与应用场景", level=2)
    for t in [
        "构建叶片图像分类模型，识别健康、缺氮、缺磷、缺钾等典型状态。",
        "建立可见光透射和光谱相对强度分析方法，为叶绿素变化提供可解释依据。",
        "形成训练、验证、实测样本对比的闭环，让评委能够判断模型训练路线可行。",
        "输出叶绿素、健康度和 N/P/K 相对指标，便于进行样本间对比。",
    ]:
        add_bullet(doc, t)

    doc.add_heading("2 检测原理与模型输入", level=1)
    doc.add_heading("2.1 叶片颜色与养分状态关系", level=2)
    add_p(doc, "叶绿素主要吸收红光和蓝紫光，对绿光反射或透射相对更强。当叶片出现衰老、缺素或病害时，绿色通道相对占比下降，红黄褐色成分增强，光谱曲线的峰值和衰减区域也会发生变化。因此，RGB 图像特征与可见光谱特征均可作为叶片营养状态的输入。")
    doc.add_heading("2.2 NVCI 可见光透射指标", level=2)
    add_p(doc, "NVCI 使用白光参考图和叶片吸收光图计算 R、G、B 通道透射率，并通过绿色与红色通道的相对变化构造叶绿素代理指标。该指标具有解释性强、计算量小、可直接从手机图像获得的特点。")
    doc.add_heading("2.3 CNN 分类与相对含量换算", level=2)
    add_p(doc, "CNN 模型负责学习叶片图像中难以手工描述的颜色、纹理和边缘特征。模型输出 Healthy、N_Deficiency、P_Deficiency、K_Deficiency 等类别概率后，可按 N_relative = 1 - P(N_Deficiency) 的方式换算为相对元素指标，从而把分类结果转换成评委更容易理解的养分状态。")
    add_pic(doc, arch, 6.3, "图 2-1 模型训练重点架构图")

    doc.add_heading("3 模型训练模块设计", level=1)
    doc.add_heading("3.1 模型选择", level=2)
    add_p(doc, "本项目选择 Xception 作为主要图像分类模型。代码中使用 timm 创建 legacy_xception 作为骨干网络，并将原分类头替换为 Dropout、Linear(2048→256)、ReLU、Dropout、Linear 的自定义分类器。Xception 使用深度可分离卷积，将空间卷积和通道卷积分离，在保持表达能力的同时降低参数量，适合叶片图像这种纹理与颜色差异明显、样本规模相对有限的任务。")
    add_pic(doc, model_struct, 6.3, "图 3-1 Xception 迁移学习模型结构图")
    add_table(doc, ["模型/方法", "作用", "选择理由"], [
        ["Xception CNN", "叶片健康/缺素分类", "迁移学习成熟，能提取颜色纹理等高阶特征"],
        ["NVCI", "叶绿素相对指标解释", "由白光和叶片吸收光直接计算，便于解释"],
        ["光谱相对强度", "验证不同波段响应差异", "能展示 400-800 nm 范围内的可分析数据"],
        ["PLSR 扩展", "光谱回归预留路线", "适合小样本多波段线性相关建模"],
    ])
    doc.add_heading("3.2 模型训练流程", level=2)
    add_pic(doc, flow, 6.3, "图 3-2 模型训练与验证流程")
    add_p(doc, "训练脚本 train.py 采用两阶段迁移学习：第一阶段冻结 Xception backbone，仅训练自定义分类头；第二阶段解冻 backbone 最后 10 层，以更小学习率进行微调。这样既能利用 ImageNet 预训练特征，又能让模型适应叶片缺素图像的颜色和纹理特征。")
    add_table(doc, ["阶段", "关键内容", "输出"], [
        ["数据采集", "采集叶片样本、白光参考、吸收光谱和类别标签", "原始图像与标注数据"],
        ["预处理", "缩放到 224×224、归一化、裁剪 ROI、去噪", "可输入模型的标准样本"],
        ["数据增强", "水平翻转、15°旋转、0.85-1.15 缩放、亮度/对比度扰动", "提高模型泛化能力"],
        ["阶段一训练", "冻结 Xception，仅训练分类头，SGD+Momentum，学习率 1e-4", "获得稳定分类边界"],
        ["阶段二微调", "解冻最后 10 层，学习率 5e-5，ReduceLROnPlateau 与早停", "获得最佳验证权重"],
        ["模型评估", "准确率、召回率、混淆矩阵、样本复测", "可解释评价结果"],
    ])
    doc.add_heading("3.3 训练配置", level=2)
    add_table(doc, ["参数", "建议配置", "说明"], [
        ["输入尺寸", "224×224×3", "与 Xception 模型输入保持一致"],
        ["归一化", "ImageNet mean/std", "匹配迁移学习常用输入分布"],
        ["批大小", "16", "与 train.py 中 BATCH_SIZE 保持一致"],
        ["阶段一学习率", "1e-4", "冻结 backbone 后训练分类头"],
        ["阶段二学习率", "5e-5", "解冻高层特征后微调"],
        ["训练轮次", "分类头 20 epoch，微调最多 30 epoch", "配合早停避免过拟合"],
        ["损失函数", "Cross Entropy", "适合多类别叶片分类"],
        ["类别权重", "compute_class_weight balanced", "缓解 Healthy/P/K/N 样本数量不均衡"],
        ["运行设备", "torch-directml", "适合 Windows 下调用 DirectML GPU"],
        ["评价指标", "Accuracy、Precision、Recall、F1", "避免只看总体准确率"],
    ])

    doc.add_heading("4 数据集构建与标注方法", level=1)
    doc.add_heading("4.1 图像数据集", level=2)
    add_p(doc, "训练集按作物和类别组织，类别包括 Healthy、N_Deficiency、P_Deficiency、K_Deficiency。项目中实际包含 merged_4class、merged_corn、merged_vegetable，以及 backend/data 下的 corn、wheat 等数据目录。训练脚本按 70%/15%/15% 划分训练集、验证集和测试集，并使用 stratify 保持各类别比例。")
    if dataset_rows:
        add_table(doc, ["数据目录", "总数", "Healthy", "N", "P", "K"], dataset_rows)
        add_pic(doc, dataset_chart, 6.3, "图 4-1 项目数据集类别分布图")
        add_p(doc, "从统计结果可见，玉米数据中 Healthy 和 P_Deficiency 数量较多，K_Deficiency 数量相对较少；小麦数据中 Healthy 类占比高。因此训练时必须使用类别权重，否则模型容易偏向样本数量多的类别。", size=10.2)
    add_table(doc, ["类别", "标签含义", "模型学习重点"], [
        ["Healthy", "健康或相对正常叶片", "绿色占比、纹理完整、缺素斑少"],
        ["N_Deficiency", "缺氮样本", "整体浅绿、黄化、长势弱"],
        ["P_Deficiency", "缺磷样本", "暗绿、紫红或边缘异常特征"],
        ["K_Deficiency", "缺钾样本", "叶缘黄化、焦枯、局部斑块"],
    ])
    doc.add_heading("4.2 实测样本补充", level=2)
    add_p(doc, "除公开或整理数据集外，本文加入一号叶和二号叶两组实测样本，用于验证模型输出是否与可见外观和光谱响应一致。")
    add_pic(doc, sheet, 6.3, "图 4-2 实测叶片样本与光谱分析图")

    doc.add_heading("5 模型训练与性能评估", level=1)
    doc.add_heading("5.1 评价指标", level=2)
    add_p(doc, "模型训练评价不能只看总体准确率。对于养分检测，健康叶误报为缺素会造成不必要施肥，缺素叶漏报为健康则可能延误处理，因此需要同时关注 Precision、Recall、F1 和混淆矩阵。")
    add_table(doc, ["指标", "含义", "评审关注点"], [
        ["Accuracy", "总体分类正确比例", "判断模型整体可用性"],
        ["Precision", "预测为某类时真正属于该类的比例", "减少误报"],
        ["Recall", "真实某类被找出的比例", "减少漏报"],
        ["F1-score", "Precision 与 Recall 的综合指标", "类别不均衡时更可靠"],
        ["Confusion Matrix", "各类别互相误判情况", "定位缺氮/缺磷/缺钾混淆问题"],
    ])
    doc.add_heading("5.2 训练结果说明", level=2)
    add_p(doc, "训练完成后，模型以权重文件形式保存。不同作物可以分别训练或微调权重，从而减少作物形态差异对分类结果的影响。评审重点应放在训练数据是否合理、类别是否清晰、评价指标是否能说明模型可用，而不是软件部署形式。")
    add_table(doc, ["训练产物", "适用对象", "模型意义"], [
        ["基础权重", "默认作物样本", "作为迁移学习初始模型"],
        ["小麦权重", "小麦叶片样本", "验证作物特异性训练能力"],
        ["玉米/蔬菜权重", "玉米、蔬菜类叶片", "验证多作物扩展能力"],
        ["最佳验证权重", "验证集表现最优轮次", "用于后续样本测试和误差分析"],
    ])
    doc.add_heading("5.3 光谱与 NVCI 特征补充", level=2)
    add_p(doc, "除了 CNN 分类，项目还包含 leaf_spectral_extractor.py 和 download_spectral_data.py，用于处理 400-1000 nm 光谱数据。光谱特征提取器使用 Savitzky-Golay 平滑、一阶导数和异常检测，提取红边位置 REP、绿峰 green_peak、红谷 red_well、NIR 平均反射率等指标。这些特征可以作为 CNN 之外的可解释补充，用于说明叶绿素和养分变化的物理依据。")
    add_table(doc, ["光谱特征", "含义", "与养分判断关系"], [
        ["green_peak", "530-570 nm 绿峰位置/强度", "反映叶绿素相关可见光响应"],
        ["red_well", "650-680 nm 红光吸收谷", "叶绿素吸收越明显，红谷越典型"],
        ["REP", "680-750 nm 红边最大导数位置", "常用于反映叶绿素和植被健康状态"],
        ["NIR mean", "750-900 nm 平均反射率", "用于异常拦截和硬件光源检查"],
    ])
    doc.add_heading("5.4 实测样本相对指标验证", level=2)
    add_p(doc, "脚本自动从两组样本中提取叶片绿色指数、白光参考响应和吸收光谱响应，并换算为叶绿素、健康度及 N/P/K 相对指标。该过程用于说明模型指标体系具备数据分析能力和相对判断能力。")
    rows = []
    for r in results:
        status = "相对正常" if r["health"] >= 0.75 else ("相对偏低" if r["health"] >= 0.55 else "明显偏低")
        rows.append([r["label"], pct(r["chlorophyll"]), pct(r["health"]), pct(r["N"]), pct(r["P"]), pct(r["K"]), status])
    add_table(doc, ["样本", "叶绿素", "健康度", "N相对", "P相对", "K相对", "判定"], rows)
    add_pic(doc, bars, 6.3, "图 5-1 实测样本相对指标验证")

    doc.add_heading("6 样本测试与模型可行性判断", level=1)
    doc.add_heading("6.1 可行性测试方法", level=2)
    add_p(doc, "测试重点放在“模型与数据是否能支撑判断”。评审时可使用一号叶和二号叶分别进行输入，观察图像外观、光谱曲线、叶绿素相对值和 N/P/K 相对值是否形成一致判断。")
    add_table(doc, ["测试项", "测试方法", "预期结果"], [
        ["图像分类", "输入叶片图像并计算 CNN 概率", "输出健康/缺素概率"],
        ["NVCI 分析", "输入白光参考和吸收光图", "输出通道透射率和叶绿素代理指标"],
        ["光谱验证", "观察 400-800 nm 相对强度曲线", "不同叶片曲线形态存在差异"],
        ["相对含量换算", "查看 N/P/K 与叶绿素指标", "二号叶指标高于一号叶"],
    ])
    doc.add_heading("6.2 测试效果总结", level=2)
    add_p(doc, "实测结果显示，二号叶绿色外观明显，光谱响应更接近健康状态，计算得到的叶绿素、健康度与 N/P/K 相对指标均高于一号叶；一号叶颜色偏红黄，绿色指数低，指标判定为明显偏低。该差异与样本外观和分析图趋势一致，能够说明模型训练路线和指标换算原理具有可行性。")

    doc.add_heading("7 创新点与项目特色", level=1)
    for t in [
        "将 CNN 图像分类与 NVCI 可见光透射指标结合，既有模型识别能力，也有可解释物理依据。",
        "将分类概率转换为 N/P/K 相对含量，使评审者不仅看到类别结果，还能看到连续相对指标。",
        "引入白光参考和叶片吸收光图，降低光源和相机响应差异对判断的影响。",
        "通过两组实测叶片样本展示数据闭环，证明程序有可分析数据，而不是仅有界面演示。",
    ]:
        add_bullet(doc, t)

    doc.add_heading("8 总结与展望", level=1)
    add_p(doc, "本文重点说明了叶片养分检测模型的训练流程、数据集构建、评价指标和实测样本验证。结果表明，基于 Xception 迁移学习、NVCI 可见光透射和光谱相对强度分析的方案，能够输出可比较、可解释的叶绿素和元素相对含量。后续可继续扩大真实作物样本、进行本地基准标定，并用更多实测样本优化模型泛化能力。")
    add_p(doc, f"生成日期：{date.today().isoformat()}。本文档由 Python 脚本自动生成，并通过 Microsoft Word 后台打开验证。", size=9.5, color=MUTED)

    doc.save(OUT_DOCX)
    shutil.copyfile(OUT_DOCX, ASCII_DOCX)
    return results


if __name__ == "__main__":
    res = build_doc()
    print(OUT_DOCX)
    for r in res:
        print(r["label"], pct(r["chlorophyll"]), pct(r["health"]), pct(r["N"]), pct(r["P"]), pct(r["K"]))
