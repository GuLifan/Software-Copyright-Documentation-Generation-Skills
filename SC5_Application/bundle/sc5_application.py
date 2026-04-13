from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class AppInfo:
    application_display_name: str
    app_version: str

    def version_label(self) -> str:
        v = self.app_version.strip()
        if v and not v.lower().startswith("v"):
            v = "V" + v
        return v


def _read_text_lossy(path: Path) -> str:
    data = path.read_bytes()
    for enc in ["utf-8", "utf-8-sig"]:
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def _load_app_info(app_config_yaml: Path) -> AppInfo:
    text = _read_text_lossy(app_config_yaml)
    display_name: str | None = None
    app_version: str | None = None

    in_app = False
    for raw in text.splitlines():
        line = raw.rstrip("\n").rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            in_app = line.strip() == "app:"
            continue
        if not in_app:
            continue
        if not line.startswith("  "):
            continue
        key_val = line.strip()
        if ":" not in key_val:
            continue
        k, v = key_val.split(":", 1)
        k = k.strip()
        v = v.strip()
        if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
            v = v[1:-1]
        if k == "application_display_name":
            display_name = v
        elif k == "app_version":
            app_version = v
        if display_name is not None and app_version is not None:
            break

    if display_name is None:
        raise ValueError("app_config.yaml 缺少 app.application_display_name")
    if app_version is None:
        raise ValueError("app_config.yaml 缺少 app.app_version")
    return AppInfo(application_display_name=display_name, app_version=app_version)


def _date_cn_from_ymd(ymd: str) -> str:
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", ymd.strip())
    if not m:
        return ymd.strip()
    y, mm, dd = m.group(1), m.group(2), m.group(3)
    return f"{y}年{mm}月{dd}日"


def _file_mtime_cn(path: Path) -> str:
    ts = path.stat().st_mtime
    d = date.fromtimestamp(ts)
    return f"{d.year:04d}年{d.month:02d}月{d.day:02d}日"


def _guess_source_lines(repo_root: Path, project_name: str) -> int | None:
    candidates = [
        repo_root / f"SC_{project_name}_2_OriginalCode.tex",
        repo_root / f"SC_{project_name}_2_OriginalCode.pdf",
        repo_root / "SC_{}_2_OriginalCode.tex".format(project_name),
    ]
    for p in candidates:
        if not p.exists():
            continue
        if p.suffix.lower() != ".tex":
            continue
        text = _read_text_lossy(p)
        nums = [int(x) for x in re.findall(r"\\SCLine\{(\d+)\}", text)]
        if nums:
            return max(nums)
    return None


def _build_main_function_cn(readme_text: str) -> str:
    lines = readme_text.splitlines()
    in_func = False
    bullets: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if re.match(r"^\s*##\s*功能概览\s*$", line):
            in_func = True
            continue
        if in_func and re.match(r"^\s*##\s+", line):
            break
        if not in_func:
            continue
        m = re.match(r"^\s*-\s+(.*)$", line)
        if m:
            bullets.append(m.group(1).strip())

    base = (
        "本软件面向临床医师，在住院场景下对2型糖尿病患者进行快速评估与分型管理，提供“数据录入—校验换算—衍生计算—分型解释—报告归档”的一体化流程。"
        "系统提供医师登录/注册与本地账号管理，支持患者信息结构化录入，并对关键输入进行校验与单位换算，减少手工换算错误与漏填风险。"
        "系统可自动计算BMI、TyG指数与eGFR等衍生指标，并基于TyG/eGFR/ALB三维特征进行四表型分型判别，输出分型结果、关键特征解释与对应的临床诊疗重点提示，辅助规范化诊疗。"
        "系统支持生成标准化报告并导出/打印，患者输入与计算结果以JSON形式归档保存，便于随访复核与科研整理。"
        "软件采用本地离线运行方式，降低网络依赖并保护患者隐私，适合在院内与基层环境推广应用。"
    )

    extra = ""
    if bullets:
        joined = "；".join(bullets[:12])
        extra = "功能要点包括：" + joined + "。"

    text = base + extra
    text = re.sub(r"\s+", "", text)

    if len(text) < 500:
        text += (
            "系统在缺失字段处理上遵循“非必需可保存、报告标注未录入；分型必需缺失则提示补全”的原则，避免因信息不完整导致误分型。"
            "模型参数与分型逻辑通过外置YAML配置固化并可版本化更新，便于在不同机构人群中维护一致性与可追溯性。"
        )
    if len(text) > 1300:
        text = text[:1300]
    return text


