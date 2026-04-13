---
name: "SC3_UserManual"
description: "生成软著用户手册（批量截图→UserManual.tex→PDF 编译）。当用户提到“生成用户手册/批量图片生成手册/软著手册PDF”时调用。"
---

# SC3 用户手册生成（软著文档鉴别材料）

当用户要求“生成软著用户手册 / 批量图片生成手册 / 输出用户手册 TeX+PDF”时，执行本流程：扫描截图目录 → 自动生成 LaTeX → 编译 PDF，输出可用于软著申请提交的用户手册材料。

## 可迁移结构（推荐）

把整个目录 `.trae/skills/SC3_UserManual/` 视为可复制的独立工具包：

- `SKILL.md`：使用说明与交付规范
- `bundle/sc3_user_manual.py`：可直接复制到任意项目使用的生成脚本（仅依赖 Python 标准库 + xelatex）

## 输入约定

### 1) 截图目录

传入 `--manual-dir` 指向截图目录。文件名约定：

- `章节号-序号图名.png|jpg|jpeg`
- 例：`3-2填写人口学信息（错误日期）.png`

脚本会按“章节号 → 序号”排序，并把“图名”用作图注与扩展说明标题来源。

### 2) 页眉信息来源

传入 `--app-config` 指向 YAML 配置文件（默认 `app_config.yaml`），从中读取：

- `app.application_display_name`
- `app.app_version`

页眉输出为：`display_name + version`（例：`xxx V1.0`）。

## 排版规则（已固化）

- A4；边距：上/下 2.5cm、左/右 2cm（参考软著材料常用边距）
- 中文宋体（SimSun，若无则回退微软雅黑），英文/数字 Times New Roman；正文字号 12pt
- 页眉：软件名 + 版本号；页脚：`第X页/共Y页`
- 目录仅到一级目录：`tocdepth=1`
- 第 1 节：前言正文 + 红色严正声明（不强制另起一页），其后 `\newpage`
- 第 8 节：单独一页；最后一句另起段

### 图片宽度（按像素宽度分档）

读取图片像素宽度后自动设置：

- `≤600`：`1/3` 页宽
- `601~1200`：`1/2` 页宽
- `1200~1800`：`2/3` 页宽
- `>1800`：`3/4` 页宽

所有图片保持水平居中。

## 产物

- `SC_{项目名}_4_UserManual.tex`
- `SC_{项目名}_4_UserManual.pdf`

默认输出到 `--repo-root`（不传则取脚本所在目录向上两级作为仓库根）。

## 使用方式

推荐直接运行可迁移脚本 `bundle/sc3_user_manual.py`（复制到目标项目的 `scripts/` 后运行）。

示例：

```bash
python .trae/skills/SC3_UserManual/bundle/sc3_user_manual.py ^
  --repo-root d:\MyProject ^
  --manual-dir d:\MyProject\manual ^
  --app-config d:\MyProject\app_config.yaml ^
  --project-name MyProject ^
  --publish-date-cn 2026年04月12日 ^
  --engine xelatex ^
  --out-tex d:\MyProject\SC_MyProject_4_UserManual.tex
```

跨项目迁移时（复制 bundle 脚本到目标项目）：

```bash
python scripts/sc3_user_manual.py --manual-dir ./manual --app-config ./app_config.yaml --project-name MyProject --engine xelatex
```

## 交付规范

- 生成 `.tex` 后先让用户确认排版与文案，再进行 PDF 编译或继续迭代修改。
