# SC2_OriginalCode 示例（脱敏）

本文件用于展示“软著源码材料”Skill 的典型输入/输出形态，便于在其他项目中照抄用法与验收要点。

## 示例输入（目录结构）

```text
MyProject/
  app_config.yaml
  main.py
  src/
    my_app/
      __init__.py
      app.py
```

## 示例输出（产物清单）

```text
SC_MyProject_2_OriginalCode.md
SC_MyProject_2_OriginalCode_wrapped.md
SC_MyProject_2_OriginalCode.tex
SC_MyProject_2_OriginalCode.pdf
```

## 示例片段：SC_MyProject_2_OriginalCode.md

```md
<span style="color:red">main.py</span>
print("hello")

<span style="color:red">src/my_app/app.py</span>
def run():
    return 0
```

## 示例片段：SC_MyProject_2_OriginalCode.tex（页眉/页脚与行号样式）

```tex
\pagestyle{fancy}
\fancyhead[C]{某某系统 V1.0}
\fancyfoot[C]{第\thepage 页/共 \pageref{LastPage} 页}

\newcommand{\SCLine}[2]{%
  \noindent\llap{\makebox[1.6cm][r]{\fontsize{8}{8}\selectfont #1}\hspace{0.3cm}}%
  {\fontsize{8}{9}\selectfont #2}\par
}
```
