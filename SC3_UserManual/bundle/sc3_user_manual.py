from __future__ import annotations

# 该脚本用于"软著用户手册"生成：批量截图 → 自动生成 LaTeX → 编译 PDF
# 设计目标：可复制到任意项目复用（尽量仅依赖 Python 标准库与 xelatex）

# 命令行参数解析（输入目录/输出路径/LaTeX 引擎等）
import argparse
# 文件名解析（按"章节-序号-图名"规范扫描截图）
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
        # 将版本号规范化为形如 "V1.0" 的格式
        v = self.app_version.strip()
        if v and not v.lower().startswith("v"):
            v = "V" + v
        return v

    def header_text(self) -> str:
        # 生成页眉文本："软件名 + 空格 + 版本号"
        return (self.display_name.strip() + " " + self.version_label()).strip()


def _read_text_lossy(path: Path) -> str:
    # 以"尽量不报错"的方式读取文本文件：
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
        # 限定为二级缩进（形如 "  key: value"），避免错误解析其他层级
        if not line.startswith("  "):
            continue
        # 提取 "key: value"
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


# 正式图注映射：将非正式图片文件名转为正式表述
# key 格式："章节号-序号 图名"（与文件名中去掉扩展名的部分一致）
_FORMAL_CAPTIONS: dict[str, str] = {
    "2-1登录界面": "登录界面",
    "2-2 错误账号或密码或不存在的账号弹窗": "账号或密码错误提示",
    "2-3 注册页面": "医师注册界面",
    "2-4 填写基本信息 最少都是6个字符": "注册信息填写与字符校验",
    "2-5账号保存弹窗": "账号注册成功提示",
    "3-1主页面": "软件主页面",
    "3-2可折叠的原生侧面导航栏": "可折叠侧面导航栏",
    "3-3常用计算器页面": "常用计算器页面",
    "3-4 归档json页面": "患者归档浏览页面",
    "3-5 关于以及相关信息页面": "关于与相关信息页面",
    "4-1 基本信息和体格填写": "患者基本信息与体格检查录入",
    "4-2日期纠错弹窗": "日期输入校验提示",
    "4-3 患者首次发病日期和病程自动换算，支持模糊计算和精确到月": "发病日期与病程自动换算",
    "4-4 仅填写病程信息可以自动补全发病时间": "病程信息自动补全发病时间",
    "4-5 选择并发症": "并发症与合并症选择",
    '4-6 勾选"其他"可以填空': "其他并发症自定义录入",
    "4-7 实验室指标自带单位换算": "实验室指标单位换算",
    "4-8 实验室指标计算防呆": "实验室指标输入校验",
    "4-9 点击生成并归档，获取聚类结果": "生成归档与代谢分型结果",
    "4-10 双模式的代谢分型": "双技术方案代谢表型识别结果",
    "4-11 结果可以导出为html": "报告导出为HTML格式",
    "4-12 导出的html": "HTML格式报告预览",
    "4-13 结果可以导出为pdf": "报告导出为PDF格式",
    "4-14 结果导出的pdf": "PDF格式报告预览",
    "5-1 计算器部分自动算BMI和WWI": "BMI与WWI自动计算",
    "5-2 病程计算": "糖尿病病程估算",
    "5-3 病程的精确计算": "病程精确计算",
    "5-4 男性的eGFR估算": "男性eGFR估算",
    "5-5 女性的eGFR估算": "女性eGFR估算",
    "5-6 血糖单位换算": "血糖单位换算",
    "5-7 HbA1c估算与换算": "HbA1c估算与换算",
    "5-8 动态血糖检测指标计算": "CGM动态血糖指标计算",
    "5-9 CGM计算结果（部分）": "CGM计算结果输出",
    "6-1 患者归档界面以及预览": "患者归档列表与预览",
    "6-2 点击刷新按钮读取当前文件夹全部文件": "刷新读取归档文件列表",
    "7-1 UI字体缩小": "界面字体缩小设置",
    "7-2 UI字体放大": "界面字体放大设置",
    "7-3 深浅色主题": "深色与浅色主题切换",
    "7-4 中英文双语UI切换": "中英文界面语言切换",
    "7-5 聚类说明": "代谢分型聚类原理说明",
    "7-6 计算器说明": "计算器使用说明",
    "7-7 自动跳转用户手册": "用户手册快捷入口",
}


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
    # - 章节说明文字按图名做扩展（更接近"手册说明"的材料形态）
    section_titles = {
        1: "前言与严正声明",
        2: "登录与注册",
        3: "主页面与功能导航",
        4: "患者信息录入与代谢分型",
        5: "常用计算器",
        6: "患者归档",
        7: "系统设置与说明",
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

    def _formal_caption(ch: int, order: int, raw_title: str) -> str:
        # 将非正式图名转为正式图注：
        # 先用 "章节号-序号 图名" 格式查映射表，命中则返回正式名称
        # 未命中则返回原始图名（兜底）
        key = f"{ch}-{order} {raw_title}"
        if key in _FORMAL_CAPTIONS:
            return _FORMAL_CAPTIONS[key]
        key_no_space = f"{ch}-{order}{raw_title}"
        if key_no_space in _FORMAL_CAPTIONS:
            return _FORMAL_CAPTIONS[key_no_space]
        return raw_title

    def _figure_description(ch: int, title: str) -> str:
        # 根据章节与图名生成"图下说明文字"
        # 说明：这里不试图做完美的自然语言理解，而是用一组稳定的匹配规则覆盖当前项目截图集。
        t = title.strip()

        def p(s: str) -> str:
            # 将单段说明转义后，追加两个换行，形成 LaTeX 的段落分隔
            return _escape_tex(s).strip() + "\n\n"

        if ch == 2:
            if "登录界面" in t:
                return (
                    p("本图展示软件的登录入口界面。医师在该界面输入 Doctor_ID 与 Password 后即可发起登录。")
                    + p("登录流程采用本地账号库校验，便于在离线环境中使用，同时保证操作者身份可追溯。")
                )
            if "错误账号" in t or "密码" in t or "不存在" in t:
                return (
                    p("本图展示账号或密码输入错误时的提示弹窗。系统会对账号与密码进行匹配校验，并在失败时给出明确提示。")
                    + p("系统会对空输入、明显不合法的字符和格式进行拦截，减少无效请求与误操作。")
                )
            if "注册页面" in t:
                return (
                    p("本图展示医师注册界面。用户按提示填写 Doctor_ID 与密码等信息后提交注册。")
                    + p("注册信息会进行唯一性检查与格式校验，避免重复账号、弱密码或不合规字符导致后续无法登录。")
                )
            if "基本信息" in t and "字符" in t:
                return (
                    p("本图展示注册信息填写时的字符校验策略。系统限制用户名与密码的最少字符数为6位，避免不可见字符与异常格式造成登录失败。")
                    + p("系统在输入阶段进行即时校验并提示原因，引导用户按规范填写，降低注册与登录的学习成本。")
                )
            if "账号保存" in t or "注册成功" in t:
                return (
                    p("本图展示注册成功后的结果提示。系统完成账号写入本地账号库，并提示用户可使用新账号登录。")
                    + p("该流程确保账号体系可在无网络条件下运行，同时便于院内离线环境快速部署。")
                )
            return p("本图展示登录/注册流程中的关键界面与提示信息，用于帮助用户完成身份验证与账号管理。")

        if ch == 3:
            if "主页面" in t:
                return (
                    p("本图展示软件主页面的整体布局。左侧为可折叠功能导航栏，右侧为当前选中页面的内容区域。")
                    + p("主页面集成了患者信息录入、常用计算器、归档浏览、设置等功能模块，用户可通过导航栏快速切换。")
                )
            if "导航栏" in t or "侧面" in t:
                return (
                    p("本图展示可折叠的侧面导航栏。用户点击折叠按钮后，导航栏收缩为图标模式，释放更多内容展示空间。")
                    + p("导航栏包含患者信息、常用计算器、归档、设置等入口，支持一键切换功能页面。")
                )
            if "计算器" in t:
                return (
                    p("本图展示常用计算器页面的入口。该模块将 BMI/WWI、病程估算、eGFR、单位换算、CGM 等临床计算集中在同一页面。")
                    + p("用户可在主页面通过导航栏进入计算器页面，快速完成常用指标的计算与换算。")
                )
            if "归档" in t and ("json" in t.lower() or "JSON" in t):
                return (
                    p("本图展示患者归档浏览页面。左侧为归档文件列表，右侧为选中文件的 JSON 内容预览。")
                    + p("用户可在此页面浏览、检索已归档的患者评估记录，并支持将归档数据重新加载回患者信息页。")
                )
            if "关于" in t:
                return (
                    p("本图展示关于与相关信息页面。该页面包含软件简介、版本信息、开发信息与联系方式等。")
                    + p("用户可在此查看软件版本号与模型版本号，便于在报告归档与问题追溯时明确依据。")
                )
            return p("本图展示主页面核心功能导航中的关键界面，用于帮助用户快速了解软件的整体布局与功能入口。")

        if ch == 4:
            if "基本信息" in t and "体格" in t:
                return (
                    p("本图展示患者基本信息与体格检查的录入界面。用户可填写姓名、年龄、性别、身高、体重、腰围等人口学信息与体格数据。")
                    + p("系统对身高、体重、腰围等数值进行合理范围校验，并在输入框失焦时即时提示异常，避免单位或小数点误填。")
                )
            if "日期纠错" in t or "日期" in t and "纠错" in t:
                return (
                    p("本图展示日期输入错误时触发的校验提示弹窗。系统会明确指出错误原因并提示用户修正。")
                    + p("弹窗会阻断错误数据进入计算流程，确保衍生指标（如病程、年龄相关提示）与分型输入的可靠性。")
                )
            if "发病日期" in t and "病程" in t and "换算" in t:
                return (
                    p("本图展示发病日期与病程的自动换算功能。用户输入首次发病日期后，系统自动计算病程；支持模糊计算（仅年份）和精确到月的计算方式。")
                    + p("该功能减少了手动换算病程的工作量，同时保证病程数据与发病日期的一致性。")
                )
            if "病程" in t and "补全" in t:
                return (
                    p("本图展示仅填写病程信息后系统自动补全发病时间的功能。当用户仅输入病程年数时，系统反向推算首次发病日期。")
                    + p("该设计适应不同临床记录习惯，无论从日期还是病程角度输入，均可获得完整的时间信息。")
                )
            if "并发症" in t and "其他" not in t:
                return (
                    p("本图展示并发症与合并症的结构化选择界面。用户可按临床常见条目进行勾选，快速完成信息补全。")
                    + p("结构化输入便于报告生成与归档检索，同时减少自由文本导致的信息遗漏与表达不一致。")
                )
            if "其他" in t and "填空" in t:
                return (
                    p('本图展示"其他"并发症的自定义录入方式。当预置条目无法覆盖时，用户可勾选"其他"后手动填写具体内容。')
                    + p("该设计在保留灵活性的同时维持数据结构化，避免仅靠自由文本导致关键字段缺失。")
                )
            if "单位换算" in t:
                return (
                    p("本图展示实验室指标录入时内置的单位换算功能。系统支持血糖、肌酐等常用指标的单位自动换算，减少手工计算。")
                    + p("系统对关键指标进行范围校验与缺失提示，减少手工换算错误与漏填风险，提高分型输入的可用性。")
                )
            if "防呆" in t or "输入校验" in t:
                return (
                    p("本图展示实验室指标输入的防呆校验机制。系统对超出合理范围的数值即时提示，防止因误填导致后续计算与分型结果偏差。")
                    + p("校验在用户离开输入框时触发，不影响正常输入流程，同时显著降低手工录入错误率。")
                )
            if "生成" in t and "归档" in t:
                return (
                    p('本图展示点击\u201c生成并归档\u201d按钮后获取代谢分型结果的界面。系统基于输入指标完成计算与分型判别，输出表型分类与管理要点提示。')
                    + p("归档会将本次评估的输入与结果以 JSON 形式写入本地目录，便于随访复核与科研整理。")
                )
            if "双模式" in t or "双技术" in t:
                return (
                    p("本图展示双技术方案代谢表型识别的结果对比。系统同时输出 TyG-eGFR-ALB 与 TyG-WWI-ALB 两种方案的分型结果。")
                    + p('两种方案均采用标准化（z-score）处理后按\u201c质心最近原则\u201d将患者归入四类代谢表型，每类表型对应明确的临床特征与诊疗重点提示。')
                )
            if "导出" in t and "html" in t.lower():
                return (
                    p("本图展示将分型报告导出为 HTML 格式的功能。导出后可在浏览器中直接打开，便于在院内电脑快速展示与分享。")
                    + p("HTML 报告包含患者基本信息、输入指标、计算结果、表型判别依据及个体化诊疗建议。")
                )
            if "导出的html" in t or "HTML格式" in t:
                return (
                    p("本图展示导出的 HTML 格式报告在浏览器中的预览效果。报告结构清晰，包含完整的评估信息与分型结果。")
                    + p("HTML 格式便于在院内网络环境中快速传递与查看，同时不依赖特定软件打开。")
                )
            if "导出" in t and "pdf" in t.lower() and "预览" not in t:
                return (
                    p("本图展示将分型报告导出为 PDF 格式的功能。PDF 格式适合打印归档与病历留存。")
                    + p('文件名默认采用\u201c患者ID_时间戳\u201d格式，确保唯一性与可追溯性。')
                )
            if "导出的pdf" in t or "PDF格式" in t:
                return (
                    p("本图展示导出的 PDF 格式报告的预览效果。输出内容为标准化报告摘要，可用于病历整理或临床讨论。")
                    + p("PDF 报告格式规范，包含完整的评估信息，适合作为病历附件归档保存。")
                )
            return p("本图展示患者信息录入与代谢分型流程中的关键操作与提示信息，用于保证输入可靠、计算准确、输出可追溯。")

        if ch == 5:
            if "BMI" in t and "WWI" in t:
                return (
                    p("本图展示 BMI 与 WWI 的自动计算功能。用户输入身高、体重后，系统即时计算体质指数（BMI）与腰围身高比（WWI）。")
                    + p("BMI 与 WWI 均为临床常用体型评估指标，系统自动完成计算，减少手工换算负担。")
                )
            if "病程" in t and "精确" not in t:
                return (
                    p("本图展示糖尿病病程估算功能。用户输入首次发病年份等信息后，系统自动计算病程，支持模糊计算方式。")
                    + p("系统会限制年份范围并提示异常输入，避免误填导致病程偏差。")
                )
            if "病程" in t and "精确" in t:
                return (
                    p("本图展示病程的精确计算方式。用户输入具体的首次发病日期后，系统精确计算病程至月。")
                    + p("精确计算适用于需要记录详细病程信息的临床场景，如科研数据整理与随访评估。")
                )
            if "男性" in t and "eGFR" in t:
                return (
                    p("本图展示男性 eGFR 估算结果。系统支持 CKD-EPI、MDRD 等多种常用公式并行输出，便于在不同临床习惯下进行比对与参考。")
                    + p("eGFR 是评估肾功能的重要指标，系统根据性别与肌酐值自动选择对应公式进行计算。")
                )
            if "女性" in t and "eGFR" in t:
                return (
                    p("本图展示女性 eGFR 估算结果。与男性估算类似，系统根据性别采用对应系数进行计算。")
                    + p("多公式并行输出的设计便于医师在不同指南要求下选择合适的估算结果。")
                )
            if "血糖单位换算" in t:
                return (
                    p("本图展示血糖单位换算功能。系统支持 mmol/L 与 mg/dL 之间的快速换算，减少手动计算。")
                    + p("系统对输入范围做合理性校验，并提示单位选择，降低因单位误选造成的错误解读。")
                )
            if "HbA1c" in t:
                return (
                    p("本图展示 HbA1c 估算与换算功能。系统提供糖化血红蛋白与平均血糖之间的换算关系，便于临床评估。")
                    + p("该功能支持在不同检测指标间进行快速转换，辅助医师综合判断血糖控制情况。")
                )
            if "CGM" in t and "计算" in t and "结果" not in t:
                return (
                    p("本图展示 CGM 动态血糖指标计算界面。用户导入 Excel/CSV 格式的连续血糖监测数据后，系统自动识别日期时间列与血糖数值列。")
                    + p("系统会对缺列、格式不一致或时间排序异常的情况进行提示，避免将不可用数据带入统计计算。")
                )
            if "CGM" in t and "结果" in t:
                return (
                    p("本图展示 CGM 动态血糖指标的计算结果输出。系统计算平均血糖、血糖变异系数、高/低血糖时间占比等关键指标。")
                    + p("该结果用于辅助评估血糖波动与低/高血糖风险，支持临床讨论与随访对比。")
                )
            return p("本图展示常用计算器模块中的关键功能，用于在临床场景下快速完成常见计算与结果记录。")

        if ch == 6:
            if "归档" in t and "预览" in t:
                return (
                    p("本图展示患者归档列表与预览界面。左侧列出已归档的 JSON 文件，右侧显示选中文件的详细内容预览。")
                    + p("用户可在此浏览所有历史评估记录，支持按文件名检索与内容查看，便于随访复核与科研数据整理。")
                )
            if "刷新" in t:
                return (
                    p("本图展示点击刷新按钮后读取当前归档文件夹全部文件的功能。系统重新扫描归档目录，更新文件列表。")
                    + p("该功能适用于在外部添加或修改归档文件后，同步更新界面显示的场景。")
                )
            return p("本图展示患者归档的浏览与检索流程，用于支撑随访复核与科研数据整理。")

        if ch == 7:
            if "字体缩小" in t:
                return (
                    p("本图展示界面字体缩小设置的效果。用户可在设置页面调整字体大小，以适配不同屏幕分辨率与使用距离。")
                    + p("字体大小调整以可逆的步进方式提供，避免一次性改动过大导致界面难以阅读。")
                )
            if "字体放大" in t:
                return (
                    p("本图展示界面字体放大设置的效果。放大后的字体更易于远距离或高分辨率屏幕下的阅读。")
                    + p("字体调整即时生效，无需重启软件，方便用户根据实际需求灵活调整。")
                )
            if "深浅色" in t or "主题" in t:
                return (
                    p("本图展示深色与浅色主题的切换效果。用户可在设置页面选择偏好主题，软件界面将即时切换配色方案。")
                    + p("深色主题适用于暗光环境，浅色主题适用于明亮环境，主题切换不影响功能与数据。")
                )
            if "双语" in t or "语言" in t:
                return (
                    p("本图展示中英文界面语言切换功能。用户可在设置页面选择中文或英文界面，所有菜单与提示将即时切换。")
                    + p("双语支持便于不同语言背景的医师使用，同时满足国际化交流需求。")
                )
            if "聚类" in t and "说明" in t:
                return (
                    p("本图展示代谢分型聚类原理的说明页面。该页面解释了分型的基本依据、特征向量构成与质心最近原则的含义。")
                    + p("说明信息帮助医师正确解读分型输出，避免对结果产生误解或过度依赖。")
                )
            if "计算器说明" in t:
                return (
                    p("本图展示计算器使用说明页面。该页面提示各计算功能的公式来源、适用范围与注意事项。")
                    + p("说明信息用于降低误用风险，帮助医师理解计算结果的临床含义与局限性。")
                )
            if "用户手册" in t:
                return (
                    p("本图展示用户手册的快捷入口。用户点击后可自动跳转至用户手册文件，便于随时查阅操作说明。")
                    + p("该入口降低了查找手册的成本，适合首次使用或需要回顾操作流程的场景。")
                )
            return p("本图展示系统设置与说明模块的关键配置项，用于管理界面偏好与查阅功能说明。")

        return p("本图展示软件运行过程中的关键界面与操作说明。")

    def fig_block(ch: int, order: int, image_abs_path: Path, rel_path: str, raw_title: str) -> str:
        # 生成单张图片的 LaTeX 块：
        # 1) figure 环境 + 居中 + includegraphics（按像素宽度分档）
        # 2) caption（图注，使用正式名称）
        # 3) 图下扩展说明段落（来自 _figure_description）
        formal_cap = _formal_caption(ch, order, raw_title)
        cap = _escape_tex(formal_cap)
        width = _infer_fig_width(image_abs_path)
        desc = _figure_description(ch, formal_cap)
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
        "本软件面向临床医师，专为住院/门诊环境下的 2 型糖尿病代谢评估与分型管理设计。软件基于两种技术方案（TyG-eGFR-ALB 与 TyG-WWI-ALB）实现代谢表型识别，提供从患者信息录入、指标计算、分型判别到报告生成与数据归档的完整工作流程。\n\n"
        "在患者信息录入环节，系统支持人口学信息、病程、并发症/合并症与关键实验室指标的结构化录入，并对核心输入执行范围校验、缺失提示与单位换算，减少手工换算错误与漏填风险。系统自动计算 BMI、WWI、TyG 与 eGFR 等衍生指标，并基于两种三维特征体系（TyG-eGFR-ALB 与 TyG-WWI-ALB）进行四表型分型判别，输出结果解释与管理重点提示。报告支持 HTML 与 PDF 两种导出格式，患者完整数据与结果将以 JSON 形式归档保存，便于随访复核与科研整理。软件采用完全本地化运行方式，无需网络连接，降低网络依赖并保护患者隐私。\n\n"
        "本手册用于说明软件的主要功能模块与典型操作流程，手册中所有界面截图均来自软件实际运行过程。\n\n"
    )
    tex_parts.append("{\\color{red}\n" + _escape_tex(STRICT_STATEMENT).replace("\n", "\n\n") + "\n}\n\n")
    tex_parts.append("\\newpage\n")

    # 第 2~7 节：每节先输出概述文字，再按截图顺序输出图片 + 说明
    for ch in [2, 3, 4, 5, 6, 7]:
        tex_parts.append(f"\\section{{{_escape_tex(section_titles[ch])}}}\n")

        # 各节的概述段落（写成固定文案，便于保持手册"可读性"与"稳定性"）
        if ch == 2:
            tex_parts.append(
                "本节介绍医师登录与注册流程。软件采用本地离线账号系统，医师可在无网络环境下注册与登录，所有账号信息加密存储于用户 AppData 目录，确保数据安全与隐私保护。\n\n"
            )
        elif ch == 3:
            tex_parts.append(
                "本节介绍软件主页面的整体布局与功能导航，包括可折叠侧面导航栏、常用计算器页面入口、归档浏览页面与关于信息页面等。\n\n"
            )
        elif ch == 4:
            tex_parts.append(
                "本节介绍患者信息录入与代谢分型的核心流程，包括基本信息与体格检查录入、日期校验、病程自动换算、并发症选择、实验室指标录入与校验、双技术方案代谢表型识别、报告导出等。\n\n"
            )
        elif ch == 5:
            tex_parts.append(
                "本节介绍常用计算器页面，包含 BMI/WWI 自动计算、糖尿病病程估算、eGFR 多公式对比输出、血糖单位换算、HbA1c 估算与换算以及 CGM 动态血糖指标计算等。\n\n"
            )
        elif ch == 6:
            tex_parts.append(
                "本节介绍患者归档的浏览与检索功能，包括归档列表预览与刷新读取等操作。\n\n"
            )
        elif ch == 7:
            tex_parts.append(
                "本节介绍系统设置与说明模块，包括界面字体调整、深色/浅色主题切换、中英文语言切换、代谢分型聚类原理说明、计算器使用说明与用户手册快捷入口等。\n\n"
            )

        # 遍历当前章节的图片，按序号输出
        figs = groups.get(ch, [])
        for idx, (order, pth, title) in enumerate(figs, start=1):
            # TeX 里引用图片走相对路径，避免与 repo-root 绑定
            rel = (Path(manual_rel) / pth.name).as_posix()
            tex_parts.append(fig_block(ch, order, pth, rel, title))

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


