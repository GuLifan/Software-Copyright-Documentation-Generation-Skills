# Software Copyright Documentation Generation Skills

本目录包含一组用于“软件著作权申请材料”自动化生成的 Skills。每个 Skill 都以可迁移结构组织：`SKILL.md`（说明）+ `bundle/*.py`（可复制脚本）。

本项目借助Trae 3.5.47 开发，使用了AI大模型。旨在于根据项目文件自动化生成“软件著作权申请材料”，包括合作开发协议、软著源码材料、软著用户手册、软著佐证材料、软著申请表。

*注意：这不代表你可以不开发软件而任由AI凭空生成文件套取软著证书，对本工具套件的不当使用带来的全部后果由使用者本人承担，开发者不承担任何连带责任！*

> 目前，SC1_CooperationAgreement 只是占位，起到一个提醒的作用，在实际应用中，合作协议应当根据开发者和项目的具体情况拟写。换言之，我建议你上网搜一个模板，比用 AI 生成之后修改方便。

> 部分 skill 的运行需要在本地配置好Tex Live 环境，包括安装 Tex Live 包、配置环境变量等。

联系开发者：[lifanguxjtu@outlook.com](mailto:lifanguxjtu@outlook.com)

## Skills
- SC1_CooperationAgreement：占位（合作开发协议）
- SC2_OriginalCode：软著源码材料（60页/3000行规则相关）
- SC3_UserManual：软著用户手册（批量截图→TeX→PDF）
- SC4_SupportingMaterial：软著佐证材料（docx/md 等→整理→PDF）
- SC5_Application：软著申请表（读取模板→填写红色条目→输出 Markdown）

## Examples

记载了若干成品的示范文档，帮助你理解每个 Skill 的典型输入与生成产物形态，实在不行，你可以自己对照着动手改。

- SC2_OriginalCode_example.md
- SC3_UserManual_example.md
- SC4_SupportingMaterial_example.md
- SC5_Application_example.md

## 通用约定

- 优先使用“可迁移脚本”：各 Skill 的 `bundle/` 下脚本可复制到任意项目直接运行。
- 路径：脚本参数普遍支持相对路径（相对 `--repo-root`）与绝对路径。
- 字体与中文：涉及 PDF/TeX 的脚本默认使用 XeLaTeX（Times New Roman + 宋体/微软雅黑回退）。

## License

本目录下全部 Skill 与脚本以 GNU GPL v3 发布，见 [LICENSE](LICENSE)。

