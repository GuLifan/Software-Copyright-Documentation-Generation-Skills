---
name: "SC4_SupportingMaterial"
description: "生成软著佐证材料（输入 docx/md 等→整理为 SupportingMaterial.md→转 PDF）。当用户提到“生成软著佐证/佐证材料PDF/开发需求转佐证”时调用。"
---

# SC4 佐证材料生成（软著相关证明/开发需求/引用片段整理）

当用户要求“生成软著佐证材料 / 把 docx 或参考材料整理成佐证 PDF”时，执行以下流程：

1) 读取用户提供的参考材料（常见为 `.docx/.md/.txt`，也可包含仅用于登记的 `.pdf`）
2) 统一整理为 `SC_{项目名}_4_SupportingMaterial.md`
3) 将上述 Markdown 转为 `SC_{项目名}_4_SupportingMaterial.pdf`

说明：佐证材料 PDF 不强调“严格 LaTeX 排版”，更接近 HTML 文档风格（脚本会优先走 HTML→PDF 路线；若环境缺少 HTML→PDF 工具，会自动回退到可编译的 XeLaTeX 简版）。

## 可迁移结构（推荐）

把整个目录 `.trae/skills/SC4_SupportingMaterial/` 视为可复制的独立工具包：

- `SKILL.md`：使用说明与交付规范
- `bundle/sc4_supporting_material.py`：可直接复制到任意项目使用的生成脚本（优先标准库；PDF 生成支持多后端自动探测）

## 输入约定

- `--inputs`：可重复传入多个文件路径（`.docx/.md/.txt/.pdf`）
- `--project-name`：用于产物命名（默认 `Project`）
- `--title/--author/--date`：用于生成与示例一致的封面标题行与署名行（可不填，脚本会尽力从材料中推断）

## 产物

- `SC_{项目名}_4_SupportingMaterial.md`
- `SC_{项目名}_4_SupportingMaterial.pdf`

## 示例（脱敏）

示例结构参考（来自“开发需求”类材料）：

```md
# 某某系统开发需求

#### *某某 2026-03-25*

## 1 基本功能需求

1. 医师登录/注册界面
2. 患者建档
3. 录入患者信息与实验室指标
```

## 使用方式（示例）

```bash
python .trae/skills/SC4_SupportingMaterial/bundle/sc4_supporting_material.py ^
  --repo-root d:\MyProject ^
  --project-name MyProject ^
  --inputs d:\MyProject\软著-0需求.docx ^
  --inputs d:\MyProject\软著-引用片段.md ^
  --title "某某系统开发需求" ^
  --author "某某" ^
  --date 2026-03-25
```

## 交付规范

- 先生成 `.md` 并让用户确认“标题/目录层级/表格是否完整/是否包含材料清单”，再生成 PDF（或在同一命令中一次性生成）。
