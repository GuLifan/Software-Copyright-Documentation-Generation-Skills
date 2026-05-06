#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SC7_ShowVideo - 演示视频配套材料生成器
Generate demo video materials: automation script + bilingual subtitles

可迁移到任意项目使用（仅依赖 Python 标准库 + 可选 PyYAML）。
Portable across projects (depends on stdlib + optional PyYAML).

使用方式 / Usage:
  python sc7_show_video.py --repo-root . --project-name MyProject

产物 / Outputs:
  {out_dir}/demo_automation.py  自动化操作脚本
  {out_dir}/subtitles.md        中英双语字幕
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# 配置读取（兼容 PyYAML 缺失时的手动解析）
# ---------------------------------------------------------------------------

def _read_yaml_simple(path: Path) -> dict[str, object]:
    """读取 YAML 配置为嵌套 dict；仅支持简单层级，不依赖 PyYAML"""
    try:
        from yaml import safe_load
        return safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        pass

    # 手动简易解析器：仅支持缩进表示的嵌套 key: value
    result: dict[str, object] = {}
    stack: list[tuple[int, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip().strip('"').strip("'")
            val = val.strip().strip('"').strip("'")

            while stack and stack[-1][0] >= indent:
                stack.pop()

            if not val:
                new_dict: dict[str, object] = {}
                if not stack:
                    result[key] = new_dict
                else:
                    parent = stack[-1][1]
                    if isinstance(parent, dict):
                        parent[key] = new_dict
                stack.append((indent, new_dict))
            else:
                if not stack:
                    target = result
                else:
                    parent_val = stack[-1][1]
                    if isinstance(parent_val, dict):
                        target = parent_val
                    else:
                        # 父节点不是 dict（输入格式异常），跳过该条目
                        # Parent not a dict (malformed input), skip this entry
                        continue
                target[key] = val
    return result


def _parse_app_info(app_config_path: Path, readme_path: Path | None) -> dict[str, str]:
    """从 YAML 和 README 中提取应用元信息"""
    info: dict[str, str] = {
        "app_name": "MyApplication",
        "app_name_en": "MyApplication",
        "version": "1.0",
        "cluster_version": "1.0",
        "dev_team": "Development Team",
        "dev_contact": "contact@example.com",
        "license": "GNU GPL v3",
        "orcid": "https://orcid.org/0000-0000-0000-0000",
        "github": "https://github.com/example/project",
        "description_cn": "功能演示。",
        "description_en": "Feature demonstration.",
        "features_cn": "核心功能展示。",
        "features_en": "Core feature showcase.",
    }

    if app_config_path.exists():
        cfg = _read_yaml_simple(app_config_path)
        app = cfg.get("app", {})
        if isinstance(app, dict):
            info["app_name"] = str(app.get("application_display_name", info["app_name"]))
            info["version"] = str(app.get("app_version", info["version"]))
        model = cfg.get("model", {})
        if isinstance(model, dict):
            info["cluster_version"] = str(model.get("cluster_version", info["cluster_version"]))
        ui = cfg.get("ui", {})
        if isinstance(ui, dict):
            about = ui.get("about", {})
            if isinstance(about, dict):
                contact = about.get("contact_dev", "")
                if isinstance(contact, str) and contact:
                    info["dev_contact"] = contact.strip()
                    for line in contact.split("\n"):
                        if "orcid" in line.lower():
                            info["orcid"] = line.split(":", 1)[-1].strip()
                        elif "github" in line.lower():
                            info["github"] = line.split(":", 1)[-1].strip()
                dev_info = about.get("dev_info", "")
                if isinstance(dev_info, str) and dev_info:
                    info["dev_team"] = "Based on config dev_info"

    if readme_path and readme_path.exists():
        readme_text = readme_path.read_text(encoding="utf-8")
        # extract first meaningful paragraph
        lines = [l for l in readme_text.splitlines() if l.strip() and not l.startswith("#")]
        if lines:
            info["description_cn"] = lines[0].strip()[:200]
            info["description_en"] = lines[0].strip()[:200]

        # extract features list
        features: list[str] = []
        in_features = False
        for line in readme_text.splitlines():
            if "功能概览" in line or "Features" in line:
                in_features = True
                continue
            if in_features and line.startswith("- "):
                features.append(line[2:].strip()[:80])
            elif in_features and not line.startswith("- ") and line.strip():
                if line.startswith("#"):
                    in_features = False
        if features:
            info["features_cn"] = "；".join(features[:6])
            info["features_en"] = "; ".join(features[:6])

        # developer info
        for line in readme_text.splitlines():
            if "开发" in line and ("团队" in line or "科室" in line):
                info["dev_team"] = line.strip().lstrip("#").strip()
                break

    return info


# ---------------------------------------------------------------------------
# 字幕生成器 / Subtitle Generator
# ---------------------------------------------------------------------------

def _generate_subtitles_md(info: dict[str, str], steps: list[dict], out_path: Path) -> None:
    """根据项目信息和步骤列表生成双语字幕 markdown"""

    def _time_range(start_s: float, end_s: float) -> str:
        return f"{start_s:.0f}s – {end_s:.0f}s"

    today = datetime.now().strftime("%Y-%m-%d")

    lines: list[str] = []
    lines.append(f"# {info['app_name']} 功能演示视频字幕 / Demo Video Subtitles")
    lines.append("")
    lines.append(
        "> 字幕按时间顺序排列，每条包含中文、英文双语。"
        "时间戳为参考值，录制时可按实际节奏微调。"
    )
    lines.append(
        "> Subtitles are in chronological order, each with Chinese and English text. "
        "Timestamps are approximate — adjust per actual recording pace."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 时间线总览 / Timeline Overview")
    lines.append("")
    lines.append("| # | 时间段 (s) | 阶段 / Stage |")
    lines.append("|---|---|---|")

    current_time = 0.0
    for i, step in enumerate(steps, 1):
        dur = step.get("duration", 12.0)
        rng = _time_range(current_time, current_time + dur)
        lines.append(f"| {i:02d} | {rng} | {step['label_cn']} / {step['label_en']} |")
        current_time += dur

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 字幕正文 / Subtitle Content")
    lines.append("")

    current_time = 0.0
    for i, step in enumerate(steps, 1):
        dur = step.get("duration", 12.0)
        rng = _time_range(current_time, current_time + dur)
        cn = step.get("cn", step.get("label_cn", ""))
        en = step.get("en", step.get("label_en", ""))

        lines.append("---")
        lines.append("")
        lines.append(f"### #{i:02d} · {step['label_cn']} / {step['label_en']}")
        lines.append(f"> {rng}")
        lines.append("")
        lines.append(f"**CN (中文)：**")
        lines.append(f"{cn}")
        lines.append("")
        lines.append(f"**EN (English)：**")
        lines.append(f"{en}")
        lines.append("")
        current_time += dur

    lines.append("---")
    lines.append("")
    lines.append("## 附录：关键术语中英对照 / Appendix: Key Terminology")
    lines.append("")
    lines.append("| 中文 | English |")
    lines.append("|---|---|")

    last_step = steps[-1] if steps else {}
    terms = last_step.get("terms", []) if isinstance(last_step, dict) else []
    if not terms:
        terms = [
            ("防呆设计", "Error-proofing / Foolproofing Design"),
            ("质心最近原则", "Centroid Nearest Principle"),
            ("分型/聚类", "Phenotyping / Clustering"),
            ("衍生指标", "Derived Indicators"),
            ("归档", "Archive / Archiving"),
            ("回填", "Autofill / Backfill"),
            ("校验", "Validation"),
            ("弹窗", "Dialog / Popup"),
            ("快捷键", "Keyboard Shortcut"),
            ("离线运行", "Offline Operation"),
            ("开源许可证", "Open-Source License"),
            ("数据落盘", "Data Persistence / Local Storage"),
        ]
    for cn, en in terms:
        lines.append(f"| {cn} | {en} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*字幕文件结束 / End of Subtitle File*")
    lines.append(f"*生成日期：{today} / Generated: {today}*")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [OK] 字幕已生成：{out_path}")


# ---------------------------------------------------------------------------
# 自动化脚本模板 / Automation Script Template
# ---------------------------------------------------------------------------
# 模板中的占位符说明：
#   {app_name}         — 应用中文名
#   {app_name_en}      — 应用英文名
#   {entry_file}       — 入口文件名
#   {step_interval}    — 步骤间隔
#   {type_interval}    — 打字间隔
#   {long_pause}       — 长暂停
#   {features_cn}      — 功能概览（中文）
#   {features_en}      — 功能概览（英文）
#   {dev_team}         — 开发团队
#   {dev_contact}      — 联系方式
#
# 模板仅提供框架与工具函数。Agent 调用此 skill 时，必须：
#   1. 深入审查项目源码，理解实际 UI 布局
#   2. 将 TODO 占位替换为项目专属的操作序列
#   3. 确保字幕与操作一一对应
#   4. 至少包含 2~3 个防呆演示环节
# ---------------------------------------------------------------------------

AUTOMATION_SCRIPT_TEMPLATE = r'''# -*- coding: utf-8 -*-
# ============================================================
# {app_name} 功能演示自动化脚本
# 用途：运行本脚本后，开始自动操作应用程序，
#       配合屏幕录制软件录制功能演示视频。
# 使用前：先手动启动应用 ({entry_file})，
#         确保主窗口/对话框可见且在前台。
# 依赖：pip install pyautogui
# ============================================================
# Demo Automation Script for {app_name_en}
# Prerequisites: Launch the app ({entry_file}) first,
#                ensure the main window/dialog is visible and in focus.
# Dependency: pip install pyautogui
# ============================================================

from __future__ import annotations

import sys
import time

# ---------- 可配置参数 / Configurable Parameters ----------
STEP_INTERVAL = {step_interval}       # 步骤间基础间隔时间（秒）/ Base interval between steps
TYPE_INTERVAL = {type_interval}       # 打字间隔（秒）/ Typing interval
LONG_PAUSE = {long_pause}            # 长暂停（秒），用于展示弹窗 / Long pause for dialogs
SHORT_PAUSE = 1.0                   # 短暂停（秒）/ Short pause

# pyautogui 延迟导入，避免初始化时干扰正在运行的 PyQt 应用
# Lazy import to prevent interfering with the running PyQt app during init
_pyautogui = None


def _pa():
    """获取 pyautogui 模块引用 / Get pyautogui module reference"""
    assert _pyautogui is not None, "pyautogui 尚未初始化，请勿在 main() 之前调用 / pyautogui not initialized"
    return _pyautogui

# ---------- 字幕输出 / Subtitle Output ----------
_subtitle_index = 0
_subtitle_start: dict[int, float] = {{}}
_start_time: float = 0.0


def _now() -> float:
    return time.time() - _start_time


def subtitle(text_cn: str, text_en: str) -> None:
    """打印中英文字幕并记录时间戳 / Print bilingual subtitle and record timestamp"""
    global _subtitle_index
    t = _now()
    _subtitle_index += 1
    _subtitle_start[_subtitle_index] = t
    line = f"[{{t:6.1f}}s] #{{_subtitle_index}}"
    print(f"\n{{'=' * 70}}")
    print(f"{{line}}")
    print(f"  CN: {{text_cn}}")
    print(f"  EN: {{text_en}}")
    print(f"{{'=' * 70}}\n")


def step_wait(extra: float = 0.0) -> None:
    """步骤间等待 / Wait between steps"""
    time.sleep(STEP_INTERVAL + extra)


def pause_long() -> None:
    """长暂停（展示弹窗/结果用）/ Long pause for displaying dialogs/results"""
    time.sleep(LONG_PAUSE)


def pause_short() -> None:
    """短暂停 / Short pause"""
    time.sleep(SHORT_PAUSE)


_clipboard_tk = None


def _set_clipboard(text: str) -> None:
    """Windows 剪贴板写入（绕过输入法中英文切换问题）
    Set Windows clipboard via tkinter — bypasses IME input mode."""
    global _clipboard_tk
    if _clipboard_tk is None:
        import tkinter
        _clipboard_tk = tkinter.Tk()
        _clipboard_tk.withdraw()
    _clipboard_tk.clipboard_clear()
    _clipboard_tk.clipboard_append(text)
    _clipboard_tk.update()


def type_text(text: str) -> None:
    """粘贴文本（通过剪贴板 Ctrl+V，绕过输入法中英文切换问题）
    Paste text via clipboard Ctrl+V — bypasses IME input mode issues."""
    _set_clipboard(text)
    time.sleep(0.06)
    _pa().hotkey("ctrl", "v")


def click_button(label_cn: str, label_en: str, hotkey: str | None = None) -> None:
    """点击按钮：优先使用快捷键，否则尝试屏幕定位后点击
    Click button: prefer hotkey, fallback to screen locate + click"""
    if hotkey:
        _pa().hotkey(*hotkey.split("+"))
    else:
        try:
            btn = _pa().locateOnScreen(label_cn, confidence=0.85)
            if btn is None:
                raise Exception("not found")
            _pa().click(_pa().center(btn))
        except Exception:
            _pa().press("enter")


def close_dialog(key: str = "enter") -> None:
    """关闭弹窗（默认 Enter，也可用 Escape）
    Close dialog (default Enter, also supports Escape)"""
    pause_short()
    _pa().press(key)
    pause_short()


# ============================================================
# 主演示流程 / Main Demo Flow
# ============================================================


def main() -> None:
    global _start_time, _pyautogui

    print("=" * 70)
    print("{app_name} 功能演示自动化脚本 / Demo Automation Script")
    print("请确保应用已启动，焦点在主窗口上。")
    print("Please ensure app is running and in focus.")
    print()
    print("准备好后按 Enter 开始自动演示...")
    print("Press Enter when ready to start the demo...")
    print("=" * 70)
    input()

    # 延迟导入 pyautogui，避免初始化时干扰正在运行的 PyQt 应用
    # Lazy import to prevent interfering with the running PyQt app during init
    try:
        import pyautogui
    except ImportError:
        print("请先安装依赖：pip install pyautogui")
        print("Please install: pip install pyautogui")
        sys.exit(1)

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.15
    _pyautogui = pyautogui

    _start_time = time.time()

    # ========================================================
    # 阶段 0：开场介绍 / Opening Introduction
    # ========================================================
    subtitle(
        "欢迎观看\u201c{app_name}\u201d的功能演示。",
        "Welcome to the demo of {app_name_en}."
    )
    pause_long()

    subtitle(
        "{features_cn}",
        "{features_en}"
    )
    pause_long()

    subtitle(
        "接下来，我们将演示核心功能。",
        "We will now demonstrate the core features."
    )
    pause_long()

    # ========================================================
    # ⚠️ 以下为占位步骤，请根据实际 UI 布局替换 ⚠️
    # ⚠️ Placeholder steps below — replace with actual UI layout ⚠️
    #
    # 常用操作模式参考 / Common operation pattern reference:
    #
    #   输入文本：           type_text("内容")
    #   Tab 前进一个字段：   pyautogui.press("tab")
    #   Shift+Tab 后退：    pyautogui.hotkey("shift", "tab")
    #   删除 N 个字符：     pyautogui.press("backspace", presses=N)
    #   Alt+字母快捷键：    pyautogui.hotkey("alt", "r")
    #   关闭弹窗(Enter)：   close_dialog()
    #   关闭弹窗(Escape)：  close_dialog("escape")
    #   导航栏点击：        pyautogui.click(x, y)
    #   菜单 Alt 触发：     pyautogui.hotkey("alt", "e"); pyautogui.press("c")
    # ========================================================

    # --- 阶段 1：登录 / Login ---
    subtitle(
        "进入登录界面，输入账号密码。",
        "Entering the login dialog and typing credentials."
    )
    step_wait()
    # TODO: type_text("demo_user")
    # TODO: pyautogui.press("tab")
    # TODO: type_text("password")
    # TODO: pyautogui.press("enter")
    # TODO: 或使用快捷键 / or use hotkey: pyautogui.hotkey("alt", "l")
    pause_long()

    # --- 阶段 2：防呆设计演示 1 — 空表单提交 / Error-proofing 1: Empty form ---
    subtitle(
        "【防呆设计演示 1】空表单提交验证。",
        "[Error-proofing Demo 1] Empty form submission validation."
    )
    step_wait()
    # TODO: pyautogui.hotkey("alt", "s")  # 触发提交快捷键
    pause_long()
    close_dialog()  # 按 Enter 关闭弹窗

    # --- 阶段 3：防呆设计演示 2 — 无效数据 / Error-proofing 2: Invalid data ---
    subtitle(
        "【防呆设计演示 2】无效数据输入验证。",
        "[Error-proofing Demo 2] Invalid data input validation."
    )
    step_wait()
    # TODO: 先填入部分有效数据，然后在目标字段填入非法值
    # TODO: type_text("ZY01000123456"); pyautogui.press("tab")
    # TODO: ...多次 tab 导航到目标字段...
    # TODO: type_text("300")  # 非法值
    # TODO: pyautogui.hotkey("alt", "s")
    pause_long()
    close_dialog()

    # --- 阶段 3.5：修正数据 / Correct data ---
    subtitle(
        "修正为有效数据。使用 Shift+Tab 回退到错误字段。",
        "Correcting to valid data. Using Shift+Tab to go back to the error field."
    )
    step_wait()
    # TODO: pyautogui.hotkey("shift", "tab")  # 多次回退到目标字段
    # TODO: pyautogui.press("backspace", presses=3)  # 删除错误值
    # TODO: type_text("170")  # 填入正确值
    step_wait()

    # --- 阶段 4：防呆设计演示 3 — 格式校验 / Error-proofing 3: Format check ---
    subtitle(
        "【防呆设计演示 3】格式校验验证。",
        "[Error-proofing Demo 3] Format validation check."
    )
    step_wait()
    # TODO: pyautogui.press("tab")  # 多次 tab 到格式敏感字段
    # TODO: type_text("12345")  # 非法格式
    # TODO: pyautogui.hotkey("alt", "s")
    pause_long()
    close_dialog()

    # --- 阶段 4.5：修正格式 / Fix format ---
    subtitle(
        "修正为正确格式并补全所有字段。",
        "Correcting format and completing all fields."
    )
    step_wait()
    # TODO: pyautogui.hotkey("shift", "tab")  # 回退到错误字段
    # TODO: pyautogui.press("backspace", presses=5)
    # TODO: type_text("13800138000")
    # TODO: 补全剩余必填字段 / Fill remaining required fields
    step_wait()

    # --- 阶段 5：正常操作流程 / Normal operation ---
    subtitle(
        "所有字段填写完毕，提交并生成结果。",
        "All fields completed. Submitting and generating results."
    )
    step_wait()
    # TODO: pyautogui.hotkey("alt", "s")
    pause_long()

    # --- 阶段 6：结果展示 / Result display ---
    subtitle(
        "操作成功！查看系统生成的结果。",
        "Operation successful! Viewing the generated result."
    )
    pause_long()

    # --- 阶段 7：菜单/扩展演示 / Menu/Extension demo ---
    subtitle(
        "浏览菜单栏和扩展功能。",
        "Browsing menu bar and extension features."
    )
    step_wait()
    # TODO: pyautogui.hotkey("alt", "e")  # 打开扩展菜单
    # TODO: pyautogui.press("x")          # 按菜单项加速键
    # TODO: 或使用导航栏点击 / or use nav click: pyautogui.click(100, 300)
    pause_long()
    # TODO: close_dialog("escape")  # 如为独立弹窗则关闭

    # ========================================================
    # 结尾总结 / Conclusion
    # ========================================================
    subtitle(
        "以上是{app_name}的核心功能演示。",
        "This concludes the core feature demo of {app_name_en}."
    )
    pause_long()

    subtitle(
        "{dev_team}开发。项目遵循学术软件规范，"
        "采用分层架构、配置外置、防呆校验和滚动日志追踪。",
        "Developed by {dev_team}. "
        "The project follows academic software standards: "
        "layered architecture, external configuration, "
        "error-proofing validation, and rolling log tracking."
    )
    pause_long()

    subtitle(
        "感谢观看。联系方式：{dev_contact}",
        "Thank you for watching. Contact: {dev_contact}"
    )
    pause_long()

    # 打印字幕时间戳汇总 / Print subtitle timestamp summary
    print("\n" + "=" * 70)
    print("字幕时间戳汇总 / Subtitle Timestamp Summary")
    print("=" * 70)
    for idx in sorted(_subtitle_start):
        t = _subtitle_start[idx]
        print(f"  #{{idx:02d}}  @ {{t:6.1f}}s")
    print("=" * 70)
    print("演示完成！/ Demo Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
'''


# ---------------------------------------------------------------------------
# 默认步骤模板
# ---------------------------------------------------------------------------

def _default_steps(info: dict[str, str]) -> list[dict]:
    """生成默认的演示步骤列表（各项目可据此定制）"""
    return [
        # ==================== 开头介绍 ====================
        {
            "label_cn": "项目简介",
            "label_en": "Project Introduction",
            "duration": 12,
            "cn": (
                f'欢迎观看\u201c{info["app_name"]}\u201d的功能演示。'
                f'本系统由{info["dev_team"]}开发，'
                f'当前版本 v{info["version"]}。'
            ),
            "en": (
                f'Welcome to the demo of "{info["app_name_en"]}". '
                f"Developed by {info['dev_team']}, "
                f"current version v{info['version']}."
            ),
        },
        {
            "label_cn": "功能概览",
            "label_en": "Feature Overview",
            "duration": 12,
            "cn": f'本系统核心功能包括：{info["features_cn"]}',
            "en": f'Core features include: {info["features_en"]}',
        },
        {
            "label_cn": "演示预告",
            "label_en": "Demo Preview",
            "duration": 8,
            "cn": "接下来，我们将依次演示系统的主要功能模块。",
            "en": "We will now demonstrate the system's main functional modules in sequence.",
        },
        # ==================== 登录流程 ====================
        {
            "label_cn": "登录界面",
            "label_en": "Login Interface",
            "duration": 10,
            "cn": "首先进入登录界面。系统要求用户进行身份认证。",
            "en": "First, we see the login dialog. The system requires user authentication.",
        },
        {
            "label_cn": "输入账号密码",
            "label_en": "Enter Credentials",
            "duration": 8,
            "cn": "输入演示账号和密码，点击登录。",
            "en": "Entering the demo account and password, then clicking Sign In.",
        },
        {
            "label_cn": "点击登录",
            "label_en": "Click Sign In",
            "duration": 8,
            "cn": "系统验证通过后进入主界面。",
            "en": "After successful verification, the main interface opens.",
        },
        # ==================== 防呆设计 ====================
        {
            "label_cn": "防呆演示1：空表单",
            "label_en": "Error-proofing 1: Empty Form",
            "duration": 15,
            "cn": (
                "【防呆设计演示一】所有字段留空直接提交。"
                "系统弹出警告提示必填项不可为空。"
                "防呆校验确保关键字段不会被遗漏。"
            ),
            "en": (
                "[Error-proofing Demo 1] Submitting with all fields empty. "
                "The system warns that required fields cannot be blank. "
                "Error-proofing ensures no critical field is missed."
            ),
        },
        {
            "label_cn": "防呆演示2：范围校验",
            "label_en": "Error-proofing 2: Range Check",
            "duration": 15,
            "cn": (
                "【防呆设计演示二】输入超出合理范围的数值。"
                "系统弹出警告提示值域限制。"
                "所有关键指标均预先定义了医学/业务合理区间。"
            ),
            "en": (
                "[Error-proofing Demo 2] Entering values outside reasonable range. "
                "The system warns about value range limits. "
                "All key indicators have pre-defined reasonable ranges."
            ),
        },
        {
            "label_cn": "防呆演示3：格式校验",
            "label_en": "Error-proofing 3: Format Check",
            "duration": 15,
            "cn": (
                "【防呆设计演示三】输入不符合格式要求的数据。"
                "系统弹出警告提示格式规则。"
                "格式校验覆盖电话号码、身份证号等结构化字段。"
            ),
            "en": (
                "[Error-proofing Demo 3] Entering data with invalid format. "
                "The system warns about format rules. "
                "Format validation covers phone numbers, IDs, and other structured fields."
            ),
        },
        # ==================== 正常操作 ====================
        {
            "label_cn": "修正数据并提交",
            "label_en": "Correct and Submit",
            "duration": 12,
            "cn": "修正为有效数据，完整填写所有必填项后提交。",
            "en": "Correcting to valid data, completing all required fields, and submitting.",
        },
        {
            "label_cn": "操作结果展示",
            "label_en": "Result Display",
            "duration": 15,
            "cn": "操作成功！查看系统生成的结果摘要。",
            "en": "Operation successful! Viewing the generated result summary.",
        },
        # ==================== 菜单/扩展 ====================
        {
            "label_cn": "菜单浏览",
            "label_en": "Menu Browse",
            "duration": 15,
            "cn": "通过菜单栏访问扩展功能和系统信息。",
            "en": "Accessing extension features and system info via the menu bar.",
        },
        # ==================== 结尾总结 ====================
        {
            "label_cn": "功能总结",
            "label_en": "Feature Summary",
            "duration": 15,
            "cn": (
                "以上就是本系统的核心功能演示。"
                "系统现已支持登录认证、数据录入校验、"
                "结果显示与导出等完整业务闭环。"
            ),
            "en": (
                "This concludes the core feature demo. "
                "The system now supports complete business workflows "
                "including authentication, data entry validation, "
                "result display and export."
            ),
        },
        {
            "label_cn": "开发过程总结",
            "label_en": "Development Summary",
            "duration": 15,
            "cn": (
                "开发过程中严格遵循学术软件规范："
                "分层架构使 UI 与业务逻辑分离；"
                "配置外置 YAML 支持热更新；"
                "防呆校验机制确保输入合规；"
                "滚动日志追踪所有关键操作。"
            ),
            "en": (
                "Development strictly followed academic software standards: "
                "layered architecture separates UI from business logic; "
                "external YAML configuration enables hot updates; "
                "error-proofing validation ensures input compliance; "
                "rolling logs track all critical operations."
            ),
        },
        {
            "label_cn": "致谢",
            "label_en": "Acknowledgments",
            "duration": 20,
            "cn": (
                f"本系统由{info['dev_team']}开发。"
                f"项目遵循 {info['license']} 协议开源。"
                "感谢观看。如有合作意向，欢迎联系开发者："
                f"{info['dev_contact']}。"
            ),
            "en": (
                f"Developed by {info['dev_team']}. "
                f"Open-source under {info['license']}. "
                "Thank you for watching. For collaboration inquiries, "
                f"please contact: {info['dev_contact']}."
            ),
        },
    ]


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SC7_ShowVideo - 演示视频配套材料生成器",
    )
    parser.add_argument("--repo-root", required=True, type=Path, help="项目根目录")
    parser.add_argument("--project-name", default="Project", help="项目名称（产物命名用）")
    parser.add_argument("--app-config", type=Path, help="YAML 配置文件路径（默认 repo-root/app_config.yaml）")
    parser.add_argument("--readme", type=Path, help="README 文件路径（默认 repo-root/README.md）")
    parser.add_argument("--entry-file", type=Path, help="应用入口文件路径（默认 repo-root/main.py）")
    parser.add_argument("--out-dir", type=Path, help="产物输出目录（默认 repo-root/show）")
    parser.add_argument("--step-interval", type=float, default=2.5, help="步骤间间隔秒数（默认 2.5）")
    parser.add_argument("--type-interval", type=float, default=0.08, help="打字间隔秒数（默认 0.08）")
    parser.add_argument("--long-pause", type=float, default=4.0, help="长暂停秒数（默认 4.0）")

    args = parser.parse_args()

    repo_root: Path = args.repo_root.resolve()
    project_name: str = args.project_name
    app_config: Path = args.app_config or (repo_root / "app_config.yaml")
    readme: Path = args.readme or (repo_root / "README.md")
    entry_file: Path = args.entry_file or (repo_root / "main.py")
    out_dir: Path = args.out_dir or (repo_root / "show")
    step_interval: float = args.step_interval
    type_interval: float = args.type_interval
    long_pause: float = args.long_pause

    print(f"SC7_ShowVideo - 演示视频配套材料生成器")
    print(f"  项目根目录: {repo_root}")
    print(f"  配置文件:   {app_config} ({'存在' if app_config.exists() else '不存在'})")
    print(f"  README:     {readme} ({'存在' if readme and readme.exists() else '不存在'})")
    print(f"  输出目录:   {out_dir}")
    print()

    # 解析项目信息
    info = _parse_app_info(app_config, readme)
    info["app_name_en"] = info["app_name"]
    info["entry_file"] = entry_file.name
    info["step_interval"] = step_interval
    info["type_interval"] = type_interval
    info["long_pause"] = long_pause

    print("提取的项目信息：")
    for k, v in info.items():
        val = str(v)[:80]
        print(f"  {k}: {val}")
    print()

    # 确保输出目录存在
    out_dir.mkdir(parents=True, exist_ok=True)

    # 生成自动化脚本（值中的花括号需转义，防止 .format() 崩溃）
    # Escape curly braces in values to prevent .format() from crashing
    automation_path = out_dir / "demo_automation.py"
    safe_info = {k: str(v).replace("{", "{{").replace("}", "}}") for k, v in info.items()}
    script_content = AUTOMATION_SCRIPT_TEMPLATE.format(**safe_info)
    automation_path.write_text(script_content, encoding="utf-8")
    print(f"  [OK] 自动化脚本已生成：{automation_path}")

    # 生成字幕文件
    steps = _default_steps(info)
    subtitle_path = out_dir / "subtitles.md"
    _generate_subtitles_md(info, steps, subtitle_path)

    print()
    print("=" * 70)
    print("生成完成！/ Generation Complete!")
    print()
    print("使用步骤：")
    print(f"  1. 先启动应用：python {entry_file.name}")
    print(f"  2. 启动屏幕录制软件（如 OBS）")
    print(f"  3. 运行自动化脚本：python {automation_path}")
    print(f"  4. 按字幕文件 {subtitle_path} 配音或叠加字幕")
    print("=" * 70)


if __name__ == "__main__":
    main()
