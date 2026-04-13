from __future__ import annotations

# 该脚本用于“软著用户手册”生成：批量截图 → 自动生成 LaTeX → 编译 PDF
# 设计目标：可复制到任意项目复用（尽量仅依赖 Python 标准库与 xelatex）

# 命令行参数解析（输入目录/输出路径/LaTeX 引擎等）
import argparse
# 文件名解析（按“章节-序号-图名”规范扫描截图）
import re
# 调用 xelatex 编译 PDF
import subprocess
# 用 dataclass 表示页眉信息（软件名、版本号）
from dataclasses import dataclass
# 跨平台路径处理与读写文件
from pathlib import Path


@dataclass(frozen=True)
class AppHeader:
    # 软件展示名称（用于页眉与封面）
    display_name: str
    # 软件版本号（用于页眉与封面）
    app_version: str

    def version_label(self) -> str:
        # 将版本号规范化为形如 “V1.0” 的格式
        v = self.app_version.strip()
        if v and not v.lower().startswith("v"):
            v = "V" + v
        return v

    def header_text(self) -> str:
        # 生成页眉文本：“软件名 + 空格 + 版本号”
        return (self.display_name.strip() + " " + self.version_label()).strip()


def _read_text_lossy(path: Path) -> str:
    # 以“尽量不报错”的方式读取文本文件：
    # 1) 先按 utf-8 / utf-8-sig 尝试严格解码
    # 2) 失败则用 utf-8 + replace 兜底，避免因个别非法字节导致流程中断
    data = path.read_bytes()
    for enc in ["utf-8", "utf-8-sig"]:
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def _load_app_header(app_config_yaml: Path) -> AppHeader:
    # 从 app_config.yaml 中提取页眉所需字段：
    # - app.application_display_name
    # - app.app_version
    # 说明：为了最大可迁移性，这里不依赖 PyYAML，而是做一个足够稳定的最小解析。
    text = _read_text_lossy(app_config_yaml)
    display_name: str | None = None
    app_version: str | None = None

    # 仅在顶层键 app: 下读取二级缩进的键值对
    in_app = False
    for raw in text.splitlines():
        # 统一去掉行尾换行符，便于后续判断缩进与分割
        line = raw.rstrip("\n").rstrip("\r")
        # 空行或注释行直接跳过
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # 顶层键：用于判断是否进入 app: 区块
        if not line.startswith(" "):
            in_app = line.strip() == "app:"
            continue
        # 只有 app: 区块中的内容才解析
        if not in_app:
            continue
        # 限定为二级缩进（形如 “  key: value”），避免错误解析其他层级
        if not line.startswith("  "):
            continue
        # 提取 “key: value”
        key_val = line.strip()
        if ":" not in key_val:
            continue
        k, v = key_val.split(":", 1)
        k = k.strip()
        v = v.strip()
        # 处理 YAML 中可能出现的单/双引号包裹
        if v.startswith('"') and v.endswith('"') and len(v) >= 2:
            v = v[1:-1]
        if v.startswith("'") and v.endswith("'") and len(v) >= 2:
            v = v[1:-1]
        # 仅提取关心的字段
        if k == "application_display_name":
            display_name = v
        elif k == "app_version":
            app_version = v
        # 两个字段均读取到后即可提前结束
        if display_name is not None and app_version is not None:
            break

    # 关键字段缺失时直接报错，避免生成的手册页眉不合规且难以追踪原因
    if display_name is None:
        raise ValueError("app_config.yaml 缺少 app.application_display_name")
    if app_version is None:
        raise ValueError("app_config.yaml 缺少 app.app_version")
    return AppHeader(display_name=display_name, app_version=app_version)


# 截图文件名格式：章节号-序号 图名.扩展名（空格可有可无）
# 例：3-2填写人口学信息（错误日期）.png
_IMG_RE = re.compile(r"^(\d+)-(\d+)\s*(.+?)\.(png|jpg|jpeg)$", re.IGNORECASE)


