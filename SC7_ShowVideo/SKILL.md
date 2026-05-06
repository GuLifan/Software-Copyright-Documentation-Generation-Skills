---
name: "SC7_ShowVideo"
description: "生成项目功能演示视频配套材料（自动化操作脚本+时间轴中英字幕Markdown）。当用户提到“制作演示视频/录屏脚本/视频字幕/academic demo video”时调用。"
---

# SC7 演示视频配套材料生成（自动化脚本 + 中英字幕）

当用户要求"制作功能演示视频 / 生成录屏脚本 / 写视频字幕 / demo video script"时，执行以下流程：

1) 深入审查项目源码，理解核心功能、UI 交互、校验逻辑（特别是弹窗/错误提示等"防呆设计"）
2) 设计覆盖所有核心功能的演示流程，确保包含至少 2~3 个错误校验（弹窗）环节
3) 生成 pyautogui 自动化操作脚本 `demo_automation.py`，模拟真人操作节奏
4) 生成按时间排序的中英双语字幕 Markdown 文件 `subtitles.md`

## 可迁移结构（推荐）

把整个目录 `.trae/skills/SC7_ShowVideo/` 视为可复制的独立工具包：

- `SKILL.md`：使用说明与交付规范
- `bundle/sc7_show_video.py`：可直接复制到任意项目使用的生成脚本（尽量仅依赖标准库）

## 输入与来源

- `--repo-root`：项目根目录（必填）
- `--project-name`：产物命名用项目名（必填）
- `--app-config`：项目 YAML 配置（默认 `app_config.yaml`），用于提取应用名、版本号
- `--readme`：项目说明文件（默认 `README.md`），用于提取功能概览文字
- `--entry-file`：应用入口文件（默认 `main.py`），用于定位 src 源码目录
- `--out-dir`：产物输出目录（默认 `--repo-root/show`）
- `--step-interval`：步骤间基础间隔时间秒数（默认 2.5）
- `--type-interval`：打字间隔秒数（默认 0.08）
- `--long-pause`：弹窗展示长暂停秒数（默认 4.0）

## 审查流程（关键）

生成脚本和字幕前，必须完成以下审查：

### A. 项目全貌审查
- 读取 `README.md` 或等价说明，提取功能列表、项目背景、开发者信息
- 读取 `app_config.yaml` 或等价配置，提取应用全称、版本号、窗口标题
- 扫描 `src/` 源码目录，理解分层架构（UI / Logic / Service 层）

### B. UI 流程识别
- 逐个阅读页面/对话框源码，梳理用户操作路径
- **重点关注**：登录流程、表单录入→提交→结果、菜单操作、弹窗触发
- 记录每个步骤的控件类型（按钮、输入框、下拉框、复选框）和触发方式（点击/快捷键/Tab导航）

### C. 防呆设计环节识别（核心要求）
- 扫描所有 `QMessageBox.warning` / `QMessageBox.critical` / `QMessageBox.information` 调用
- 扫描所有 `raise ValueError` 调用（业务校验层）
- 识别表单校验逻辑（空值检查、范围校验、格式校验）
- **确保自动脚本中至少包含 2~3 个触发性弹窗演示**，例如：
  - 空 Patient_ID 提交 → "Patient_ID不能为空"
  - 身高超出医学合理范围 → "身高必须在100~250 cm范围内"
  - 手机号格式不正确 → "手机号码必须为1开头的11位数字"

### D. 菜单与扩展功能审查
- 扫描 `QMainWindow._build_menu()` 或等价方法，提取菜单项与触发动作
- 识别"关于"/"扩展"/"设置"等菜单下的弹窗与信息展示

## 产物

### 1. `demo_automation.py`
自动化操作脚本，特点：
- 基于 `pyautogui` 实现键盘输入、Tab 导航、快捷键触发
- 每步操作之间插入合理等待间隔（`time.sleep`）
- 每个操作步骤对应字幕索引号（`#01, #02, ...`）
- 支持 `pyautogui.FAILSAFE`（鼠标移到左上角紧急停止）
- 提供可配置参数：`STEP_INTERVAL`、`TYPE_INTERVAL`、`LONG_PAUSE`、`SHORT_PAUSE`
- 脚本用 `input()` 等待用户就绪（替代固定 sleep，更灵活）
- 内置工具函数：`type_text()`、`click_button()`、`close_dialog(key)`、`pause_long()`、`pause_short()`、`step_wait()`
- `close_dialog(key)` 支持 `"enter"` 和 `"escape"` 两种关闭方式
- pyautogui 延迟导入（`_pyautogui` / `_pa()` 模式），避免干扰 PyQt 应用初始化

### 2. `subtitles.md`
中英双语字幕文件，结构：
- 时间线总览表（#编号、时间段、阶段名称）
- 每条字幕包含：时间段、中文（CN）、英文（EN）
- 字幕分为三个阶段：
  - **开头**（约30s~40s）：项目全面介绍——名称、开发团队、技术栈、功能概览
  - **正文**（按操作步骤逐条）：每步操作对应的解说词（中英双语）
  - **结尾**（约30s~45s）：开发过程总结——架构设计、技术选型、开源信息、联系方式
