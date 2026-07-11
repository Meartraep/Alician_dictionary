# Full 版本的 text2vec 运行时

`AlicianDictionaryFull.exe` 已内置 text2vec、PyTorch、Transformers、NumPy 及
`shibing624/text2vec-base-chinese` 模型。目标设备不需要安装 Python、第三方库，
也不需要预先下载 Hugging Face 模型。

Lite 版本不包含这些组件，也不会启用语义相似词功能。

## 开发与打包

Full 版本打包时，构建机必须已经完整缓存模型。`AlicianDictionary.spec` 会在
构建开始时检查本地缓存，缺失时直接报错，避免生成一个表面成功但无法使用
text2vec 的 Full EXE。

如需在源码调试时覆盖默认模型位置，可设置：

```powershell
$env:ALICIAN_TEXT2VEC_MODEL_PATH = "D:\models\text2vec-base-chinese"
```
