---
name: "FG1_Figure"
description: "Generates scientific figure plotting code based on existing R/Python patterns in the project. Invoke when user says '绘制论文插图' or requests to create figure plotting code with configurable parameters."
---

# FG1_Figure 科研论文插图生成技能

此技能帮助用户基于当前项目中已有的 R 或 Python 绘图代码，生成新的科研论文插图绘制代码。生成的代码将图片尺寸、DPI、颜色、图片格式、字体字号等参数集中放置在代码醒目的位置，便于快速修改，并可在不同项目间复用。

## 技能目标

- 分析当前项目中的绘图代码模式（Python/matplotlib 或 R/ggplot2）
- 提取常见的可配置参数（字体、DPI、尺寸、颜色方案等）
- 根据用户需求生成新的绘图代码模板
- 确保生成的代码符合科研论文插图的可重复性与可调性要求

## 使用场景

当用户说以下内容时，立即调用本技能：
- “绘制论文插图”
- “生成科研图代码”
- “帮我写一个画图脚本”
- “根据现有代码生成新的绘图脚本”

## 技能执行步骤

### 1. 扫描项目中的绘图代码
- 搜索当前目录及子目录中的 `.py` 和 `.R` 文件
- 识别包含绘图函数（如 `plt.plot`、`ggplot`、`ggsave`）的文件
- 分析这些文件的开头部分，提取硬编码的参数配置模式

### 2. 提取参数模式
从现有代码中提取以下常见参数（如果存在）：
- **字体设置**：`FONT_SIZE`、`FONT_NAME`、`FONT_FAMILY`
- **图像尺寸**：`IMAGE_SIZE`（宽,高）、`figsize`、`width`/`height`
- **分辨率**：`IMAGE_DPI`、`dpi`、`DPI`
- **颜色方案**：`COLOR_*` 变量（RGB元组或十六进制）
- **输出格式**：`OUTPUT_IMAGE_PATH`、文件扩展名（`.png`、`.jpg`、`.pdf`）
- **其他业务参数**：如 `CLUSTER_GROUP`、`TARGET_LOW` 等

### 3. 询问用户偏好
通过 `AskUserQuestion` 工具询问用户以下问题（每次调用时选择最相关的2-3个）：
- **图表类型**：散点图、线图、柱状图、雷达图、AGP图谱、RCS曲线等
- **编程语言**：Python (matplotlib) 或 R (ggplot2)
- **输出格式**：PNG、JPG、PDF、TIFF（默认JPG）
- **DPI要求**：300、600、1200（默认600）
- **是否包含图例/标题/坐标轴标签**：是/否

### 4. 生成代码模板
基于分析结果和用户选择，创建一个新的绘图脚本文件（如 `new_figure.py` 或 `new_figure.R`）。代码结构如下：

#### Python (matplotlib) 模板示例
```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==================== 可配置参数（集中在此，方便修改）====================
FONT_SIZE = 16                     # 字体大小
FONT_NAME = 'Times New Roman'      # 字体名称
IMAGE_DPI = 600                    # 输出图片DPI
IMAGE_SIZE = (10, 6)               # 图像尺寸（宽,高），单位英寸
OUTPUT_PATH = 'output_figure.jpg'  # 输出文件路径

# 颜色方案（RGB元组，0-255范围）
COLOR_MAIN = (46, 159, 223)        # 主色
COLOR_SECONDARY = (255, 177, 153)  # 辅助色
COLOR_BACKGROUND = (240, 240, 240) # 背景色

# 数据相关参数（根据实际数据调整）
DATA_FILE = 'your_data.csv'        # 数据文件路径
X_COLUMN = 'x_column'              # X轴数据列名
Y_COLUMN = 'y_column'              # Y轴数据列名
GROUP_COLUMN = 'group'             # 分组列名（可选）

# ==================== 核心绘图函数 =====================
def load_data():
    """加载数据（根据实际情况修改）"""
    df = pd.read_csv(DATA_FILE)
    return df

def create_figure():
    """创建图表（根据图表类型修改）"""
    # 设置全局字体
    plt.rcParams['font.family'] = FONT_NAME
    plt.rcParams['font.size'] = FONT_SIZE
    
    # 创建图形
    fig, ax = plt.subplots(figsize=IMAGE_SIZE, dpi=IMAGE_DPI)
    
    # 示例：绘制散点图（根据实际需求修改）
    df = load_data()
    ax.scatter(df[X_COLUMN], df[Y_COLUMN], 
               color=np.array(COLOR_MAIN)/255, alpha=0.7, s=50)
    
    # 图表美化
    ax.set_xlabel(X_COLUMN, fontsize=FONT_SIZE, fontweight='bold')
    ax.set_ylabel(Y_COLUMN, fontsize=FONT_SIZE, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # 保存图像
    plt.tight_layout()
    plt.savefig(OUTPUT_PATH, dpi=IMAGE_DPI, bbox_inches='tight')
    plt.close()
    print(f"图表已保存至：{OUTPUT_PATH} (DPI={IMAGE_DPI})")

# ==================== 主程序 =====================
if __name__ == "__main__":
    create_figure()
```

