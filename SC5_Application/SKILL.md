---
name: "SC5_Application"
description: "生成软著申请表 Markdown（读取模板→根据 YAML/README/源码信息填写红色条目）。当用户提到“生成软著申请表/填写申请表/更新申请.md”时调用。"
---

# SC5 软著申请表生成（Markdown 表格填充）

当用户要求“生成软著申请表 / 更新申请表 Markdown”时，执行以下流程：

1) 读取用户提供的申请表模板（常见为 `软著XXX-5申请.md`）
2) 读取项目事实来源（优先 `app_config.yaml` 与 `README.md`，必要时读取代码与既有软著源码产物）
3) 仅修改每个条目冒号 `：` 之后的内容（通常是红色条目），保持条目名称与结构不变
4) 输出 `SC_{项目名}_5_Application.md`

说明：该 Skill 不生成 PDF，只交付 Markdown 结果。

## 可迁移结构（推荐）

把整个目录 `.trae/skills/SC5_Application/` 视为可复制的独立工具包：

- `SKILL.md`：使用说明与交付规范
- `bundle/sc5_application.py`：可直接复制到任意项目使用的生成脚本（尽量仅依赖标准库）

## 输入与来源

- `--template-md`：申请表模板 Markdown
- `--app-config`：项目 YAML 配置（默认 `app_config.yaml`）
- `--readme`：项目说明（默认 `README.md`）
- `--project-name`：产物命名用项目名（默认 `Project`）

脚本会优先填写：

- 软件全称 / 版本号：来自 `app_config.yaml`
- 开发完成日期：优先取 `README.md` 文件修改时间（可参数覆盖）
- 源程序量：若存在 `SC_{项目名}_2_OriginalCode.tex`，则从其行号中推断最大行号；否则保留模板原值
- “软件主要功能”（500~1300字）：根据 README 的功能概览自动整理，并做长度约束

## 产物

- `SC_{项目名}_5_Application.md`

## 示例（脱敏）

```bash
python .trae/skills/SC5_Application/bundle/sc5_application.py ^
  --repo-root d:\MyProject ^
  --project-name MyProject ^
  --template-md d:\MyProject\软著MyProject-5申请.md ^
  --app-config d:\MyProject\app_config.yaml ^
  --readme d:\MyProject\README.md
```

## 交付规范

- 生成后需要人工快速校对红色条目字数限制（括号中的“限XX字/限500~1300字”）。
