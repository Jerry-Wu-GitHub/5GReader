# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 收集必要的资源文件
datas = []
datas += collect_data_files('tiktoken')  # tiktoken 编码文件
datas += collect_data_files('easyocr')   # easyocr 模型配置
datas += [('config', 'config')]
datas += [('plugins', 'plugins')]

# 收集隐藏模块
hiddenimports = []
hiddenimports += collect_submodules('torch')
hiddenimports += collect_submodules('torchvision')  # easyocr 依赖
hiddenimports += collect_submodules('tiktoken')
hiddenimports += collect_submodules('openai')
hiddenimports += collect_submodules('PIL')  # pillow
hiddenimports += ['pyperclip']
hiddenimports += ['tkinter.scrolledtext', 'tkinter.filedialog', 'tkinter.messagebox']
hiddenimports += ['pymupdf', 'fitz']

# 排除 CUDA 相关模块以减小体积（如只用 CPU）
excludes = [
    'torch.cuda',
    'torch.cuda.*',
    'nvidia',
    'nvidia.*',
    'cupy',
    'cupy.*',
    'plugins',  # 排除整个 plugins 包
    'plugins.*',
    'config',  # 排除整个 config 包
    'config.*',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],  # 如果需要自定义 hooks，改为 ['./hooks']
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='5GReader',  # 修改为你的应用名称
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'ucrtbase.dll'],  # 避免压缩关键系统库
    runtime_tmpdir=None,
    console=False,  # 设为 True 可看到调试信息
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[r'static\icon\GR.ico'],  # 添加图标
)