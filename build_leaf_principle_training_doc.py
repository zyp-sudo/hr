from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUT = Path(r"E:\leaf-nutrient-detector2\叶片养分检测仪-原理与模型训练过程.docx")

BLUE = RGBColor(46, 116, 181)
DARK_BLUE = RGBColor(31, 77, 120)
INK = RGBColor(20, 32, 44)
MUTED = RGBColor(92, 101, 112)
LIGHT_GRAY = "F2F4F7"
CALLOUT = "F4F6F9"
WHITE = "FFFFFF"


def set_run_font(run, name="Calibri", size=None, color=None, bold=None, italic=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:ascii"), name)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), name)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    if size is not None:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def set_para_spacing(paragraph, before=0, after=6, line=1.10):
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.space_after = Pt(after)
    paragraph.paragraph_format.line_spacing = line


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_cell_text(cell, text, bold=False, color=INK, size=10.5, align=WD_ALIGN_PARAGRAPH.LEFT):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    set_para_spacing(p, after=0, line=1.10)
    r = p.add_run(text)
    set_run_font(r, size=size, color=color, bold=bold)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    set_cell_margins(cell)


def set_table_widths(table, widths):
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), "9360")
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120")
    tbl_ind.set(qn("w:type"), "dxa")

    grid = table._tbl.tblGrid
    if grid is None:
        grid = OxmlElement("w:tblGrid")
        table._tbl.insert(0, grid)
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            cell.width = Pt(widths[idx] / 20)
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(widths[idx]))
            tc_w.set(qn("w:type"), "dxa")


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("叶片养分检测仪软件端技术报告")
    set_run_font(run, size=9, color=MUTED)


def add_heading(doc, text, level=1):
    p = doc.add_paragraph(style=f"Heading {level}")
    p.add_run(text)
    return p


def add_body(doc, text):
    p = doc.add_paragraph()
    set_para_spacing(p)
    r = p.add_run(text)
    set_run_font(r, size=11, color=INK)
    return p


def add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    set_para_spacing(p, after=4, line=1.167)
    r = p.add_run(text)
    set_run_font(r, size=11, color=INK)
    return p


def add_numbered(doc, text):
    p = doc.add_paragraph(style="List Number")
    set_para_spacing(p, after=4, line=1.167)
    r = p.add_run(text)
    set_run_font(r, size=11, color=INK)
    return p


def add_callout(doc, label, text):
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    set_table_widths(table, [9360])
    cell = table.cell(0, 0)
    set_cell_shading(cell, CALLOUT)
    cell.text = ""
    p = cell.paragraphs[0]
    set_para_spacing(p, after=0, line=1.10)
    r1 = p.add_run(label + "：")
    set_run_font(r1, size=10.5, color=DARK_BLUE, bold=True)
    r2 = p.add_run(text)
    set_run_font(r2, size=10.5, color=INK)
    set_cell_margins(cell, top=140, bottom=140, start=160, end=160)
    doc.add_paragraph()


def add_matrix(doc, headers, rows, widths):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    set_table_widths(table, widths)
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        set_cell_shading(hdr[i], LIGHT_GRAY)
        set_cell_text(hdr[i], h, bold=True, color=INK, size=10.2, align=WD_ALIGN_PARAGRAPH.CENTER)
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            set_cell_shading(cells[i], WHITE)
            align = WD_ALIGN_PARAGRAPH.CENTER if i == 0 else WD_ALIGN_PARAGRAPH.LEFT
            set_cell_text(cells[i], val, size=10.0, align=align)
    doc.add_paragraph()
    return table


def configure_styles(doc):
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(11)
    normal.font.color.rgb = INK
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.10

    specs = [
        ("Heading 1", 16, BLUE, 16, 8),
        ("Heading 2", 13, BLUE, 12, 6),
        ("Heading 3", 12, DARK_BLUE, 8, 4),
    ]
    for style_name, size, color, before, after in specs:
        style = doc.styles[style_name]
        style.font.name = "Calibri"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.color.rgb = color
        style.font.bold = True
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.10


