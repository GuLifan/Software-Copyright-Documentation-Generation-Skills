# SC3_UserManual 示例（脱敏）

本文件用于展示“软著用户手册”Skill 的典型输入与生成产物形态。

## 示例输入（截图命名规则）

截图目录建议形如：

```text
manual/
  1-1前言.png
  2-1登录页面.png
  2-2尝试登录.png
  3-1主页面.png
  8-1软件信息声明.png
```

文件名含义：

- 第 1 个数字：章节号（将对应文档中的 section）
- 第 2 个数字：章节内顺序（用于排序）
- 后续文本：图名（用于 caption 与图下扩展说明的输入）

## 示例输出（产物清单）

```text
SC_MyProject_4_UserManual.tex
SC_MyProject_4_UserManual.pdf
```

## 示例调用（命令行）

```bash
python .trae/skills/SC3_UserManual/bundle/sc3_user_manual.py ^
  --repo-root d:\MyProject ^
  --manual-dir d:\MyProject\manual ^
  --app-config d:\MyProject\app_config.yaml ^
  --project-name MyProject ^
  --publish-date-cn 2026年04月12日 ^
  --engine xelatex
```

## 示例片段（TeX 图片块）

```tex
\begin{figure}[H]
\centering
\includegraphics[width=0.67\textwidth]{manual/3-1主页面.png}
\caption{主页面}
\end{figure}
```
