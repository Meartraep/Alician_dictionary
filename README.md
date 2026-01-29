> All code was wrote by AI coder and All programs are powered by Python 3.13 or later.
# Alician_dictionary
Helper is a tool kit which can help you learn and write Alician.
It has a graphical interface, and no external libraries required.
## alice_dictionary.py
核心功能模块之一。它的功能如下：
1.可查询单词的中文释义，或根据中文释义查找对应词汇。
2.可选择模糊搜索或精确搜索模式。
3.每句下方会一一列出句中词汇及其中文翻译。
4.可查询到某个单词出自哪首歌曲、歌词的哪一句。
5.程序会对包含搜索词的句子进行查重。
6.若包含该搜索词的相同句子出现在同一首歌曲中，会判定为重复。
7.若多首歌曲包含相同句子，则全部记录在案。
8.程序会采用两种不同颜色，分别高亮显示包含搜索词的句子和搜索语句本身。
One of the main program. Its functions are as follows:
1.You can look up the Chinese definition of a word or find the corresponding word based on its Chinese definition.
2.You can choose between fuzzy search or exact search.
3.Under each sentence, the words in the sentence and their Chinese translations are listed one-to-one.
4.You can find out which song and which line of lyrics a word comes from.
5.The program performs plagiarism checks on sentences containing the search term.
6.If the same sentence containing the searched word appears in the same song, it will be checked for duplicates. 
7.If multiple songs contain the same sentence, all of them will be recorded.
8.The program highlights sentences containing the search words and the search sentences itself using two different colors.
## translated.db
SQLite3
本项目所有程序的数据来源。
所有内容均来自互联网，并已获得其创作者的授权。
我也参与了数据库的创建。
Data source for all programs in the project.
All content is sourced from the internet and has been authorized by its creators.
I also participated in the creation of the database.
## update_word_count.py
项目中的支持组件。
该程序用于查询和更新词频及覆盖范围统计，并自动保存至数据库。每当数据库中的词汇发生更新时，需运行该程序，以获取该词汇的词频及覆盖范围。
Supporting components in the project.
This program is used to query and update word frequency and breadth statistics and automatically save them to a database. It should be run whenever the words in the database are updated to obtain the word frequency and breadth of that word.
> 广泛度（覆盖范围）的含义就是这个单词于多少首歌中出现。
> The breadth of a word refers to how many songs it appears in.
> 当一个单词的词频和泛度中的任意一个小于3时它会被施加蓝色高亮。
> 目前使用的词频是去重前的词频。
## word_checker.py
项目的另一核心组件是编辑器，它具备以下功能：
1.可实时检测输入单词是否正确。
2.拼写错误的单词用红色标注，低频词或生僻词用蓝色标注。
3.程序设有侧边栏，实时显示输入错误。
4.在屏幕上拖动选择单词，右键点击即可查看其中文释义。
5.点击侧边栏中的单词，会在新窗口显示该单词的相关问题；双击该单词，可跳转至其在文本中的首次出现位置；点击新窗口外部即可关闭该窗口。
6.可选择是否严格匹配单词大小写。
7.支持从电脑任意位置打开.txt 文件，将其内容加载到程序中；也可将程序中的文本保存为.txt 文件，存储至电脑任意位置。
8.设置信息永久存储在 JSON 文件中。
Another main component of the project is an editor. It provides the following features:
1.It can detect whether the input words are correct in real time.
2.It can highlight typos and low-frequency or low-breadth words in red and blue respectively.
3.The program has a sidebar that displays input errors in real time.
4.Drag on the screen to select words, then right-click to view their Chinese definitions.
5.Click on a word in the sidebar to display its question in a new window, double-click it to jump to the first occurrence of that word in the text, and click outside the new window to close it.
6.You can choose whether to strictly match word case.
7.You can open a .txt file from anywhere on your computer to load its contents into the program, or save the text from the program as a .txt file to anywhere on your computer.
8.Settings are permanently stored in a JSON file.
## word_checker_config.json
用来存储word_checker.py的设置项的JSON文件
JSON file used to store settings of word_checker.py