#### R (ggplot2) 模板示例
```r
# ==================== 可配置参数（集中在此，方便修改）====================
FONT_SIZE <- 16                    # 字体大小
FONT_FAMILY <- "Times New Roman"   # 字体族
IMAGE_DPI <- 600                   # 输出图片DPI
IMAGE_WIDTH <- 10                  # 图像宽度（英寸）
IMAGE_HEIGHT <- 6                  # 图像高度（英寸）
OUTPUT_PATH <- "output_figure.jpg" # 输出文件路径

# 颜色方案（十六进制）
COLOR_MAIN <- "#2E9FDF"            # 主色
COLOR_SECONDARY <- "#FFB199"       # 辅助色

# 数据相关参数
DATA_FILE <- "your_data.csv"       # 数据文件路径
X_COLUMN <- "x_column"             # X轴数据列名
Y_COLUMN <- "y_column"             # Y轴数据列名

# ==================== 加载包 =====================
library(ggplot2)
library(readr)

# ==================== 核心绘图函数 =====================
create_figure <- function() {
  # 加载数据
  df <- read_csv(DATA_FILE)
  
  # 创建图形
  p <- ggplot(df, aes(x = .data[[X_COLUMN]], y = .data[[Y_COLUMN]])) +
    geom_point(color = COLOR_MAIN, alpha = 0.7, size = 2) +
    theme_bw(base_size = FONT_SIZE, base_family = FONT_FAMILY) +
    theme(
      panel.grid.minor = element_blank(),
      axis.title = element_text(face = "bold")
    ) +
    labs(x = X_COLUMN, y = Y_COLUMN)
  
  # 保存图像
  ggsave(OUTPUT_PATH, p, 
         width = IMAGE_WIDTH, height = IMAGE_HEIGHT, 
         dpi = IMAGE_DPI, device = "jpeg")
  
  message(paste("图表已保存至：", OUTPUT_PATH, "(DPI=", IMAGE_DPI, ")"))
}

# ==================== 执行绘图 =====================
create_figure()
```

### 5. 适配现有项目风格
- 如果项目中已存在绘图代码，尽量采用相同的参数命名风格
- 颜色方案可沿用现有调色板（如 `PALETTE = ["#2E9FDF", "#00AFBB", "#E7B800", "#FC4E07"]`）
- 字体设置应与已有代码保持一致（如 Helvetica、Times New Roman 等）
- 输出文件命名可遵循项目惯例（如 `{描述}_{DPI}dpi.{格式}`）

### 6. 提供修改指导
在生成代码后，提醒用户：
- 修改 `可配置参数` 区域以适应具体需求
- 根据实际数据结构调整数据加载部分
- 替换绘图函数以匹配所需的图表类型
- 运行脚本前确保已安装必要依赖包

## 注意事项

1. **参数醒目**：所有可配置参数必须集中在代码开头，并使用醒目的注释分隔
2. **硬编码优先**：科研代码通常使用硬编码参数以保证可重复性，避免从配置文件读取
3. **DPI设置**：学术期刊通常要求300-1200 DPI，根据目标期刊要求调整
4. **字体嵌入**：如果使用特定字体（如 Helvetica），确保系统中已安装或提供备用方案
5. **颜色无障碍**：考虑色盲友好配色，可使用 ColorBrewer 或 viridis 色系

## 示例调用

用户说：“绘制论文插图”
- 技能被触发
- 扫描当前项目，发现多个AGP图谱Python代码
- 询问用户：“需要生成什么类型的图表？[AGP图谱/散点图/雷达图/RCS曲线]”
- 用户选择“散点图”
- 生成基于现有AGP代码风格的散点图模板，参数区醒目突出

通过本技能，用户可以快速生成符合项目风格的科研插图代码，提高工作效率并保持图表一致性。