def _replace_backticked_value(line: str, new_value: str) -> str:
    if "`" not in line:
        return line
    parts = line.split("`")
    if len(parts) < 3:
        return line
    parts[1] = new_value
    return "`".join(parts)


def generate_application_md(
    *,
    template_md: str,
    app_info: AppInfo,
    project_name: str,
    readme_text: str,
    repo_root: Path,
    complete_date_cn: str,
    publish_date_cn: str,
    short_name_override: str | None,
) -> str:
    source_lines = _guess_source_lines(repo_root, project_name)
    main_func = _build_main_function_cn(readme_text)

    lines = template_md.splitlines(True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if 'color="red"' not in line:
            out.append(line)
            i += 1
            continue

        if "软件全称" in line:
            out.append(_replace_backticked_value(line, app_info.application_display_name))
            i += 1
            continue
        if "软件简称" in line and short_name_override:
            out.append(_replace_backticked_value(line, short_name_override))
            i += 1
            continue
        if "版本号" in line:
            out.append(_replace_backticked_value(line, app_info.version_label()))
            i += 1
            continue
        if "开发完成日期" in line:
            out.append(_replace_backticked_value(line, complete_date_cn))
            i += 1
            continue
        if "首次发表日期" in line:
            out.append(_replace_backticked_value(line, publish_date_cn))
            i += 1
            continue
        if "编程语言" in line:
            out.append(_replace_backticked_value(line, "Python"))
            i += 1
            continue
        if "源程序量" in line and source_lines is not None:
            out.append(_replace_backticked_value(line, f"{source_lines}（行）"))
            i += 1
            continue
        if "开发目的" in line:
            out.append(_replace_backticked_value(line, "为2型糖尿病住院患者提供代谢分型与管理要点提示，辅助规范化诊疗。"))
            i += 1
            continue
        if "软件的主要功能" in line:
            out.append(line)
            out.append("\n    " + main_func + "\n\n")
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.lstrip().startswith("<font") and 'color="red"' in nxt:
                    break
                if nxt.startswith("    "):
                    i += 1
                    continue
                if nxt.strip() == "":
                    i += 1
                    continue
                break
            continue

        out.append(line)
        i += 1

    return "".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=str, default="")
    parser.add_argument("--project-name", type=str, default="Project")
    parser.add_argument("--template-md", type=str, required=True)
    parser.add_argument("--app-config", type=str, default="app_config.yaml")
    parser.add_argument("--readme", type=str, default="README.md")
    parser.add_argument("--out-md", type=str, default="")
    parser.add_argument("--publish-date-cn", type=str, default="")
    parser.add_argument("--complete-date-cn", type=str, default="")
    parser.add_argument("--short-name", type=str, default="")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[3]
    template_path = Path(args.template_md)
    template_path = template_path if template_path.is_absolute() else (repo_root / template_path)
    app_config_path = Path(args.app_config)
    app_config_path = app_config_path if app_config_path.is_absolute() else (repo_root / app_config_path)
    readme_path = Path(args.readme)
    readme_path = readme_path if readme_path.is_absolute() else (repo_root / readme_path)

    app_info = _load_app_info(app_config_path)
    template_text = _read_text_lossy(template_path)
    readme_text = _read_text_lossy(readme_path) if readme_path.exists() else ""

    complete_date_cn = args.complete_date_cn.strip() or (_file_mtime_cn(readme_path) if readme_path.exists() else _date_cn_from_ymd(date.today().isoformat()))
    publish_date_cn = args.publish_date_cn.strip() or _date_cn_from_ymd(date.today().isoformat())
    short_name_override = args.short_name.strip() or None

    out_md = Path(args.out_md) if args.out_md else (repo_root / f"SC_{args.project_name}_5_Application.md")
    out_md = out_md.resolve()

    out_text = generate_application_md(
        template_md=template_text,
        app_info=app_info,
        project_name=args.project_name,
        readme_text=readme_text,
        repo_root=repo_root,
        complete_date_cn=complete_date_cn,
        publish_date_cn=publish_date_cn,
        short_name_override=short_name_override,
    )

    out_md.write_text(out_text, encoding="utf-8", newline="\n")
    print(str(out_md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

