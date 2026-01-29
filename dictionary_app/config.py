import sys


import os


class Config:
    APP_TITLE = "爱丽丝语词典"
    INITIAL_SIZE = "1000x600"
    MIN_SIZE = "800x500"
    # 使用相对于当前文件的绝对路径，确保无论从哪里运行都能找到数据库文件
    DB_NAME = os.path.abspath(os.path.join(os.path.dirname(__file__), "../translated.db"))  # 数据库文件名，相对于当前文件
    REQUIRED_TABLES = {"dictionary": ["words", "explanation", "class"], "songs": ["title", "lyric", "Album"], "phrase": ["PHRASE", "explanation"]}
    
    if sys.platform == 'win32':
        FONT_FAMILY = "SimHei"
        DEFAULT_FONT_SIZE = 10
        ENTRY_FONT_SIZE = 12
    elif sys.platform == 'darwin':
        FONT_FAMILY = "PingFang SC"
        DEFAULT_FONT_SIZE = 11
        ENTRY_FONT_SIZE = 13
    else:
        FONT_FAMILY = "WenQuanYi Zen Hei"
        DEFAULT_FONT_SIZE = 10
        ENTRY_FONT_SIZE = 12
    
    LABEL_FONT_SIZE = 9
    EXAMPLE_MIN_HEIGHT = 4
    SOURCES_BOX_HEIGHT = 9
    HIGHLIGHT_COLOR = "#FFD700"
    CURRENT_HIGHLIGHT_COLOR = "#FFFFCC"
    INFO_COLOR = "#666666"
    CURRENT_DB = DB_NAME
