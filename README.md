> All code was wrote by AI coder 
> All programs are powered by Python 3.17 or later.
# Helper
Helper is a tool kit which can help you learn and write Alician.
It has a graphical interface, and no external libraries required.
It use SQLite3
## alice_dictionary.py
核心功能模块之一。
可查询单词的中文释义，或根据中文释义查找对应词汇。
可选择模糊搜索或精确搜索模式。
每句下方会一一列出句中词汇及其中文翻译。
可查询到某个单词出自哪首歌曲、歌词的哪一句。
程序会对包含搜索词的句子进行查重。
若包含该搜索词的相同句子出现在同一首歌曲中，会判定为重复。
若多首歌曲包含相同句子，则全部记录在案。
程序会采用两种不同颜色，分别高亮显示包含搜索词的句子和搜索语句本身。
One of the main program. 
You can look up the Chinese definition of a word or find the corresponding word based on its Chinese definition.
You can choose between fuzzy search or exact search.
Under each sentence, the words in the sentence and their Chinese translations are listed one-to-one.
You can find out which song and which line of lyrics a word comes from.
The program performs plagiarism checks on sentences containing the search term.
If the same sentence containing the searched word appears in the same song, it will be checked for duplicates. 
If multiple songs contain the same sentence, all of them will be recorded.
The program highlights sentences containing the search words and the search sentences itself using two different colors.
## translated.db
SQLite3
本项目所有程序的数据来源。
所有内容均来自互联网，并已获得其创作者的授权。
我也参与了数据库的创建。
Data source for all programs in the project.
All content is sourced from the internet and has been authorized by its creators.
I also participated in the creation of the database.




