from __future__ import annotations

"""
用途：生成“软著源码鉴别材料（60页/3000行）”相关产物

输入：
- 仓库根目录 repo_root（默认当前工作目录）
- 需要纳入的源码范围（--include / --extra）
- 版本信息来源配置文件（--app-config，用于页眉“软件名 + 版本号”）
- 忽略规则文件（--ignore-file，通常为 .gitignore）

输出（默认落在 out_dir）：
- SC_{项目名}_2_OriginalCode.md：按相对路径聚合源码（红色标题 + 原文）
- SC_{项目名}_2_OriginalCode_wrapped.md：删除空行并按版面宽度“预换行”，避免 LaTeX 再次折行
- SC_{项目名}_2_OriginalCode.tex：A4、边距、页眉页脚、固定每页 50 行、左侧行号
- SC_{项目名}_2_OriginalCode.pdf：由 xelatex 编译生成

设计要点：
- “每页固定 50 行”的规则优先级最高：在 TeX 中每 50 行强制分页，并显式输出行号
- “超过 3000 行只保留前 1500 行与后 1500 行”：行号在后半段跳转以反映真实总行数
"""

# 标准库：命令行参数解析
import argparse
# 标准库：glob/ignore 模式匹配（用于简化版 .gitignore 过滤）
import fnmatch
# 标准库：目录遍历（os.walk）
import os
# 标准库：正则表达式（解析标题行、解析 YAML 键值）
import re
# 标准库：子进程调用（xelatex 编译）
import subprocess
# 标准库：Unicode 字符宽度/组合字符判断（预换行时估算“可容纳字符数”）
import unicodedata
# 标准库：数据类（结构化保存 header 两个字段）
from dataclasses import dataclass
# 标准库：路径处理（跨平台）
from pathlib import Path


@dataclass(frozen=True)
class AppHeader:
    # 软件显示名（application_display_name）
    display_name: str
    # 软件版本号（app_version）
    app_version: str

    def header_text(self) -> str:
        # 生成页眉文字：display_name + V{version}
        v = self.app_version.strip()
        # 若版本号未带 V/v 前缀，则自动补上 V（与软著材料常见写法一致）
        if v and not v.lower().startswith("v"):
            v = "V" + v
        # 拼接并去除两侧空白
        return (self.display_name.strip() + " " + v).strip()


def _read_text_lossy(path: Path) -> str:
    # 以字节读取文件，避免因编码问题直接抛异常
    data = path.read_bytes()
    # 优先尝试 utf-8 与 utf-8-sig（带 BOM）
    for enc in ["utf-8", "utf-8-sig"]:
        try:
            return data.decode(enc)
        except Exception:
            continue
    # 最终兜底：用 utf-8 并替换无法解码字符
    return data.decode("utf-8", errors="replace")


def _load_app_header(app_config_yaml: Path) -> AppHeader:
    # 读取 YAML 文本（不依赖 PyYAML，确保脚本可迁移）
    text = _read_text_lossy(app_config_yaml)
    # application_display_name 解析结果
    display_name: str | None = None
    # app_version 解析结果
    app_version: str | None = None

    # 是否处于 app: section 内（只解析 app: 下的二级键）
    in_app = False
    for raw in text.splitlines():
        # 统一去除换行符
        line = raw.rstrip("\n").rstrip("\r")
        # 跳过空行与注释行
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # 顶层键（无缩进）：用于判断是否进入 app: 段
        if not line.startswith(" "):
            in_app = line.strip() == "app:"
            continue
        # 不在 app 段内则忽略
        if not in_app:
            continue
        # 仅接受二级缩进（两个空格）
        if not line.startswith("  "):
            continue
        # 去掉缩进后解析 key: value
        key_val = line.strip()
        if ":" not in key_val:
            continue
        k, v = key_val.split(":", 1)
        k = k.strip()
        v = v.strip()
        # 去掉两侧引号（简单场景）
        if v.startswith('"') and v.endswith('"') and len(v) >= 2:
            v = v[1:-1]
        if v.startswith("'") and v.endswith("'") and len(v) >= 2:
            v = v[1:-1]
        # 只关心两个字段
        if k == "application_display_name":
            display_name = v
        elif k == "app_version":
            app_version = v
        # 两者都解析到就提前结束
        if display_name is not None and app_version is not None:
            break

    # 必填校验：缺字段直接报错
    if display_name is None:
        raise ValueError("app_config.yaml 缺少 app.application_display_name")
    if app_version is None:
        raise ValueError("app_config.yaml 缺少 app.app_version")
    # 构造 header 对象
    return AppHeader(display_name=display_name, app_version=app_version)