def _scan_images(manual_dir: Path) -> dict[int, list[tuple[int, Path, str]]]:
    # 扫描截图目录，将图片按章节分组：
    # 返回结构：{chapter: [(order, path, title), ...]}
    groups: dict[int, list[tuple[int, Path, str]]] = {}
    for p in manual_dir.iterdir():
        # 只处理文件，目录/其他项忽略
        if not p.is_file():
            continue
        # 只处理符合命名规范的图片
        m = _IMG_RE.match(p.name)
        if not m:
            continue
        # 解析章节号、图序号、图名（作为图注与扩展说明输入）
        chapter = int(m.group(1))
        order = int(m.group(2))
        title = m.group(3).strip()
        groups.setdefault(chapter, []).append((order, p, title))

    # 每个章节内按序号排序，保证输出顺序稳定
    for ch in groups:
        groups[ch].sort(key=lambda x: x[0])
    return groups


def _escape_tex(s: str) -> str:
    # 将普通文本转为可安全插入 LaTeX 的形式，避免特殊字符导致编译失败
    t = s
    t = t.replace("\\", r"\textbackslash{}")
    t = t.replace("{", r"\{")
    t = t.replace("}", r"\}")
    t = t.replace("$", r"\$")
    t = t.replace("&", r"\&")
    t = t.replace("#", r"\#")
    t = t.replace("_", r"\_")
    t = t.replace("%", r"\%")
    t = t.replace("~", r"\textasciitilde{}")
    t = t.replace("^", r"\textasciicircum{}")
    return t


def _read_png_width_px(data: bytes) -> int | None:
    # 读取 PNG 像素宽度（不依赖第三方库）：
    # PNG 头 8 字节固定；其后第一个 chunk 常为 IHDR，宽度位于 IHDR 数据的前 4 字节
    if len(data) < 24:
        return None
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if data[12:16] != b"IHDR":
        return None
    return int.from_bytes(data[16:20], "big", signed=False)


def _read_jpeg_width_px(data: bytes) -> int | None:
    # 读取 JPEG 像素宽度（不依赖第三方库）：
    # JPEG 由若干段（marker）组成，宽高通常在 SOF（Start Of Frame）段里
    if len(data) < 4:
        return None
    if data[:2] != b"\xff\xd8":
        return None
    # 从 SOI 后开始扫描 marker 段
    i = 2
    while i + 4 <= len(data):
        # JPEG 段以 0xFF 开头；若遇到非 0xFF 则向前推进继续找
        if data[i] != 0xFF:
            i += 1
            continue
        # 跳过填充的 0xFF
        while i < len(data) and data[i] == 0xFF:
            i += 1
        if i >= len(data):
            break
        marker = data[i]
        i += 1
        # EOI（0xD9）与 SOS（0xDA）后不再包含 SOF 信息，可停止
        if marker == 0xD9 or marker == 0xDA:
            break
        # 每个段通常有 2 字节长度字段（包含长度字段本身）
        if i + 2 > len(data):
            break
        seg_len = int.from_bytes(data[i : i + 2], "big", signed=False)
        if seg_len < 2:
            return None
        seg_start = i + 2
        seg_end = seg_start + (seg_len - 2)
        if seg_end > len(data):
            break

        # 常见的 SOF 标记集合：这些段包含图像精度/高度/宽度
        is_sof = marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }
        # SOF 段格式：P(1) + Y(2) + X(2) + ...，因此宽度位于 seg_start+5:seg_start+7
        if is_sof and seg_end - seg_start >= 7:
            width = int.from_bytes(data[seg_start + 5 : seg_start + 7], "big", signed=False)
            return width

        # 跳到下一个段
        i = seg_end
    return None


def _read_image_width_px(path: Path) -> int | None:
    # 读取图片像素宽度：先尝试按 PNG 解析，失败再按 JPEG 解析
    try:
        data = path.read_bytes()
    except Exception:
        return None

    w = _read_png_width_px(data)
    if w is not None:
        return w
    w = _read_jpeg_width_px(data)
    if w is not None:
        return w
    return None


