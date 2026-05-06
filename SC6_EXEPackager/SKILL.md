---
name: "WindowsEXEPackager"
description: "将Python项目打包为Windows可执行文件（EXE），包含版本资源嵌入和代码签名。当用户需要将Python应用打包为Windows单文件EXE、解决安全中心误报或需要代码签名时调用。"
---

# Windows EXE 打包器

本技能提供完整的Python项目打包流程，将Python应用转换为Windows可执行文件（EXE），包含版本资源嵌入、代码签名和Windows安全中心兼容性优化。

## 功能特性

- ✅ **单文件打包**：使用PyInstaller创建独立的可执行文件
- ✅ **版本资源嵌入**：嵌入公司、版权、版本号等Windows资源信息
- ✅ **代码签名**：支持自签名和商业证书签名
- ✅ **安全中心兼容**：通过资源嵌入和签名减少Windows Defender误报
- ✅ **资源文件包含**：自动包含配置文件、图片、PDF等资源
- ✅ **可复用配置**：提供模板和配置文件，适应不同项目结构

## 前提条件

### 1. 环境要求
- Python 3.8+ 虚拟环境
- PyInstaller 5.0+
- Windows SDK（用于代码签名，可选）
- 项目依赖已安装（requirements.txt）

### 2. 项目结构
```
项目根目录/
├── main.py              # 主程序入口
├── src/                 # 源代码目录
├── assets/              # 资源文件（图标、图片、PDF等）
├── config.yaml          # 配置文件
├── requirements.txt     # 依赖列表
└── version_info.txt     # 版本资源文件（可选）
```

## 打包流程

### 步骤1：环境准备

```powershell
# 创建虚拟环境（如果不存在）
python -m venv .venv

# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 安装项目依赖
pip install -r requirements.txt

# 安装打包工具
pip install pyinstaller
```

### 步骤2：创建版本资源文件

创建 `version_info.txt` 文件：

```python
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [StringStruct(u'CompanyName', u'您的公司名称'),
           StringStruct(u'FileDescription', u'应用程序描述'),
           StringStruct(u'FileVersion', u'1.0.0.0'),
           StringStruct(u'InternalName', u'应用内部名称'),
           StringStruct(u'LegalCopyright', u'Copyright © 2026 版权所有'),
           StringStruct(u'OriginalFilename', u'应用名称.exe'),
           StringStruct(u'ProductName', u'产品名称'),
           StringStruct(u'ProductVersion', u'1.0.0.0')])
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [0x409, 1200])])
  ]
)
```

**注意**：字符串中的单引号需要转义（例如：`Xi\'an`）。

### 步骤3：创建PyInstaller配置文件

创建或生成 `TTCAS_PyInstaller.spec` 文件：

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.', 'src'],  # 添加src目录到模块搜索路径
    binaries=[],
    datas=[
        ('config.yaml', '.'),          # 配置文件
        ('assets', 'assets'),          # 资源目录
        ('*.pdf', 'assets'),           # PDF文件
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TTCAS',                     # 输出文件名
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                    # 控制台应用设为True
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\app.ico'],         # 应用图标
    version='version_info.txt',       # 版本资源文件
)
```

### 步骤4：运行打包命令

```powershell
# 清理之前的构建
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

# 执行打包
.\.venv\Scripts\pyinstaller.exe TTCAS_PyInstaller.spec --clean
```

### 步骤5：代码签名（可选但推荐）

#### 5.1 生成自签名证书

```powershell
# 创建自签名证书
New-SelfSignedCertificate -Type CodeSigning -Subject "CN=Your Company" -CertStoreLocation "Cert:\CurrentUser\My" -KeyExportPolicy Exportable -NotAfter (Get-Date).AddYears(1)

# 导出为PFX文件
$cert = Get-ChildItem -Path "Cert:\CurrentUser\My" | Where-Object {$_.Subject -eq "CN=Your Company"} | Select-Object -First 1
Export-PfxCertificate -Cert $cert -FilePath ".\app_cert.pfx" -Password (ConvertTo-SecureString -String "YourPassword123" -Force -AsPlainText)
```

#### 5.2 使用Windows SDK签名

```powershell
# 使用signtool签名（需要Windows SDK）
& "C:\Program Files (x86)\Windows Kits\10\bin\10.0.28000.0\x64\signtool.exe" sign /f "app_cert.pfx" /p YourPassword123 /fd SHA256 /t "http://timestamp.digicert.com" /v "dist\TTCAS.exe"
```

#### 5.3 验证签名

```powershell
& "C:\Program Files (x86)\Windows Kits\10\bin\10.0.28000.0\x64\signtool.exe" verify /v /pa "dist\TTCAS.exe"
```

### 步骤6：安装证书（减少误报）

```powershell
# 将证书安装到受信任的根证书存储
Import-PfxCertificate -FilePath ".\app_cert.pfx" -CertStoreLocation "Cert:\LocalMachine\Root" -Password (ConvertTo-SecureString -String "YourPassword123" -Force -AsPlainText)
```

## 故障排除

### 1. 模块找不到错误
**问题**：`ModuleNotFoundError: No module named 'xxx'`
**解决**：在spec文件的`pathex`中添加模块目录，或使用`hiddenimports`

### 2. 版本资源语法错误
**问题**：`SyntaxError: invalid syntax` in version_info.txt
**解决**：转义字符串中的单引号（`\'`），确保Python语法正确

### 3. Windows安全中心误报
**问题**：EXE文件被Windows Defender拦截
**解决**：
1. 确保完整的版本资源信息
2. 进行代码签名（即使自签名）
3. 安装证书到受信任的根证书存储
4. 考虑购买商业代码签名证书

### 4. 字体/主题切换问题
**问题**：UI控件样式更新不及时
**解决**：在代码中添加完整的控件刷新逻辑：

```python
# 应用字体到所有控件
font = QFont(app.font())
font.setPointSize(new_size)
app.setFont(font)

# 刷新所有控件
for w in QApplication.allWidgets():
    try:
        w.setFont(font)
        w.update()
    except Exception:
        continue

QApplication.processEvents()
```

## 可复用提示词

当需要打包新项目时，使用以下模板：

```
我需要将Python项目打包为Windows EXE文件：
1. 项目结构：main.py在根目录，src/为源代码，assets/为资源文件
2. 输出名称：[应用名称].exe
3. 图标路径：assets/app.ico
4. 版本信息：
   - 公司名称：[公司名]
   - 文件描述：[应用描述]
   - 版权信息：Copyright © [年份] [作者]
   - 版本号：[主版本].[次版本].[构建号].[修订号]
5. 需要代码签名：[是/否]
6. 特殊要求：[控制台应用/无控制台]
```

## 最佳实践

1. **版本控制**：每次发布更新版本号
2. **签名证书**：对于正式发布，使用商业代码签名证书
3. **测试环境**：在干净的Windows虚拟机中测试打包结果
4. **依赖管理**：使用requirements.txt精确控制依赖版本
5. **资源优化**：压缩图片等资源，减小EXE体积

## 相关文件

- `version_info.txt` - 版本资源模板
- `TTCAS_PyInstaller.spec` - PyInstaller配置模板
- `app_cert.pfx` - 自签名证书示例

---

**最后更新**：2026-04-20  
**基于项目**：TTCAS（基于TyG-WWI-ALB的2型糖尿病住院患者代谢分型与治疗反应预测系统）