def compile_pdf(tex_path: Path, engine: str = "xelatex", engine_path: str = "") -> Path:
    # 使用指定引擎（默认 xelatex）编译 TeX 为 PDF
    # 说明：为了让目录页码/总页数引用稳定，通常需要编译两次
    work_dir = tex_path.parent
    cmd_name = engine_path if engine_path else engine
    cmd = [cmd_name, "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
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
    parser.add_argument("--engine-path", type=str, default="")
    parser.add_argument("--publish-date-cn", type=str, default="")
    args = parser.parse_args()

    # repo_root：不传则取脚本所在目录向上两级作为"项目根目录"
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[1]
    # manual_dir/app_config 支持相对路径（相对于 repo_root）或绝对路径
    manual_dir = Path(args.manual_dir)
    manual_dir = manual_dir if manual_dir.is_absolute() else (repo_root / manual_dir)
    app_config_path = Path(args.app_config)
    app_config_path = app_config_path if app_config_path.is_absolute() else (repo_root / app_config_path)

    # 读取页眉文本所需的"软件名+版本号"
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
    pdf = compile_pdf(out_tex, engine=args.engine, engine_path=args.engine_path)
    # 向标准输出写出产物路径，便于脚本被其他工具链调用
    print(str(out_tex))
    print(str(pdf))
    return 0


if __name__ == "__main__":
    # 作为脚本执行时，返回码交给操作系统
    raise SystemExit(main())
