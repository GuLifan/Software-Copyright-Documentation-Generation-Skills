# SC4_SupportingMaterial 示例（脱敏）

本文件用于展示“软著佐证材料”Skill 的输入与输出形态。常见输入包括：开发需求、领导指定参考材料、引用片段等。

## 示例输入 A：开发需求（Markdown）

文件：`supporting_inputs/需求.md`

```md
# 某某系统开发需求

#### *某某 2026-03-25*

## 1 基本功能需求

1. 登录与注册
2. 数据录入与校验
3. 报告导出与归档
```

## 示例输入 B：参考材料（DOCX）

文件：`supporting_inputs/参考材料.docx`（正文略）

## 示例输出（产物清单）

```text
SC_MyProject_4_SupportingMaterial.md
SC_MyProject_4_SupportingMaterial.pdf
```

## 示例输出片段（材料清单）

```md
## 0 材料清单

| 序号 | 文件名 | 类型 | 摘要 |
| :--: | --- | :--: | --- |
| 1 | 需求.md | md | 某某系统开发需求 … |
| 2 | 参考材料.docx | docx | （摘录若干段落）… |
```

## 示例调用（命令行）

```bash
python .trae/skills/SC4_SupportingMaterial/bundle/sc4_supporting_material.py ^
  --repo-root d:\MyProject ^
  --project-name MyProject ^
  --inputs d:\MyProject\supporting_inputs\需求.md ^
  --inputs d:\MyProject\supporting_inputs\参考材料.docx ^
  --title "某某系统开发需求" ^
  --author "某某" ^
  --date 2026-03-25
```
