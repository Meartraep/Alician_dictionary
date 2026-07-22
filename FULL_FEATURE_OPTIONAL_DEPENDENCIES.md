# Full 版运行时、模型与安装包

Full 版包含 text2vec、PyTorch、Transformers 和 NumPy 等程序运行库，但模型权重不再
打入 `AlicianDictionaryFull.exe`。程序更新与约 409 MB 的语义模型是两个独立组件。

## 面向用户的安装包

- `release\Full\AlicianDictionaryFullOnlineSetup.exe`
  - 包含完整程序运行库。
  - 首次安装时从 Hugging Face 的固定修订版本下载模型。
  - 每个下载文件都进行 SHA-256 校验。
- `release\Full\AlicianDictionaryFullOfflineSetup.exe`
  - 包含完整程序运行库和模型，安装过程不需要网络。
- 两种安装包都允许用户指定模型的实际存储文件夹。
- 升级安装会复用注册表中保存的模型位置。模型文件完整时，在线版不下载、离线版不复制模型。
- 卸载程序默认保留模型文件和用户数据，避免重新安装时丢失大文件或个人数据库。

默认模型目录为：

```text
%LOCALAPPDATA%\AlicianDictionary\Models\text2vec-base-chinese
```

用户可以在安装向导中改为任意有写入权限的位置。安装后也可以在程序的“设置”页选择
另一个已经包含完整模型的目录；重启程序后生效。

## 模型版本

```text
Model: shibing624/text2vec-base-chinese
Revision: 183bb99aa7af74355fb58d16edf8c13ae7c5433e
License: Apache-2.0
```

完整文件名、大小和 SHA-256 位于 `installer\model_manifest.json`，应用与构建脚本共同
使用同一组固定元数据。离线安装会把模型来源说明、清单和 Apache-2.0 许可证一起安装
到用户选择的模型目录。

## 开发与构建

所有当前发布产物只能写入以下固定目录：

- Full 程序本体：`release\Full\AlicianDictionaryFull.exe`
- Lite 程序本体：`release\Lite\AlicianDictionaryLite.exe`
- Full 在线安装包：`release\Full\AlicianDictionaryFullOnlineSetup.exe`
- Full 离线安装包：`release\Full\AlicianDictionaryFullOfflineSetup.exe`

安装 Inno Setup 6.5 或更新版本后运行：

```powershell
.\scripts\build_full_installers.ps1 -AppVersion 26.7.22
```

脚本会：

1. 使用各自独立的 `release_build\full` 与 `release_build\lite` 工作目录构建程序。
2. 从本地 Hugging Face 缓存定位固定修订模型，并逐文件校验大小和 SHA-256。
3. 生成在线与离线安装包。
4. 输出两个程序本体和两个安装包的修改时间、大小与 SHA-256。

如只修改安装脚本而不需要重新构建程序：

```powershell
.\scripts\build_full_installers.ps1 -AppVersion 26.7.22 -SkipProgramBuild
```

源码调试时仍可临时覆盖模型路径：

```powershell
$env:ALICIAN_TEXT2VEC_MODEL_PATH = "D:\models\text2vec-base-chinese"
```
