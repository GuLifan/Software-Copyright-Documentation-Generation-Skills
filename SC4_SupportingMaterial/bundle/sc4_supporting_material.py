from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET


def _read_text_lossy(path: Path) -> str:
    data = path.read_bytes()
    for enc in ["utf-8", "utf-8-sig"]:
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def _docx_to_text(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zf:
        xml_bytes = zf.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    paras: list[str] = []
    for p in root.findall(".//w:p", ns):
        runs = p.findall(".//w:t", ns)
        txt = "".join((r.text or "") for r in runs).strip()
        if txt:
            paras.append(txt)
    return "\n".join(paras).strip()


def _summarize_text(s: str, max_chars: int = 120) -> str:
    t = re.sub(r"\s+", " ", s.strip())
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1] + "…"


def _guess_title_from_markdown(md: str) -> str | None:
    for line in md.splitlines():
        m = re.match(r"^\s*#\s+(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    return None


def _strip_top_level_title(md: str) -> str:
    lines = md.splitlines()
    if lines and re.match(r"^\s*#\s+.+", lines[0]):
        return "\n".join(lines[1:]).lstrip("\n").rstrip() + "\n"
    return md.rstrip() + "\n"


def _load_material_text(path: Path) -> tuple[str, str]:
    ext = path.suffix.lower()
    if ext in {".md", ".txt"}:
        return ext.lstrip("."), _read_text_lossy(path)
    if ext == ".docx":
        return "docx", _docx_to_text(path)
    if ext == ".pdf":
        return "pdf", ""
    return ext.lstrip("."), _read_text_lossy(path)


def build_supporting_markdown(
    *,
    project_name: str,
    inputs: list[Path],
    title: str | None,
    author: str | None,
    date_str: str | None,
) -> str:
    parts: list[str] = []

    guessed_title = None
    if inputs:
        try:
            typ, txt = _load_material_text(inputs[0])
            if typ == "md":
                guessed_title = _guess_title_from_markdown(txt)
        except Exception:
            guessed_title = None

    doc_title = (title or guessed_title or f"{project_name} 软著佐证材料").strip()
    parts.append(f"# {doc_title}\n\n")

    if author or date_str:
        a = (author or "").strip()
        d = (date_str or "").strip()
        parts.append(f"#### *{(a + ' ' + d).strip()}*\n\n")

    parts.append("## 0 材料清单\n\n")
    parts.append("| 序号 | 文件名 | 类型 | 摘要 |\n")
    parts.append("| :--: | --- | :--: | --- |\n")
    for i, p in enumerate(inputs, start=1):
        typ, txt = _load_material_text(p)
        summary = _summarize_text(txt) if txt else "（仅引用/登记，不内嵌正文）"
        parts.append(f"| {i} | {p.name} | {typ} | {summary} |\n")
    parts.append("\n")

    for i, p in enumerate(inputs, start=1):
        typ, txt = _load_material_text(p)
        parts.append(f"## {i} {p.stem}\n\n")
        parts.append(f"> 来源文件：`{p.name}`\n\n")
        if typ == "md":
            parts.append(_strip_top_level_title(txt))
        elif typ == "pdf":
            parts.append("该文件作为佐证材料引用提交，本页仅记录文件名与来源。\n\n")
        else:
            if txt.strip():
                parts.append(txt.strip() + "\n\n")
            else:
                parts.append("（无可抽取正文）\n\n")

    return "".join(parts).rstrip() + "\n"


def _markdown_to_html(md: str) -> str:
    try:
        import markdown  # type: ignore

        body = markdown.markdown(md, extensions=["tables", "fenced_code"])
    except Exception:
        escaped = html.escape(md)
        body = "<pre>" + escaped + "</pre>"

    css = """
    body{font-family: 'Times New Roman','SimSun','Microsoft YaHei',serif; font-size: 12pt; line-height: 1.5;}
    h1{font-size: 20pt; margin: 0 0 12pt 0;}
    h2{font-size: 14pt; margin: 14pt 0 8pt 0;}
    table{border-collapse: collapse; width: 100%;}
    th,td{border:1px solid #333; padding:6px 8px; vertical-align: top;}
    blockquote{margin: 0 0 8pt 0; padding-left: 10pt; border-left: 3px solid #999; color:#333;}
    pre{white-space: pre-wrap; word-wrap: break-word; font-family: 'Consolas','Courier New',monospace; font-size: 10.5pt;}
    """
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"


def _write_pdf_from_html(html_text: str, out_pdf: Path, base_dir: Path) -> bool:
    try:
        from weasyprint import HTML  # type: ignore

        HTML(string=html_text, base_url=str(base_dir)).write_pdf(str(out_pdf))
        return True
    except Exception:
        return False


def _write_pdf_with_wkhtmltopdf(html_text: str, out_pdf: Path, work_dir: Path) -> bool:
    exe = shutil.which("wkhtmltopdf")
    if not exe:
        return False
    tmp_html = out_pdf.with_suffix(".html")
    tmp_html.write_text(html_text, encoding="utf-8", newline="\n")
    p = subprocess.run([exe, str(tmp_html), str(out_pdf)], cwd=str(work_dir))
    return p.returncode == 0 and out_pdf.exists()


def _write_pdf_with_pandoc(md_path: Path, out_pdf: Path, work_dir: Path) -> bool:
    exe = shutil.which("pandoc")
    if not exe:
        return False
    p = subprocess.run([exe, str(md_path), "-o", str(out_pdf)], cwd=str(work_dir))
    return p.returncode == 0 and out_pdf.exists()


def _write_pdf_with_xelatex(md_text: str, out_pdf: Path, work_dir: Path) -> bool:
    tex_path = out_pdf.with_suffix(".tex")

    def esc(s: str) -> str:
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

    lines: list[str] = []
    lines.append(r"\documentclass[12pt,a4paper]{article}" + "\n")
    lines.append(r"\usepackage[a4paper,top=2.5cm,bottom=2.5cm,left=2cm,right=2cm]{geometry}" + "\n")
    lines.append(r"\usepackage{fontspec}" + "\n")
    lines.append(r"\usepackage{xeCJK}" + "\n")
    lines.append(r"\setmainfont{Times New Roman}" + "\n")
    lines.append(r"\IfFontExistsTF{SimSun}{\setCJKmainfont{SimSun}}{\setCJKmainfont{Microsoft YaHei}}" + "\n")
    lines.append(r"\usepackage{xcolor}" + "\n")
    lines.append(r"\usepackage{hyperref}" + "\n")
    lines.append(r"\begin{document}" + "\n")

    for raw in md_text.splitlines():
        if raw.startswith("# "):
            lines.append(r"\section*{" + esc(raw[2:].strip()) + "}\n")
            continue
        if raw.startswith("## "):
            lines.append(r"\subsection*{" + esc(raw[3:].strip()) + "}\n")
            continue
        if raw.startswith("### "):
            lines.append(r"\subsubsection*{" + esc(raw[4:].strip()) + "}\n")
            continue
        lines.append(esc(raw) + r"\\ " + "\n")

    lines.append(r"\end{document}" + "\n")
    tex_path.write_text("".join(lines), encoding="utf-8", newline="\n")

    exe = shutil.which("xelatex") or "xelatex"
    for _ in range(2):
        p = subprocess.run([exe, "-interaction=nonstopmode", "-halt-on-error", tex_path.name], cwd=str(work_dir))
        if p.returncode != 0:
            return False
    pdf = tex_path.with_suffix(".pdf")
    if not pdf.exists():
        return False
    pdf.replace(out_pdf)
    return out_pdf.exists()


def write_supporting_pdf(md_path: Path, out_pdf: Path) -> Path:
    md_text = _read_text_lossy(md_path)
    html_text = _markdown_to_html(md_text)
    work_dir = out_pdf.parent

    if _write_pdf_from_html(html_text, out_pdf, base_dir=work_dir):
        return out_pdf
    if _write_pdf_with_wkhtmltopdf(html_text, out_pdf, work_dir=work_dir):
        return out_pdf
    if _write_pdf_with_pandoc(md_path, out_pdf, work_dir=work_dir):
        return out_pdf
    if _write_pdf_with_xelatex(md_text, out_pdf, work_dir=work_dir):
        return out_pdf

    raise RuntimeError("无法生成 PDF：未找到可用的 HTML→PDF 后端，且 XeLaTeX 回退失败。")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=str, default="")
    parser.add_argument("--project-name", type=str, default="Project")
    parser.add_argument("--inputs", type=str, action="append", default=[])
    parser.add_argument("--out-dir", type=str, default="")
    parser.add_argument("--title", type=str, default="")
    parser.add_argument("--author", type=str, default="")
    parser.add_argument("--date", type=str, default="")
    parser.add_argument("--no-pdf", action="store_true", default=False)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[3]
    out_dir = Path(args.out_dir).resolve() if args.out_dir else repo_root
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs = [Path(p).resolve() for p in args.inputs]
    out_md = out_dir / f"SC_{args.project_name}_4_SupportingMaterial.md"
    out_pdf = out_dir / f"SC_{args.project_name}_4_SupportingMaterial.pdf"

    d = args.date.strip() or date.today().isoformat()
    md = build_supporting_markdown(
        project_name=args.project_name,
        inputs=inputs,
        title=args.title.strip() or None,
        author=args.author.strip() or None,
        date_str=d if (args.author.strip() or args.date.strip()) else None,
    )
    out_md.write_text(md, encoding="utf-8", newline="\n")

    if not args.no_pdf:
        write_supporting_pdf(out_md, out_pdf)

    print(str(out_md))
    if not args.no_pdf:
        print(str(out_pdf))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