- 末尾附有关键术语中英对照表
- 字幕总数建议 20~35 条，总时长 4~8 分钟

## 字幕内容要求

### 开头介绍（3~5 条字幕）
必须覆盖：
1. 项目全称与开发团队（来自 config/README）
2. 项目核心功能与技术栈简介
3. 即将演示的功能预告

### 正文操作解说（每步 1 条字幕）
每条字幕应包含：
- 当前操作的叙述（"现在我们输入..."）
- 关键业务含义的解释（"TyG 指数是..."）
- 对于防呆演示环节，明确标注"【防呆设计演示】"并解释校验规则

### 结尾总结（3~5 条字幕）
必须覆盖：
1. 开发过程中遵循的工程规范（分层架构、配置外置、日志追踪、校验机制）
2. 项目开源信息（许可证、GitHub、ORCID）
3. 致谢与联系方式

## 生成策略（Agent 执行指引）

脚本生成优先遵循以下策略：

1. **最大化 UI 源码定位精度**：优先用 `Tab` 键逐字段导航 + `typewrite` 输入，避免依赖屏幕坐标定位（跨分辨率不兼容）
2. **防呆环节优先于正确流程**：先演示空提交/错误输入触发弹窗，再修正为正确值——这种"先错后改"的节奏比直接填对更有演示价值
3. **快捷键优先**：能用 `Alt+字母` 触发按钮的，用快捷键而非鼠标点击（加速演示同时避免坐标定位问题）
4. **弹窗关闭双策略**：默认用 `Enter` 关闭弹窗，但某些对话框（如"关于"/"说明"类独立弹窗）用 `Escape` 更合适——`close_dialog(key)` 支持两种方式
5. **字幕与脚本的索引对应**：`demo_automation.py` 中的 `subtitle()` 调用顺序必须与 `subtitles.md` 中的 `#01, #02, ...` 一一对应
6. **PyQt 兼容：延迟导入 pyautogui**：模板已内置 `_pyautogui = None` → `_pa()` → `main()` 中 `import pyautogui` 的延迟加载模式，避免 import 时干扰已运行的 QApplication

### 核心操作模式速查表

生成脚本时，优先使用以下已验证的成熟模式：

| 操作 | 代码 | 说明 |
|---|---|---|
| 输入文本 | `type_text("内容")` | 逐字模拟打字，间隔 `TYPE_INTERVAL` |
| Tab 前进一个字段 | `pyautogui.press("tab")` | 表单字段间跳转 |
| Shift+Tab 后退 | `pyautogui.hotkey("shift", "tab")` | 回退到前一字段（修正错误值） |
| 删除 N 个字符 | `pyautogui.press("backspace", presses=3)` | 删除错误输入后重新填入 |
| Alt+字母快捷键 | `pyautogui.hotkey("alt", "r")` | 触发按钮（比鼠标点击更可靠） |
| 菜单栏 Alt 触发 | `pyautogui.hotkey("alt", "e"); pyautogui.press("c")` | 先激活菜单，再按子项加速键 |
| 关闭弹窗 (Enter) | `close_dialog()` | 默认 Enter，适用于表单校验弹窗 |
| 关闭弹窗 (Escape) | `close_dialog("escape")` | 适用于独立信息展示弹窗 |
| 导航栏点击 | `pyautogui.click(x, y)` | 坐标定位（仅当无快捷键时使用） |
| 等待就绪信号 | `input()` | 等待用户按 Enter 后开始（替代固定 sleep） |

### "先错后改"节奏编排

每个防呆演示环节必须包含三个连续步骤（各对应一条字幕）：

```
步骤 A：填入错误值 → 提交 → 触发弹窗 → 展示校验规则
步骤 B：Shift+Tab 回退到错误字段 → backspace 删除 → 填入正确值
步骤 C：继续填写 → 进入下一环节
```

确保 **防呆演示 → 修正 → 下阶段** 形成完整的叙事链，而非孤立展示错误弹窗。

## 示例

```bash
python .trae/skills/SC7_ShowVideo/bundle/sc7_show_video.py ^
  --repo-root d:\MyProject ^
  --project-name MyProject ^
  --app-config d:\MyProject\app_config.yaml ^
  --readme d:\MyProject\README.md ^
  --entry-file d:\MyProject\main.py ^
  --out-dir d:\MyProject\show
```

跨项目迁移时（复制 bundle 脚本到目标项目）：

```bash
python scripts/sc7_show_video.py --repo-root . --project-name MyProject --entry-file ./main.py
```

## 交付规范

- 两个产物必须同步交付：`demo_automation.py` 和 `subtitles.md`
- 生成后应提示用户：先启动应用，再运行自动化脚本，同时开启屏幕录制
- 字幕时间戳为参考值，提醒用户可根据实际录制节奏微调
- 字幕文件末尾必须附有关键术语中英对照表（至少 10 对）