def _norm_rel_path(path: Path) -> str:
    # 统一输出为 posix 样式（便于跨平台一致、也便于 LaTeX/Markdown 展示）
    return path.as_posix()


def _is_ignored(rel_posix: str, patterns: list[str]) -> bool:
    # rel_posix：相对仓库根的路径（posix 风格）
    rp = rel_posix.lstrip("./")
    # 路径分段（用于处理 “xxx/” 目录类忽略规则）
    parts = rp.split("/")

    # 逐条匹配 ignore pattern（简化实现，覆盖常见通配符与目录忽略）
    for pat in patterns:
        p = pat.strip()
        if not p or p.startswith("#"):
            continue
        # 反向规则（!）暂不支持：直接忽略
        if p.startswith("!"):
            continue

        # 统一转为 posix 风格
        p = p.replace("\\", "/")
        # 是否以 / 开头（锚定仓库根）
        anchored = p.startswith("/")
        if anchored:
            p = p.lstrip("/")

        # 目录忽略：以 / 结尾（例如 __pycache__/）
        if p.endswith("/"):
            base = p.rstrip("/")
            if not base:
                continue
            for i in range(len(parts)):
                sub = "/".join(parts[: i + 1])
                name = parts[i]
                # 同时尝试匹配 “前缀路径” 与 “目录名本身”
                if fnmatch.fnmatch(sub, base) or fnmatch.fnmatch(name, base):
                    return True
            continue

        # 含 / 的规则：更像是路径模式（如 build/*.whl）
        if "/" in p:
            if fnmatch.fnmatch(rp, p):
                return True
            # 非 anchored 的模式允许出现在任意子目录
            if not anchored and fnmatch.fnmatch("/" + rp, "*/" + p):
                return True
            continue

        # 仅文件名模式：匹配末段文件名
        if fnmatch.fnmatch(parts[-1], p):
            return True
        # 兜底：也尝试全路径匹配
        if fnmatch.fnmatch(rp, p):
            return True

    # 默认不忽略
    return False


def _collect_target_files_custom(
    repo_root: Path,
    include_paths: list[Path],
    extra_files: list[Path],
    ignore_file: Path | None,
) -> list[Path]:
    # 读取忽略规则文件（通常是 .gitignore）
    patterns: list[str] = []
    if ignore_file is not None and ignore_file.exists() and ignore_file.is_file():
        for raw in _read_text_lossy(ignore_file).splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)

    # 收集到的文件列表（绝对路径）
    targets: list[Path] = []

    def add_one(p: Path) -> None:
        # 只收集存在且为文件的路径
        if not p.exists() or not p.is_file():
            return
        # 计算相对路径，并按 ignore 规则过滤
        rel = _norm_rel_path(p.relative_to(repo_root))
        if _is_ignored(rel, patterns):
            return
        # 纳入目标文件
        targets.append(p)

    # 先收集额外文件（通常 app_config.yaml / main.py）
    for ef in extra_files:
        p = ef if ef.is_absolute() else (repo_root / ef)
        add_one(p)

    # 再遍历 include_paths 指定的目录/文件
    for inc in include_paths:
        base = inc if inc.is_absolute() else (repo_root / inc)
        if not base.exists():
            continue
        if base.is_file():
            add_one(base)
            continue
        # 目录：按“目录树顺序”（dirs/files 排序）遍历
        for root, dirs, files in os.walk(str(base)):
            dirs.sort()
            files.sort()
            for name in files:
                add_one(Path(root) / name)

    # 去重：同一路径只保留一次
    uniq: dict[str, Path] = {}
    for p in targets:
        rel = _norm_rel_path(p.relative_to(repo_root))
        uniq[rel] = p
    # 按相对路径排序，保证输出稳定
    return [uniq[k] for k in sorted(uniq.keys())]


