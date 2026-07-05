# 完整功能可选外部库

当前 `Alician_Dictionary.exe` 为了控制体积，不会内置 `text2vec`、`torch`、`transformers`、`numpy` 等重型库。基础查词、上下文、数据库管理、写作检查仍随 exe 可用；安装下面的可选依赖后，缺词时的 text2vec 语义相似词推荐会启用。

## 推荐安装方式

建议使用和打包环境一致的 Python 3.11。先安装 CPU 版 PyTorch，再安装 text2vec：

```powershell
py -3.11 -m pip install -U pip
py -3.11 -m pip install -U torch --index-url https://download.pytorch.org/whl/cpu
py -3.11 -m pip install -U text2vec
```

如果你希望把依赖放在 exe 同目录，不污染系统 Python，可以在 `Alician_Dictionary.exe` 同目录创建 `external_libs` 文件夹，然后安装到那里：

```powershell
py -3.11 -m pip install -U torch --index-url https://download.pytorch.org/whl/cpu --target .\external_libs
py -3.11 -m pip install -U text2vec --target .\external_libs
```

也可以把依赖放到任意目录，并在启动 exe 前设置环境变量：

```powershell
$env:ALICIAN_EXTERNAL_LIB_PATH = "D:\AlicianDeps"
.\Alician_Dictionary.exe
```

## 模型缓存

程序默认使用 `shibing624/text2vec-base-chinese`，并默认离线加载，避免 exe 运行时突然联网下载模型。首次使用完整相似词功能前，请先联网缓存模型：

```powershell
py -3.11 -c "from text2vec import SentenceModel; SentenceModel('shibing624/text2vec-base-chinese')"
```

如果你确实希望运行时允许 Hugging Face 在线下载，可以在启动前设置：

```powershell
$env:HF_HUB_OFFLINE = "0"
.\Alician_Dictionary.exe
```

## 实际需要的主要库

- `text2vec`
- `torch`
- `transformers`
- `numpy`
- `sentence-transformers`
- `huggingface-hub`
- `tokenizers`
- `safetensors`
- `tqdm`
- `scipy`
- `scikit-learn`

通常不需要逐个安装这些库，`pip install text2vec` 会自动安装大多数依赖；单独列出是为了方便排查环境问题。