def setup_header_footer(section):
    header = section.header.paragraphs[0]
    header.text = ""
    header.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = header.add_run("叶片养分检测仪软件端")
    set_run_font(r, size=9, color=MUTED)
    footer = section.footer.paragraphs[0]
    add_page_number(footer)


def add_cover(doc):
    p = doc.add_paragraph()
    set_para_spacing(p, before=12, after=4)
    r = p.add_run("技术报告")
    set_run_font(r, size=11, color=MUTED, bold=True)

    title = doc.add_paragraph()
    set_para_spacing(title, after=8)
    r = title.add_run("叶片养分检测仪软件端")
    set_run_font(r, size=24, color=INK, bold=True)

    sub = doc.add_paragraph()
    set_para_spacing(sub, after=18)
    r = sub.add_run("检测原理与模型训练过程")
    set_run_font(r, size=15, color=MUTED)

    rows = [
        ("项目名称", "leaf-nutrient-detector2"),
        ("软件形态", "微信小程序前端 + FastAPI 后端 + 深度学习模型服务"),
        ("核心方法", "NVCI 可见光透射指数、Xception CNN 图像分类、可选 PLSR 光谱回归"),
        ("文档定位", "说明系统检测原理、模型训练流程、推理部署与质量控制"),
        ("生成日期", date.today().isoformat()),
    ]
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    set_table_widths(table, [1800, 7560])
    for label, value in rows:
        cells = table.add_row().cells
        set_cell_shading(cells[0], LIGHT_GRAY)
        set_cell_text(cells[0], label, bold=True, size=10.5, align=WD_ALIGN_PARAGRAPH.CENTER)
        set_cell_text(cells[1], value, size=10.5)

    add_callout(
        doc,
        "使用边界",
        "本文所述检测结果均为相对指标，适合田间快速筛查、农事管理和复测趋势判断；不替代实验室绝对浓度检测。"
    )
    doc.add_page_break()


def add_static_toc(doc):
    add_heading(doc, "目录", 1)
    toc_items = [
        "1. 系统检测原理",
        "2. NVCI 可见光透射检测原理",
        "3. CNN 图像分类与相对含量换算原理",
        "4. 光谱回归接口的扩展原理",
        "5. 模型训练数据与样本组织",
        "6. Xception 迁移学习训练流程",
        "7. 训练评估、模型导出与部署",
        "8. 前后端联调与质量控制",
    ]
    for item in toc_items:
        add_bullet(doc, item)
    doc.add_page_break()