def generate_markdown(
    repo_root: Path,
    project_name: str,
    out_dir: Path,
    include_paths: list[Path] | None = None,
    extra_files: list[Path] | None = None,
    ignore_file: Path | None = None,
) -> Path:
    # 默认遍历 src（可跨项目复用：让用户用 --include 控制范围）
    include_paths = include_paths or [Path("src")]
    # 默认不带额外文件（由调用方决定）
    extra_files = extra_files or []
    # 默认读取 repo_root 下的 .gitignore
    ignore_file = ignore_file if ignore_file is not None else (repo_root / ".gitignore")

    # 收集目标文件
    files = _collect_target_files_custom(
        repo_root=repo_root,
        include_paths=include_paths,
        extra_files=extra_files,
        ignore_file=ignore_file,
    )
    # 输出文件路径：SC_{项目名}_2_OriginalCode.md
    out_path = out_dir / f"SC_{project_name}_2_OriginalCode.md"

    # 确保输出目录存在
    out_dir.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        for i, p in enumerate(files):
            # 写入红色标题：相对路径
            rel = _norm_rel_path(p.relative_to(repo_root))
            f.write(f'<span style="color:red">{rel}</span>\n')
            # 写入原始内容（尽量保留原貌）
            content = _read_text_lossy(p).replace("\r\n", "\n").replace("\r", "\n")
            if content:
                f.write(content)
                if not content.endswith("\n"):
                    f.write("\n")
            # 文件之间插入一个空行（便于阅读；后续 wrapped 阶段会删除空行）
            if i != len(files) - 1:
                f.write("\n")

    return out_path


# 标题行匹配：用于在 wrapped/tex 中识别“红色路径标题”
_TITLE_RE = re.compile(r'^\s*<span\s+style="color:\s*red"\s*>(.*?)</span>\s*$')


def _md_to_logical_lines(md_path: Path) -> list[str]:
    # 读取 md 并标准化换行符
    raw_lines = _read_text_lossy(md_path).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # 删除空行（软著材料要求删除空行，但不应破坏每行缩进/内容）
    return [ln for ln in raw_lines if ln.strip() != ""]


def _char_units(ch: str) -> int:
    # 估算字符占用宽度：
    # - 组合字符（重音等）算 0
    # - 全角/宽字符算 2
    # - 其他算 1
    if not ch:
        return 0
    if unicodedata.combining(ch):
        return 0
    ea = unicodedata.east_asian_width(ch)
    if ea in ("W", "F"):
        return 2
    return 1


def _wrap_one_line_keep_indent(line: str, max_units: int) -> list[str]:
    # 将 tab 统一替换为空格（避免 tab 宽度在不同渲染器下不一致）
    s = line.replace("\t", " " * 4)
    # 统计行首缩进空格数
    i = 0
    while i < len(s) and s[i] == " ":
        i += 1
    # 缩进部分（会复制到续行）
    indent = s[:i]
    # 实际内容部分
    rest = s[i:]
    if not rest:
        return [indent]

    # 缩进占用的宽度（单位数）
    indent_units = sum(_char_units(c) for c in indent)
    # 允许的内容宽度：总宽度 - 缩进宽度（下限 10）
    limit = max(int(max_units) - indent_units, 10)

    # 输出分行结果
    out: list[str] = []
    # 当前缓冲区（字符列表）
    cur: list[str] = []
    # 当前缓冲区宽度（单位数）
    cur_units = 0
    # 最近一次空格位置（用于优先在空格处断行）
    last_space_idx: int | None = None

    def flush() -> None:
        # 将当前缓冲区输出为一行（带缩进），并清空缓冲区
        nonlocal cur, cur_units, last_space_idx
        out.append(indent + "".join(cur))
        cur = []
        cur_units = 0
        last_space_idx = None

    # 逐字符填充，超过 limit 时断行
    for ch in rest:
        u = _char_units(ch)
        if cur_units + u > limit and cur:
            # 优先在最近的空格处断行（更接近自然文本/代码分词）
            if last_space_idx is not None and last_space_idx >= 0:
                chunk = cur[:last_space_idx]
                out.append(indent + "".join(chunk).rstrip())
                cur = cur[last_space_idx + 1 :]
                cur_units = sum(_char_units(c) for c in cur)
                last_space_idx = None
                for idx, c in enumerate(cur):
                    if c == " ":
                        last_space_idx = idx
            else:
                # 没有空格可断：强制断行
                flush()
        cur.append(ch)
        cur_units += u
        if ch == " ":
            last_space_idx = len(cur) - 1

    # 输出最后一段
    if cur or not out:
        flush()

    return out


