---
name: "SC2_OriginalCode"
description: "生成软著源码文档（源码汇总MD + LaTeX排版 + PDF编译）。当用户提到“生成软著源码文档/软著源码PDF/提交源码材料”时调用。"
---

# SC2 原始代码文档生成（软著源码材料）

当用户要求“生成软著源码文档”时，执行以下流程，输出可用于软件著作权申请提交的源码材料文件。

## 可迁移结构（推荐）

把整个目录 `.trae/skills/SC2_OriginalCode/` 视为可复制的独立工具包，其中：

- `SKILL.md`：使用说明与交付规范
- `bundle/sc2_original_code.py`：可直接复制到任意项目使用的生成脚本（不依赖本项目特定路径）

## 适用项目（本仓库默认）

- 需要遍历的源码范围：
  - `src/winfront_app/` 下全部文件
  - `main.py`
  - `app_config.yaml`
- 忽略规则：
  - 读取仓库根目录 `.gitignore`，按其中规则过滤（至少覆盖目录忽略与通配符忽略）

## 产物

- `SC_{项目名}_2_OriginalCode.md`
  - 结构：按相对路径顺序排列：红色标题行（正文红色，不用标题语法）+ 换行 + 源码内容
  - 标题建议格式：`<span style="color:red">relative/path</span>`
- `SC_{项目名}_2_OriginalCode_wrapped.md`
  - 说明：为保证“PDF每页固定50行”和“截取规则按文本行数”一致，先按每行可容纳字符数将 MD 预切分为“不会在 TeX 中再次自动换行”的版本
  - 规则：删除空行但不改变缩进；对超长行按缩进对齐进行分行（续行保持原缩进）
- `SC_{项目名}_2_OriginalCode.tex`
  - A4
  - 边距：上/下约 2.5cm；左/右约 2cm
  - 字体：Times New Roman，8pt
  - 页眉：从 `app_config.yaml` 读取 `application_display_name` + `app_version`（例：`xxx V1.0`）
  - 页脚：页码“第X页/共X页”
  - 内容：左侧行号、右侧正文；正文来自 `*_wrapped.md`，标题保持红色
  - 每页固定 50 行：在 TeX 中每 50 行强制分页（行号与页数严格对应）
  - 若总行数 > 3000（>60页），仅保留前 1500 行与后 1500 行；行号会在后半段跳转为“总行数-1500+1”，以便最后一行号体现真实文本行数
- `SC_{项目名}_2_OriginalCode.pdf`
  - 由 tex 编译生成（推荐 xelatex 以确保 Times New Roman 与中文）

## 推荐实现（仓库内脚本）

使用仓库脚本生成：

- `scripts/sc2_original_code.py`

也可以直接使用可迁移脚本（建议复制到目标项目的 `scripts/` 目录）：

- `.trae/skills/SC2_OriginalCode/bundle/sc2_original_code.py`

运行方式（示例）：

- 仅生成 Markdown：`python scripts/sc2_original_code.py --step md`
- 生成预切分 Markdown：`python scripts/sc2_original_code.py --step wrap`
- 生成 TeX：`python scripts/sc2_original_code.py --step tex`
- 编译 PDF：`python scripts/sc2_original_code.py --step pdf`
- 一次生成全部：`python scripts/sc2_original_code.py --step all`

跨项目/自定义范围（关键参数）：

- `--include`：要遍历的目录/文件（可重复传入）
- `--extra`：额外单文件（可重复传入）
- `--app-config`：用于页眉的软件名与版本号来源（默认 `app_config.yaml`）
- `--ignore-file`：忽略规则文件（默认 `.gitignore`）
- `--out-dir`：产物输出目录（建议指定到一个文件夹，便于打包迁移）

交付要求：

- 按用户要求分步骤生成，并在每一步产物生成后等待用户确认再继续下一步。

## 示例（脱敏）

```text
产物示例：
- SC_Project_2_OriginalCode.md
- SC_Project_2_OriginalCode_wrapped.md
- SC_Project_2_OriginalCode.tex
- SC_Project_2_OriginalCode.pdf
```