def build_doc():
    doc = Document()
    configure_styles(doc)
    setup_header_footer(doc.sections[0])
    add_cover(doc)
    add_static_toc(doc)

    add_heading(doc, "1. 系统检测原理", 1)
    add_body(doc, "叶片养分检测仪的软件端采用“前端采集、后端推理、统一相对指标输出”的结构。微信小程序负责图像采集、连接发现、结果展示和历史记录；FastAPI 后端负责图像解码、NVCI 指数计算、CNN 模型推理、数据库查询与接口响应。")
    add_body(doc, "系统提供两条主要检测路径：其一是 NVCI 双图检测，通过空白基准图和叶片遮挡图计算可见光透射变化；其二是 CNN 单图检测，通过叶片照片识别健康、缺氮、缺磷、缺钾等类别，再将分类概率换算为相对养分指标。")
    add_matrix(
        doc,
        ["检测路径", "输入数据", "核心计算", "输出结果"],
        [
            ("NVCI", "空白基准图、叶片遮挡图", "RGB 透射率、NVCI、健康基准 Ratio", "NVCI 值、相对健康比率、红黄绿状态、建议"),
            ("CNN", "单张叶片图像", "Xception 分类、Softmax 概率、相对含量换算", "分类标签、置信度、健康度、N/P/K 相对含量"),
            ("Spectral", "400-1000nm 反射率序列", "PLSR 回归和异常质量检查", "相对趋势预测、可靠性标记"),
        ],
        [1600, 2300, 2800, 2660],
    )
    add_callout(doc, "统一判定", "两条主路径都使用 Ratio 思想表达相对健康程度：大于 0.9 为相对正常，0.7 到 0.9 为相对偏低，小于等于 0.7 为明显偏低。")

    add_heading(doc, "2. NVCI 可见光透射检测原理", 1)
    add_body(doc, "NVCI 模式基于可见光穿过叶片后的 RGB 通道变化。软件先采集一张空白基准图，用于表示无叶片遮挡时光源与摄像头的基准亮度；再采集叶片遮挡图，用于表示叶片对红、绿、蓝通道的吸收与透射结果。")
    add_numbered(doc, "图像进入后端后，OpenCV 将 base64 或上传文件解码为 BGR 数组。")
    add_numbered(doc, "NVCIEngine 自动检测或使用指定 ROI，提取空白图与叶片图在同一区域内的通道亮度。")
    add_numbered(doc, "分别计算 R、G、B 通道透射率，即叶片图亮度与空白图亮度的比值。")
    add_numbered(doc, "根据可见光叶绿素敏感关系计算归一化可见光叶绿素指数 NVCI。")
    add_numbered(doc, "从 plant_baselines 查询健康基准 NVCI，并计算 Ratio = 当前 NVCI / baseline_nvci。")
    add_numbered(doc, "根据 Ratio 输出 normal、mild、severe 或 unknown 状态，并生成追肥或复测建议。")
    add_matrix(
        doc,
        ["指标", "含义", "软件位置"],
        [
            ("T_R/T_G/T_B", "红、绿、蓝通道透射率，反映叶片对不同可见光通道的吸收差异", "backend/nvci_engine.py"),
            ("NVCI", "由 RGB 透射关系构造的相对叶绿素指数", "backend/nvci_engine.py"),
            ("baseline_nvci", "健康叶片或通用基准 NVCI，用于本地化标定", "backend/database.py、plant_baselines"),
            ("Ratio", "当前样本相对健康基准的比例，是最终状态判定的核心", "backend/nvci_service.py"),
        ],
        [1700, 5600, 2060],
    )
    add_body(doc, "NVCI 模式的优点是推理过程解释性强、无需深度学习权重即可运行，适合固定光源和固定拍摄结构下的快速筛查。其主要误差来源包括光源不稳定、叶片厚度差异、ROI 偏移、镜头曝光变化和健康基准未本地化标定。")

    add_heading(doc, "3. CNN 图像分类与相对含量换算原理", 1)
    add_body(doc, "CNN 模式使用 Xception 卷积神经网络对叶片照片进行分类。模型输出各类别的 Softmax 概率，后端再将概率转换为更便于农事解释的相对健康度和 N/P/K 相对含量。")
    add_matrix(
        doc,
        ["类别", "模型含义", "相对含量解释"],
        [
            ("Healthy", "叶片图像更接近健康样本", "P(Healthy) 作为综合健康度 health_ratio"),
            ("N_Deficiency", "图像特征更接近缺氮样本", "N_relative = 1 - P(N_Deficiency)"),
            ("P_Deficiency", "图像特征更接近缺磷样本", "P_relative = 1 - P(P_Deficiency)"),
            ("K_Deficiency", "图像特征更接近缺钾样本", "K_relative = 1 - P(K_Deficiency)"),
        ],
        [1600, 3400, 4360],
    )
    add_body(doc, "这种换算方式的目的不是给出实验室意义上的氮、磷、钾含量，而是把分类概率转化为统一的相对风险指标。当前后端会返回 prediction、confidence、probabilities、health_ratio、nutrient_ratios、status、status_label 和 status_color 等字段，前端据此绘制概率图和相对含量条。")
    add_callout(doc, "模型解释", "当某一缺素类别概率升高时，对应元素的相对含量会降低；当 Healthy 概率升高时，综合健康度提高。该设计便于把分类模型嵌入统一的红黄绿状态体系。")

    add_heading(doc, "4. 光谱回归接口的扩展原理", 1)
    add_body(doc, "后端保留了 /predict-spectral 接口，用于扩展 400-1000nm 反射率光谱输入。该接口采用 PLSR 思路，将多波段反射率映射为相对养分趋势，并包含光谱质量检查。")
    add_bullet(doc, "输入维度默认为 61 个波段，对应 400nm 到 1000nm、10nm 步长。")
    add_bullet(doc, "预处理可包含 SNV、MSC 和 StandardScaler，用于降低散射、基线漂移和量纲差异。")
    add_bullet(doc, "异常检测可使用 PCA 重建误差和 Isolation Forest，输出 is_reliable 与 quality_warning。")
    add_bullet(doc, "模型文件不存在时接口返回 success=false，不影响 CNN 与 NVCI 主流程。")

    add_heading(doc, "5. 模型训练数据与样本组织", 1)
    add_body(doc, "CNN 模型训练依赖按作物和类别组织的叶片图像数据。项目中可见的训练数据目录按作物划分，例如 corn、wheat、rice 或 vegetable，再在作物目录下按 Healthy、N_Deficiency、P_Deficiency、K_Deficiency 等类别建立子目录。")
    add_matrix(
        doc,
        ["环节", "处理内容", "目的"],
        [
            ("数据收集", "采集不同作物、不同生长阶段、不同光照环境下的叶片图像", "提高模型对真实田间场景的泛化能力"),
            ("类别标注", "根据健康、缺氮、缺磷、缺钾等类别整理文件夹", "让训练脚本直接从目录结构读取标签"),
            ("数据清洗", "剔除模糊、遮挡严重、背景干扰过强和标注不一致图片", "减少噪声样本对模型决策边界的影响"),
            ("数据划分", "划分训练集、验证集和测试集，尽量避免同一植株图片泄漏到不同集合", "保证评估结果更接近真实泛化表现"),
        ],
        [1700, 4700, 2960],
    )
    add_body(doc, "训练前通常需要对图像进行统一尺寸、颜色空间和归一化处理。项目推理端将图片缩放到 224 x 224，并使用 ImageNet 的均值和标准差归一化，因此训练端也应保持同样的输入规范，避免训练与推理分布不一致。")

    add_heading(doc, "6. Xception 迁移学习训练流程", 1)
    add_body(doc, "项目后端模型加载器定义了 XceptionClassifier：以 legacy_xception 作为特征提取骨干，去掉原分类头后接入 Dropout、Linear、ReLU、Dropout、Linear 组成的自定义分类器。该结构适合在样本量有限的农业图像任务中进行迁移学习。")
    add_matrix(
        doc,
        ["阶段", "关键操作", "输出"],
        [
            ("骨干网络初始化", "使用 timm 创建 legacy_xception，设置 pretrained=False 或加载已有权重", "通用卷积特征提取器"),
            ("分类头构建", "2048 维特征接 256 维隐藏层，再输出 3 类或 4 类", "适配缺素分类任务的模型结构"),
            ("训练循环", "前向传播、交叉熵损失、反向传播、优化器更新", "不断降低训练损失"),
            ("验证评估", "在验证集计算准确率、混淆矩阵和类别表现", "选择最佳权重并判断过拟合"),
            ("权重保存", "保存 .pth state_dict，部署时可转换为 .pt 完整模型缓存", "可复用的推理模型文件"),
        ],
        [1700, 5100, 2560],
    )
    add_body(doc, "训练过程中应使用数据增强提升鲁棒性，例如随机裁剪、水平翻转、亮度/对比度扰动、轻微旋转和颜色抖动。农业叶片图像容易受到背景、光照、角度和品种差异影响，适度增强能降低模型只记住拍摄条件的风险。")
    add_callout(doc, "类别数注意", "model_loader.py 能根据分类器输出层自动识别 3 类或 4 类模型，并映射到对应标签。训练和部署时必须保证标签顺序与后端 CLASS_LABELS_MAP 一致。")

    add_heading(doc, "7. 训练评估、模型导出与部署", 1)
    add_body(doc, "模型训练完成后，需要在独立测试集上评估整体准确率和各类别表现。单一准确率不能完全反映农业检测质量，尤其当缺素类别样本不均衡时，应同时关注召回率、混淆矩阵和误判类型。")
    add_bullet(doc, "健康样本被误判为缺素，会导致不必要追肥，属于成本型误报。")
    add_bullet(doc, "缺素样本被误判为健康，会延误农事处理，属于风险型漏报。")
    add_bullet(doc, "缺氮、缺磷、缺钾之间互相误判，会影响建议肥料类型，需要在类别层面重点复核。")
    add_body(doc, "部署端支持按作物选择权重：rice 对应 weights.pth，wheat 对应 weights_wheat.pth，corn 和 vegetable 对应 weights_corn_veg.pth。首次加载 .pth 时，后端会构建模型、加载 state_dict、执行 DirectML 设备预热，并尝试保存 .pt 完整模型缓存；后续启动优先读取 .pt，以减少 timm 建模和权重加载时间。")
    add_matrix(
        doc,
        ["文件", "用途", "部署说明"],
        [
            ("weights.pth", "默认/水稻模型 state_dict", "放置于 backend 目录，缺失时 /predict 回退 mock"),
            ("weights_wheat.pth", "小麦模型 state_dict", "crop_type=wheat 时加载"),
            ("weights_corn_veg.pth", "玉米/蔬菜模型 state_dict", "crop_type=corn 或 vegetable 时加载"),
            ("*.pt", "完整模型缓存", "由后端首次加载后生成，后续启动优先使用"),
        ],
        [2300, 3000, 4060],
    )

    add_heading(doc, "8. 前后端联调与质量控制", 1)
    add_body(doc, "软件端质量控制需要同时覆盖模型正确性、接口稳定性和前端展示一致性。小程序通过缓存地址、UDP 自动发现和端口扫描寻找后端；后端通过 /health 暴露模型、权重和 MySQL 状态；检测失败时前端或后端会进入 mock 降级路径，保证演示流程不中断。")
    add_matrix(
        doc,
        ["检查项", "建议方法", "通过标准"],
        [
            ("后端健康", "访问 /health 或首页刷新状态", "status=ok，端口与小程序连接地址一致"),
            ("CNN 推理", "上传已知类别叶片图片到 /predict", "返回 prediction、confidence 和 probabilities"),
            ("NVCI 推理", "上传空白图和叶片图到 /predict-nvci", "返回 nvci、ratio、status 和通道详情"),
            ("历史记录", "保存结果后进入历史页", "本地记录存在，MySQL 可用时同步成功"),
            ("降级流程", "关闭后端或移除权重后测试", "前端提示离线或返回 mock，不出现页面崩溃"),
        ],
        [1800, 4100, 3460],
    )
    add_body(doc, "在正式部署前，建议使用本地真实作物样本重新标定 NVCI 基准值，并使用目标作物、目标设备和目标拍摄条件采集验证集。对于 CNN 模型，建议持续收集误判样本并加入下一轮训练，以形成数据闭环。")
    add_callout(doc, "结论", "本软件端采用可解释的 NVCI 指数和可迁移的 CNN 分类模型并行工作，以统一的相对指标输出检测结果。NVCI 适合固定光路下的快速指数判断，CNN 适合基于外观症状的类别识别；二者结合能够兼顾可解释性、易用性和扩展性。")

    return doc


if __name__ == "__main__":
    document = build_doc()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    document.save(OUT)
    print(OUT)