def generate_wrapped_markdown(md_path: Path, project_name: str, out_dir: Path, max_units_per_line: int) -> Path:
    # 输出文件路径：SC_{项目名}_2_OriginalCode_wrapped.md
    out_path = out_dir / f"SC_{project_name}_2_OriginalCode_wrapped.md"
    # 读取并删除空行后的 md 行
    lines = _md_to_logical_lines(md_path)

    # wrapped 后的行列表（保证每行在 TeX 中不再二次换行）
    wrapped: list[str] = []
    # 最小宽度保护：避免用户传入过小导致几乎每个词都换行
    max_units = max(int(max_units_per_line), 40)
    for ln in lines:
        # 标题行不做切分，保持原样（后续在 tex 中渲染为红色）
        if _TITLE_RE.match(ln):
            wrapped.append(ln.strip())
            continue
        # 普通内容行：按缩进对齐切分
        wrapped.extend(_wrap_one_line_keep_indent(ln, max_units=max_units))

    # 写入 wrapped 文件
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(wrapped) + "\n", encoding="utf-8", newline="\n")
    return out_path


def _latex_escape_text(s: str) -> str:
    # 将普通文本转换为可放入 LaTeX 宏参数的安全文本
    # 注意：这里不处理换行；换行由 SCLine 与每 50 行分页控制
    s = s.replace("\t", " " * 4)
    s = s.replace("\\", r"\textbackslash{}")
    s = s.replace("{", r"\{")
    s = s.replace("}", r"\}")
    s = s.replace("$", r"\$")
    s = s.replace("&", r"\&")
    s = s.replace("#", r"\#")
    s = s.replace("_", r"\_")
    s = s.replace("%", r"\%")
    s = s.replace("~", r"\textasciitilde{}")
    s = s.replace("^", r"\textasciicircum{}")
    return s


def _preserve_all_spaces(s: str) -> str:
    # 在 LaTeX 中保留所有空格：把普通空格替换成“控制空格” \␠
    # 这样可保持代码缩进与对齐（软著材料常要求保留缩进）
    return s.replace(" ", r"\ ")