# 严正声明文本（保持红色输出）
STRICT_STATEMENT = (
    "严正声明：\n"
    "该软件旨在为用户提供医疗相关的辅助工具，不能将其视为专业医疗服务或其替代品。无论用户在使用本软件时获得了何种信息或建议，都应以专业医护人员为准。"
    "用户在使用本软件时，应明确其辅助性质，避免产生误解或依赖。任何个人和组织使用本软件必须遵守相关法律法规，应自行承担因使用软件而产生的所有风险和责任。"
    "软件著作权人对于因使用本软件而可能导致的任何直接或间接损失、损害或伤害，均不承担任何法律责任；对于可能存在的侵权行为，保留一切追溯的权利。"
)


def _build_tex(
    app_header: AppHeader,
    manual_dir: Path,
    groups: dict[int, list[tuple[int, Path, str]]],
    out_tex: Path,
    publish_date_cn: str,
) -> str:
    # 生成整份 LaTeX 文档字符串：
    # - 封面、目录、各章节内容
    # - 图片按像素宽度分档设置版心占比
    # - 章节说明文字按图名做扩展（更接近“手册说明”的材料形态）
    section_titles = {
        1: "前言与严正声明",
        2: "登录与注册",
        3: "主页面与报告生成",
        4: "常用计算器",
        5: "患者信息存档",
        6: "设置",
        7: "顶部导航栏",
        8: "附录（软件信息声明）",
    }

    def _infer_fig_width(image_abs_path: Path) -> float:
        # 根据图片像素宽度映射到 LaTeX 的相对宽度（\textwidth 比例）
        # - ≤600：1/3
        # - 601~1200：1/2
        # - 1200~1800：2/3
        # - >1800：3/4
        w = _read_image_width_px(image_abs_path)
        if w is None:
            return 0.75
        if w <= 600:
            return 0.33
        if w <= 1200:
            return 0.50
        if w <= 1800:
            return 0.67
        return 0.75

    def _figure_description(ch: int, title: str) -> str:
        # 根据章节与图名生成“图下说明文字”
        # 说明：这里不试图做完美的自然语言理解，而是用一组稳定的匹配规则覆盖当前项目截图集。
        t = title.strip()

        def p(s: str) -> str:
            # 将单段说明转义后，追加两个换行，形成 LaTeX 的段落分隔
            return _escape_tex(s).strip() + "\n\n"

        if ch == 2:
            if "登录页面" in t:
                return (
                    p("本图展示软件的登录入口。医师在该界面输入 Doctor_ID 与 Password 后即可发起登录。")
                    + p("登录流程采用本地账号库校验，便于在离线环境中使用，同时保证操作者身份可追溯。")
                )
            if "尝试登录" in t:
                return (
                    p("本图展示用户提交登录信息后的反馈过程。系统会对账号与密码进行匹配校验，并在失败时给出明确提示。")
                    + p("系统会对空输入、明显不合法的字符和格式进行拦截，减少无效请求与误操作。")
                )
            if "字符校验" in t:
                return (
                    p("本图展示用户名与密码的字符校验策略。系统限制输入字符范围与长度，避免不可见字符与异常格式造成登录失败。")
                    + p("系统在输入阶段进行即时校验并提示原因，引导用户按规范填写，降低注册与登录的学习成本。")
                )
            if "注册账号" in t and "成功" not in t:
                return (
                    p("本图展示医师注册界面。用户按提示填写 Doctor_ID 与密码等信息后提交注册。")
                    + p("注册信息会进行唯一性检查与格式校验，避免重复账号、弱密码或不合规字符导致后续无法登录。")
                )
            if "注册账号成功" in t:
                return (
                    p("本图展示注册成功后的结果提示。系统完成账号写入本地账号库，并提示用户可使用新账号登录。")
                    + p("该流程确保账号体系可在无网络条件下运行，同时便于院内离线环境快速部署。")
                )
            return p("本图展示登录/注册流程中的关键界面与提示信息，用于帮助用户完成身份验证与账号管理。")

        if ch == 3:
            if "主页面" in t:
                return (
                    p("本图展示主页面的整体布局。左侧为功能导航，右侧为患者信息录入与计算结果展示区域。")
                    + p("主流程围绕“数据录入—校验换算—衍生计算—分型解释—报告归档”展开，减少在多个系统间反复切换。")
                )
            if "错误日期弹窗" in t:
                return (
                    p("本图展示错误日期触发的提示弹窗。系统会明确指出错误原因并提示用户修正。")
                    + p("弹窗会阻断错误数据进入计算流程，确保衍生指标（如病程、年龄相关提示）与分型输入的可靠性。")
                )
            if "错误日期" in t:
                return (
                    p("本图展示在人口学信息录入时输入错误日期的场景。系统会在用户提交或离开输入框时触发校验。")
                    + p("系统对日期格式与取值范围进行限制，避免出生日期异常导致年龄计算错误，从而影响后续指标与报告。")
                )
            if "BMI" in t:
                return (
                    p("本图展示身高体重录入后 BMI 的自动计算结果。用户填写身高与体重后，系统会实时更新 BMI。")
                    + p("系统对身高体重进行合理范围校验，避免单位或小数点误填导致 BMI 异常。")
                )
            if "并发症" in t and "其他" not in t:
                return (
                    p("本图展示并发症/合并症信息的结构化录入。用户可按临床常见条目进行勾选，快速完成信息补全。")
                    + p("结构化输入便于报告生成与归档检索，同时减少自由文本导致的信息遗漏与表达不一致。")
                )
            if "其他" in t:
                return (
                    p("本图展示“其他”并发症的自定义录入方式。当预置条目无法覆盖时，用户可手动补充。")
                    + p("该设计在保留灵活性的同时维持数据结构化，避免仅靠自由文本导致关键字段缺失。")
                )
            if "实验室指标" in t:
                return (
                    p("本图展示实验室指标录入界面。系统提供上下限提示与单位选择，并可进行常用单位换算。")
                    + p("系统对关键指标进行范围校验与缺失提示，减少手工换算错误与漏填风险，提高分型输入的可用性。")
                )
            if "报告和归档" in t:
                return (
                    p("本图展示报告生成与归档入口。用户点击后可在下方查看分型结果、重点提示与摘要信息。")
                    + p("归档会将本次评估的输入与结果以 JSON 形式写入本地目录，便于随访复核与科研整理。")
                )
            if "导出成html" in t:
                return (
                    p("本图展示将报告导出为 HTML 的功能。导出后可在浏览器中直接打开，便于在院内电脑快速展示。")
                    + p("导出内容默认不包含“医师诊疗备注”，降低敏感信息外泄风险。")
                )
            if "打印" in t and "结果" not in t:
                return (
                    p("本图展示点击打印按钮后呼出的打印对话流程。用户可选择打印机或保存为 PDF。")
                    + p("该功能用于将标准化结果快速形成可共享的纸质或电子材料。")
                )
            if "打印结果" in t:
                return (
                    p("本图展示打印输出的 PDF 效果示例。输出内容为标准化报告摘要，并可用于病历整理或讨论。")
                    + p("隐私与合规考虑：打印结果不包含医师备注，避免将个人判断性内容写入外发材料。")
                )
            if "医师备注" in t:
                return (
                    p("本图展示医师诊疗备注的录入区域。该备注仅在本地可见，用于记录个体化判断与处置要点。")
                    + p("隐私与合规考虑：导出报告时可选择不包含该备注，避免在外发材料中泄露敏感信息。")
                )
            return p("本图展示主页面核心流程中的关键操作与提示信息，用于保证输入可靠、计算准确、输出可追溯。")

        if ch == 4:
            if "常用计算器" in t:
                return p("本图展示常用计算器入口页。该模块将常见的临床计算集中在同一处，减少在多处工具间切换。")
            if "BMI计算器" in t:
                return p("本图展示 BMI 计算器。输入身高与体重后即时得到 BMI，用于快速评估体重状态。")
            if "病程计算器输入年份" in t:
                return (
                    p("本图展示病程计算器的粗略计算方式。用户输入年份信息即可得到大致病程，用于快速记录。")
                    + p("系统会限制年份范围并提示异常输入，避免误填导致病程偏差。")
                )
            if "病程计算器输入具体时间" in t or "肾小球滤过率" in t:
                return (
                    p("本图展示病程计算器的精确计算方式，并同时给出肾小球滤过率（eGFR）估算结果。")
                    + p("eGFR 提供多种常用公式并行输出，便于在不同临床习惯下进行比对与参考。")
                )
            if "单位换算" in t or "HbA1c" in t:
                return (
                    p("本图展示血糖单位换算与 HbA1c 估算功能。系统提供常用单位间换算，减少手动计算。")
                    + p("系统对输入范围做合理性校验，并提示单位选择，降低因单位误选造成的错误解读。")
                )
            if "CGM" in t and "导出文件" in t:
                return (
                    p("本图展示 CGM 动态计算器的文件导入过程。用户选择 Excel/CSV 文件后，系统自动识别日期时间列与血糖数值列。")
                    + p("系统会对缺列、格式不一致或时间排序异常的情况进行提示，避免将不可用数据带入统计计算。")
                )
            if "CGM计算结果" in t:
                return (
                    p("本图展示 CGM 动态计算器的结果输出。系统计算整段记录的关键指标，并给出“文档记载天数”等摘要信息。")
                    + p("该结果用于辅助评估血糖波动与低/高血糖风险，支持临床讨论与随访对比。")
                )
            return p("本图展示常用计算器模块中的关键功能，用于在临床场景下快速完成常见计算与结果记录。")

        if ch == 5:
            if "记录存档" in t:
                return (
                    p("本图展示患者信息记录的存档页面。每次评估会写入 1 个 JSON 文件，包含输入与计算结果。")
                    + p("同一 Patient_ID 在短时间内重复保存会覆盖最新一次，减少误点导致的重复文件堆积。")
                )
            if "打开归档目录" in t:
                return (
                    p("本图展示“打开归档目录”功能。点击后直接定位到本地数据保存路径，便于备份与导入。")
                    + p("该设计降低了用户查找 AppData 路径的成本，适合院内多机部署与维护。")
                )
            if "读取归档" in t or "回填" in t:
                return (
                    p("本图展示读取既往归档并自动回填信息的能力。复诊时可快速复用固定信息并更新与就诊时间相关的字段。")
                    + p("系统会对回填数据进行一致性检查，避免旧数据与当前时间不匹配造成误用。")
                )
            return p("本图展示患者归档的浏览、读取与回填流程，用于支撑随访复核与科研数据整理。")

        if ch == 6:
            if "设置和程序保存路径" in t:
                return (
                    p("本图展示设置页面与程序数据保存路径。系统将日志、配置与归档数据写入用户 AppData，便于权限隔离与维护。")
                    + p("系统使用标准路径避免写入受限目录导致保存失败，同时减少因手动选择路径引入的误操作。")
                )
            if "合法本地账户" in t or "哈希" in t:
                return (
                    p("本图展示本地账户记载与加密策略。账号信息以本地 JSON 形式保存，并对敏感字段进行哈希处理。")
                    + p("该设计在离线可用的前提下尽量降低明文泄露风险，同时满足身份校验与责任追溯需求。")
                )
            return p("本图展示设置模块的关键配置项，用于管理本地数据保存、账号信息与界面偏好。")

        if ch == 7:
            if "文件" in t:
                return p("本图展示顶部导航栏的“文件”菜单。用户可在此触发常用的打开、保存、导出等操作入口。")
            if "主题和字体" in t:
                return (
                    p("本图展示主题与字体设置入口。用户可在浅色/深色主题间切换，并调整字体大小以适配不同屏幕与距离。")
                    + p("字体大小调整以可逆的步进方式提供，避免一次性改动过大导致界面难以阅读。")
                )
            if "拓展" in t:
                return p("本图展示导航栏扩展说明入口。该区域集中放置算法/工具说明，便于用户在使用时随时查阅。")
            if "聚类原则" in t:
                return p("本图展示分型聚类原则说明。用于解释分型的基本依据与结果含义，帮助医师正确解读输出。")
            if "计算器说明" in t:
                return p("本图展示计算器说明信息。用于提示公式来源、适用范围与注意事项，降低误用风险。")
            if "关于" in t:
                return p("本图展示“关于”页面入口，用于查看软件简介、版本信息与相关说明。")
            if "版本信息" in t:
                return p("本图展示版本信息页面。用于记录软件版本与模型版本，便于在报告归档与问题追溯时明确依据。")
            if "开发信息" in t:
                return p("本图展示开发信息页面。用于列出开发者与所属单位等信息，便于维护与对外沟通。")
            if "联系开发者" in t:
                return p("本图展示联系开发者方式。用户可通过邮件反馈问题或提出需求，形成持续迭代闭环。")
            return p("本图展示顶部导航栏的功能入口与说明信息，用于提升可用性与可解释性。")

        return p("本图展示软件运行过程中的关键界面与操作说明。")

    def fig_block(ch: int, idx: int, image_abs_path: Path, rel_path: str, caption: str) -> str:
        # 生成单张图片的 LaTeX 块：
        # 1) figure 环境 + 居中 + includegraphics（按像素宽度分档）
        # 2) caption（图注）
        # 3) 图下扩展说明段落（来自 _figure_description）
        cap = _escape_tex(caption)
        width = _infer_fig_width(image_abs_path)
        desc = _figure_description(ch, caption)
        return (
            "\\begin{figure}[H]\n"
            "\\centering\n"
            f"\\includegraphics[width={width:.2f}\\textwidth]{{{rel_path}}}\n"
            f"\\caption{{{cap}}}\n"
            "\\end{figure}\n\n"
            f"{desc}"
        )

    # 生成 LaTeX 引用图片的相对路径前缀（TeX 内统一使用 posix 风格路径分隔符）
    manual_rel = manual_dir.as_posix().rstrip("/") + "/"

    # 用列表拼接全文，避免大字符串频繁拼接的开销，同时结构更清晰
    tex_parts: list[str] = []
    tex_parts.append(
        rf"""\documentclass[12pt,a4paper]{{article}}
\usepackage[a4paper,top=2.5cm,bottom=2.5cm,left=2cm,right=2cm,includeheadfoot]{{geometry}}
\usepackage{{fontspec}}
\usepackage{{xeCJK}}
\setmainfont{{Times New Roman}}
\IfFontExistsTF{{SimSun}}{{\setCJKmainfont{{SimSun}}}}{{\setCJKmainfont{{Microsoft YaHei}}}}
\usepackage{{xcolor}}
\usepackage{{graphicx}}
\usepackage{{float}}
\usepackage{{caption}}
\usepackage{{fancyhdr}}
\usepackage{{lastpage}}
\usepackage{{chngcntr}}

\setlength{{\parindent}}{{2em}}
\setlength{{\parskip}}{{0.3em}}
\setlength{{\headheight}}{{14.5pt}}

\renewcommand{{\contentsname}}{{目录}}
\renewcommand{{\figurename}}{{图}}
\counterwithin{{figure}}{{section}}
\renewcommand{{\thefigure}}{{\thesection-\arabic{{figure}}}}
\captionsetup{{font=small,labelfont=bf}}

\pagestyle{{fancy}}
\fancyhf{{}}
\fancyhead[C]{{{_escape_tex(app_header.header_text())}}}
\fancyfoot[C]{{第\thepage 页/共 \pageref{{LastPage}} 页}}

\newcommand{{\SCLine}}[2]{{%
  \noindent\llap{{\makebox[1.6cm][r]{{\fontsize{{8}}{{8}}\selectfont #1}}\hspace{{0.3cm}}}}%
  {{\fontsize{{8}}{{9}}\selectfont #2}}\par
}}

\begin{{document}}
"""
    )

    # 封面：标题/手册名/版本号/发布日期/单位
    tex_parts.append(
        f"""
\\thispagestyle{{empty}}
\\begin{{center}}
{{\\fontsize{{26}}{{32}}\\selectfont {_escape_tex(app_header.display_name)}}}\\par
\\vspace{{1.2cm}}
{{\\fontsize{{22}}{{28}}\\selectfont 用户手册}}\\par
\\vfill
{{\\fontsize{{12}}{{16}}\\selectfont 版本号：{_escape_tex(app_header.version_label())}}}\\par
\\vspace{{0.2cm}}
{{\\fontsize{{12}}{{16}}\\selectfont 发布日期：{_escape_tex(publish_date_cn)}}}\\par
\\vspace{{0.2cm}}
{{\\fontsize{{12}}{{16}}\\selectfont 西安交通大学第一附属医院}}\\par
\\end{{center}}
\\clearpage
"""
    )

    # 目录页：仅到一级目录（section）
    tex_parts.append(
        r"""
\pagenumbering{arabic}
\setcounter{page}{1}
\setcounter{tocdepth}{1}
\tableofcontents
\clearpage
"""
    )

    # 第 1 节：前言正文 + 严正声明（红色），其后换页进入第 2 节
    tex_parts.append(f"\\section{{{_escape_tex(section_titles[1])}}}\n")
    tex_parts.append(
        "本软件面向临床医师，在住院场景下对 2 型糖尿病患者进行快速评估与分型管理，提供“数据录入—校验换算—衍生计算—分型解释—报告归档”的一体化流程。\n\n"
        "在患者信息录入环节，系统支持人口学信息、病程、并发症/合并症与关键实验室指标的结构化录入，并对核心输入执行范围校验、缺失提示与单位换算，减少手工换算错误与漏填风险。系统自动计算 BMI、TyG 与 eGFR 等衍生指标，并基于 TyG/eGFR/ALB 三维特征进行四表型分型判别，输出结果解释与管理重点提示。报告可导出与打印，患者完整数据与结果将以 JSON 形式归档保存，便于随访复核与科研整理。软件采用本地离线运行方式，降低网络依赖并保护患者隐私。\n\n"
        "本手册用于说明软件的主要功能模块与典型操作流程，手册中所有界面截图均来自软件实际运行过程。\n\n"
    )
    tex_parts.append("{\\color{red}\n" + _escape_tex(STRICT_STATEMENT).replace("\n", "\n\n") + "\n}\n\n")
    tex_parts.append("\\newpage\n")

    # 第 2~7 节：每节先输出概述文字，再按截图顺序输出图片 + 说明
    for ch in [2, 3, 4, 5, 6, 7]:
        tex_parts.append(f"\\section{{{_escape_tex(section_titles[ch])}}}\n")

        # 各节的概述段落（写成固定文案，便于保持手册“可读性”与“稳定性”）
        if ch == 2:
            tex_parts.append(
                "本节介绍医师登录与注册流程。登录页面仅需填写 Doctor\\_ID 与 Password。当前版本采用本地账号库进行校验，后续可扩展为远程数据库认证。\n\n"
            )
        elif ch == 3:
            tex_parts.append(
                "本节介绍主页面中的患者信息录入、数据校验与单位换算、衍生指标计算、分型结果输出、报告生成与归档等核心流程。\n\n"
            )
        elif ch == 4:
            tex_parts.append(
                "本节介绍常用计算器页面，包含 BMI、病程估算、eGFR 多公式输出、单位换算以及 CGM 动态计算器等。\n\n"
            )
        elif ch == 5:
            tex_parts.append(
                "本节介绍患者归档 JSON 的浏览与回填功能，以及打开归档目录与外部归档读取等操作。\n\n"
            )
        elif ch == 6:
            tex_parts.append(
                "本节介绍设置页面，包括程序数据保存路径（AppData）与本地账号库位置等信息。\n\n"
            )
        elif ch == 7:
            tex_parts.append(
                "本节介绍顶部导航栏的各项菜单功能：文件、主题与字体、扩展说明与关于信息等。\n\n"
            )

        # 遍历当前章节的图片，按序号输出
        figs = groups.get(ch, [])
        for idx, (_, pth, title) in enumerate(figs, start=1):
            # TeX 里引用图片走相对路径，避免与 repo-root 绑定
            rel = (Path(manual_rel) / pth.name).as_posix()
            # 图注与说明的输入源：文件名中的“图名”
            cap = title
            tex_parts.append(fig_block(ch, idx, pth, rel, cap))

        # 章节之间留一个空行（让生成的 TeX 更易读）
        tex_parts.append("\n")

    # 第 8 节（附录）：单独一页，最后一句另起段
    tex_parts.append("\\newpage\n")
    tex_parts.append(f"\\section{{{_escape_tex(section_titles[8])}}}\n")
    appendix_p1 = (
        "软件信息声明：\n"
        "本软件由强薇提出并领导开发进程，董睿青、谷立帆完成代码实现。所属单位西安交通大学第一附属医院对本软件宣称全部合法权利。"
        "如需开发者信息请联系 lifanguxjtu@outlook.com。"
    )
    appendix_p2 = "本软件的开发得到了西安交通大学第一附属医院内分泌代谢科的支持与指导。"
    tex_parts.append(_escape_tex(appendix_p1).replace("\n", "\n\n") + "\n\n")
    tex_parts.append(_escape_tex(appendix_p2) + "\n")

    # 文档结束
    tex_parts.append(r"\end{document}" + "\n")
    return "".join(tex_parts)


