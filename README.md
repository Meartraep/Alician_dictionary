# 项目名称：Alician_dictionary
这是一个帮助你进行爱丽丝语学习的工具包。<br>
本项目自2025年5月10日起遵循CC-BY-NC-SA 4.0协议开源<br>
感谢@mdt_witch大佬研究出的数据库，没有它我无法做出这个。
# 依赖
- 推荐3.11版本Python
- 用户需要使用代码安装以下外部库
```
pip install pywebview requests openpyxl python-Levenshtein
```
其中，`python-Levenshtein`用于 Full 和 Lite 的爱丽丝语拼写纠错查询；`openpyxl`仍为可选依赖。
# 运行源代码
## 将代码拉取到本地
```
git clone https://github.com/Meartraep/Alician_dictionary.git
```
编不下去了，不用那么麻烦的bro，直接把我main分支下载下来就好了
## 运行
要运行程序，请双击打开`toolkit.py`。首次打开会显示欢迎窗口，随后向注册表`HKEY_CURRENT_USER\Software\Meartraep\AlicianDictionary`中写入值`FirstLaunchCompleted=1`,手动删除该值再运行会再次显示欢迎窗口。<br>
~~欢迎窗口源于一开始我准备做一个功能，让大家拿到程序首次运行成功就邮件通知我，后来因为安全性无法保证（无法解决恶意刷邮件问题），删除了这个功能，只留下这个欢迎入口~~ 以后窗口上会显示协议

# Full 版安装

Full 版提供两种安装程序：在线安装包首次安装时下载语义模型，离线安装包直接携带模型。
两者都允许把模型存放到用户指定的任意有写入权限的位置。模型与程序本体分开保存，
后续覆盖升级只更新程序；只要现有模型校验完整，就不会再次下载或复制约 409 MB 的权重。

程序安装后仍可在“设置”页改为另一个已经包含完整模型的目录，重启后生效。详细的构建、
模型版本和校验说明见 `FULL_FEATURE_OPTIONAL_DEPENDENCIES.md`。
# 功能
查找爱丽丝语单词、查找关于该单词所在的原歌词上下文<br>
提供输入框，输入爱丽丝语词句，自动发现单词错误并提供建议、发现使用的低频词汇<br>
提供爱丽丝语单词词频、泛度统计功能。词频统计是去重的。<br>
**泛度**指代一个单词在多少首歌曲中出现
# 协议
Attribution-NonCommercial-ShareAlike 4.0 International
# 项目icon
使用豆包AI基于Alice Schach and the Magic Orchestra官方的爱丽丝·夏赫形象绘制，这张图片限于非商业使用
<img width="512" height="512" alt="app_icon" src="https://github.com/user-attachments/assets/fa213729-3adf-4656-b091-6a27da952547" />
# 链接
[Alice Schach and the Magic Orchestra](https://alice-orchestra.com)<br>
[hackto(character-designer)](http://villains-hackto.com/)