def generate_tex(repo_root: Path, project_name: str, out_dir: Path, wrapped_md_path: Path, app_config_path: Path) -> Path:
    # 页眉：从 app_config.yaml 提取 display_name + app_version
    header = _load_app_header(app_config_path).header_text()
    # 输出 tex 路径
    out_path = out_dir / f"SC_{project_name}_2_OriginalCode.tex"

    # wrapped 行（删除空行 + 预切分后的“文本行”）
    wrapped_lines = _md_to_logical_lines(wrapped_md_path)
    # 总文本行数（用于决定是否截断）
    total_text_lines = len(wrapped_lines)
    # 软著要求：保留开头 1500 行
    head_keep = 1500
    # 软著要求：保留结尾 1500 行
    tail_keep = 1500
    # 只有当总行数 > 3000 时才截断
    use_tail = total_text_lines > 3000

    if use_tail:
        # 前 1500 行
        head_lines = wrapped_lines[:head_keep]
        # 后 1500 行
        tail_lines = wrapped_lines[-tail_keep:]
        # 后半段起始行号：总行数-1500+1（让最后一行号反映真实总行数）
        tail_start = total_text_lines - tail_keep + 1
    else:
        # 不截断：全部作为“前半段”
        head_lines = wrapped_lines
        tail_lines = []
        tail_start = 1

    def line_to_tex_text(ln: str) -> str:
        # 将一行 wrapped 文本转换为 TeX 可安全渲染的文本
        m = _TITLE_RE.match(ln)
        if m:
            # 标题行：保持红色，并用 detokenize 避免下划线等触发 TeX 语法
            title = m.group(1)
            return rf"\textcolor{{red}}{{\detokenize{{{title}}}}}"
        # 普通行：转义 LaTeX 特殊字符，并保留空格（缩进）
        esc = _latex_escape_text(ln)
        esc = _preserve_all_spaces(esc)
        return esc

    def emit_segment(lines: list[str], start_no: int) -> list[str]:
        # 输出一段（前段或尾段）：
        # - 每一行输出为 \SCLine{行号}{内容}
        # - 每 50 行插入 \newpage，保证每页固定 50 行
        out: list[str] = []
        n = int(start_no)
        for idx, ln in enumerate(lines):
            out.append(rf"\SCLine{{{n}}}{{{line_to_tex_text(ln)}}}")
            n += 1
            if (idx + 1) % 50 == 0 and (idx + 1) != len(lines):
                out.append(r"\newpage")
        return out

    # 生成前段 TeX 内容
    head_seg = "\n".join(emit_segment(head_lines, 1))
    # 生成尾段 TeX 内容（可为空）
    tail_seg = "\n".join(emit_segment(tail_lines, tail_start)) if tail_lines else ""

    # LaTeX 模板：使用 xelatex + xeCJK 以支持中文；页眉页脚用 fancyhdr + lastpage
    tex = rf"""\documentclass[a4paper]{{article}}
\usepackage[a4paper,top=2.5cm,bottom=2.5cm,left=2cm,right=2cm,includeheadfoot]{{geometry}}
\usepackage{{fontspec}}
\usepackage{{xeCJK}}
\setmainfont{{Times New Roman}}
\IfFontExistsTF{{SimSun}}{{\setCJKmainfont{{SimSun}}}}{{\setCJKmainfont{{Microsoft YaHei}}}}
\XeTeXlinebreaklocale "en"
\XeTeXlinebreakskip=0pt plus 0pt
\usepackage{{xcolor}}
\usepackage{{fancyhdr}}
\usepackage{{lastpage}}

\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0pt}}
\setlength{{\headheight}}{{14pt}}

\pagestyle{{fancy}}
\fancyhf{{}}
\fancyhead[C]{{{header}}}
\fancyfoot[C]{{第\thepage 页/共 \pageref{{LastPage}} 页}}

% 单行输出宏：
% - 行号放在左侧页边距（\llap），不占用正文宽度
% - 行号宽度 1.6cm，行号与正文之间 0.3cm 间距
% - 正文字号 8pt，行距 9pt（与软著常见排版接近）
\newcommand{{\SCLine}}[2]{{%
  \noindent\llap{{\makebox[1.6cm][r]{{\fontsize{{8}}{{8}}\selectfont #1}}\hspace{{0.3cm}}}}%
  {{\fontsize{{8}}{{9}}\selectfont #2}}\par
}}

\begin{{document}}
{head_seg}
"""
    if use_tail:
        # 分隔前段与尾段（从新页开始，便于审查）
        tex += rf"""
\clearpage
{tail_seg}
"""

    # 文档结束
    tex += r"\end{document}"

    # 写入 tex 文件
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tex, encoding="utf-8", newline="\n")
    return out_path