def compile_pdf(tex_path: Path, engine: str = "xelatex") -> Path:
    # 使用指定引擎（默认 xelatex）编译 TeX 为 PDF
    # 说明：为了让目录页码/总页数引用稳定，通常需要编译两次
    work_dir = tex_path.parent
    cmd = [engine, "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
    for _ in range(2):
        # capture_output=True：将编译日志捕获到内存，失败时一并抛出，便于排错
        p = subprocess.run(
            cmd,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if p.returncode != 0:
            raise RuntimeError(f"LaTeX 编译失败（{engine}）。\n\nSTDOUT:\n{p.stdout}\n\nSTDERR:\n{p.stderr}")
    # 约定输出 PDF 与 TeX 同名，仅后缀不同
    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        raise RuntimeError("LaTeX 编译完成但未找到输出 PDF：" + str(pdf_path))
    return pdf_path


def main() -> int:
    # 命令行入口：解析参数 → 扫描图片 → 生成 TeX → 编译 PDF → 输出文件路径
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=str, default="")
    parser.add_argument("--manual-dir", type=str, default="manual")
    parser.add_argument("--app-config", type=str, default="app_config.yaml")
    parser.add_argument("--project-name", type=str, default="Project")
    parser.add_argument("--out-tex", type=str, default="")
    parser.add_argument("--engine", type=str, default="xelatex")
    parser.add_argument("--publish-date-cn", type=str, default="")
    args = parser.parse_args()

    # repo_root：不传则取脚本所在目录向上两级作为“项目根目录”
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[1]
    # manual_dir/app_config 支持相对路径（相对于 repo_root）或绝对路径
    manual_dir = Path(args.manual_dir)
    manual_dir = manual_dir if manual_dir.is_absolute() else (repo_root / manual_dir)
    app_config_path = Path(args.app_config)
    app_config_path = app_config_path if app_config_path.is_absolute() else (repo_root / app_config_path)

    # 读取页眉文本所需的“软件名+版本号”
    app_header = _load_app_header(app_config_path)
    # 按命名规范扫描截图并分组排序
    groups = _scan_images(manual_dir)

    # 输出路径：默认写到 repo_root 下（SC_{项目名}_4_UserManual.tex）
    out_tex = Path(args.out_tex) if args.out_tex else (repo_root / f"SC_{args.project_name}_4_UserManual.tex")
    out_tex = out_tex.resolve()
    # 发布日期：允许外部传入；为空则用占位格式提示用户自行填写
    publish_date_cn = args.publish_date_cn.strip() or ""
    if not publish_date_cn:
        publish_date_cn = "YYYY年MM月DD日"

    # 生成 LaTeX 文本
    tex = _build_tex(
        app_header=app_header,
        manual_dir=manual_dir.relative_to(repo_root) if manual_dir.is_relative_to(repo_root) else manual_dir,
        groups=groups,
        out_tex=out_tex,
        publish_date_cn=publish_date_cn,
    )

    # 写入 TeX 文件（统一 LF 换行，便于跨平台/跨工具一致）
    out_tex.write_text(tex, encoding="utf-8", newline="\n")
    # 编译得到 PDF
    pdf = compile_pdf(out_tex, engine=args.engine)
    # 向标准输出写出产物路径，便于脚本被其他工具链调用
    print(str(out_tex))
    print(str(pdf))
    return 0


if __name__ == "__main__":
    # 作为脚本执行时，返回码交给操作系统
    raise SystemExit(main())
