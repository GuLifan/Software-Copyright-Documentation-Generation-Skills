# SC5_Application 示例（脱敏）

本文件用于展示“软著申请表 Markdown 填充”Skill 的输入与输出形态。

## 示例输入：申请表模板（节选）

文件：`application_inputs/软著MyProject-5申请.md`

```md
<font color="red">软件全称</font>：`（待填写）`

<font color="red">版本号</font>：`（待填写）`

<font color="red">开发完成日期（最后修改README.md文件的日期）</font>：`（待填写）`

<font color="red">软件的主要功能【限500~1300字】</font>：

    （待填写）
```

## 示例事实来源

- `app_config.yaml`：提供 `application_display_name` 与 `app_version`
- `README.md`：提供“功能概览”与项目描述，用于自动整理“软件的主要功能”
- `SC_{项目名}_2_OriginalCode.tex`（如存在）：用于推断“源程序量”

## 示例输出：SC_{项目名}_5_Application.md（节选）

```md
<font color="red">软件全称</font>：`某某系统`

<font color="red">版本号</font>：`V1.0`

<font color="red">开发完成日期（最后修改README.md文件的日期）</font>：`2026年04月07日`

<font color="red">软件的主要功能【限500~1300字】</font>：

    本软件面向…（自动生成，需人工复核字数与用词）…
```

## 示例调用（命令行）

```bash
python .trae/skills/SC5_Application/bundle/sc5_application.py ^
  --repo-root d:\MyProject ^
  --project-name MyProject ^
  --template-md d:\MyProject\application_inputs\软著MyProject-5申请.md ^
  --app-config d:\MyProject\app_config.yaml ^
  --readme d:\MyProject\README.md
```