def compile_pdf(tex_path: Path, engine: str = "xelatex") -> Path:
    # 以 tex 所在目录作为工作目录（生成 .aux/.log/.pdf 等）
    work_dir = tex_path.parent
    # 选择编译引擎（默认 xelatex），并启用 nonstopmode + halt-on-error 便于自动化
    cmd = [engine, "-interaction=nonstopmode", "-halt-on-error", tex_path.name]

    # 编译两遍：确保 lastpage 能正确得到总页数
    for _ in range(2):
        p = subprocess.run(
            cmd,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if p.returncode != 0:
            raise RuntimeError(
                f"LaTeX 编译失败（{engine}）。\n\nSTDOUT:\n{p.stdout}\n\nSTDERR:\n{p.stderr}"
            )

    # 输出 pdf 应与 tex 同名
    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        raise RuntimeError("LaTeX 编译完成但未找到输出 PDF：" + str(pdf_path))
    return pdf_path


def main() -> int:
    # 命令行入口：支持分步执行（md / wrap / tex / pdf / all）
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=str, default="")
    parser.add_argument("--project-name", type=str, default="PROJECT")
    parser.add_argument("--out-dir", type=str, default="")
    parser.add_argument("--step", type=str, choices=["md", "wrap", "tex", "pdf", "all"], default="all")
    parser.add_argument("--engine", type=str, default="xelatex")
    parser.add_argument("--wrap-columns", type=int, default=120)
    # --include 可重复：要遍历纳入的目录/文件
    parser.add_argument("--include", action="append", default=[])
    # --extra 可重复：额外单文件（如 main.py / app_config.yaml）
    parser.add_argument("--extra", action="append", default=[])
    # 页眉来源配置文件：用于读取软件名与版本号
    parser.add_argument("--app-config", type=str, default="app_config.yaml")
    # 忽略规则文件（通常是 .gitignore）
    parser.add_argument("--ignore-file", type=str, default=".gitignore")
    args = parser.parse_args()

    # 仓库根目录：默认当前工作目录（可迁移脚本不依赖固定目录结构）
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd().resolve()
    # 输出目录：默认仓库根目录，也建议用户指定到一个专用文件夹便于打包
    out_dir = Path(args.out_dir).resolve() if args.out_dir else repo_root

    # include 路径列表：默认 src（跨项目通用）
    include_paths = [Path(p) for p in args.include] if args.include else [Path("src")]
    # extra 文件列表：默认空（跨项目由用户指定）
    extra_files = [Path(p) for p in args.extra] if args.extra else []
    # app_config 路径（相对 repo_root 解析）
    app_config_path = Path(args.app_config)
    app_config_path = app_config_path if app_config_path.is_absolute() else (repo_root / app_config_path)
    # ignore 文件路径（相对 repo_root 解析）
    ignore_file = Path(args.ignore_file)
    ignore_file = ignore_file if ignore_file.is_absolute() else (repo_root / ignore_file)

    # 输出文件名统一采用 SC_{项目名}_2_OriginalCode.*
    md_path = out_dir / f"SC_{args.project_name}_2_OriginalCode.md"
    wrapped_md_path = out_dir / f"SC_{args.project_name}_2_OriginalCode_wrapped.md"
    tex_path = out_dir / f"SC_{args.project_name}_2_OriginalCode.tex"

    if args.step in ["md", "all"]:
        # 第一步：聚合源码为 MD（带红色标题）
        md_path = generate_markdown(
            repo_root=repo_root,
            project_name=args.project_name,
            out_dir=out_dir,
            include_paths=include_paths,
            extra_files=extra_files,
            ignore_file=ignore_file,
        )
        print(str(md_path))
        if args.step == "md":
            return 0

    if args.step in ["wrap", "all"]:
        # 第二步：删除空行 + 按宽度预换行，生成 wrapped.md
        if not md_path.exists():
            raise RuntimeError("未找到 markdown 文件：" + str(md_path))
        wrapped_md_path = generate_wrapped_markdown(
            md_path, args.project_name, out_dir, max_units_per_line=int(args.wrap_columns)
        )
        print(str(wrapped_md_path))
        if args.step == "wrap":
            return 0

    if args.step in ["tex", "all"]:
        # 第三步：把 wrapped.md 转为 TeX（固定每页 50 行 + 行号 + 页眉页脚）
        if not wrapped_md_path.exists():
            raise RuntimeError("未找到 wrapped markdown 文件：" + str(wrapped_md_path))
        tex_path = generate_tex(repo_root, args.project_name, out_dir, wrapped_md_path, app_config_path=app_config_path)
        print(str(tex_path))
        if args.step == "tex":
            return 0

    if args.step in ["pdf", "all"]:
        # 第四步：编译 TeX -> PDF（两遍）
        if not tex_path.exists():
            if wrapped_md_path.exists():
                tex_path = generate_tex(
                    repo_root, args.project_name, out_dir, wrapped_md_path, app_config_path=app_config_path
                )
            else:
                raise RuntimeError("未找到 tex/wrapped markdown 文件，无法编译 PDF。")
        pdf_path = compile_pdf(tex_path, engine=args.engine)
        print(str(pdf_path))
        return 0

    return 0


if __name__ == "__main__":
    # 作为脚本执行时返回退出码（便于 CI/自动化）
    raise SystemExit(main())

