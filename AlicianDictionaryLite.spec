# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = [
    'db_update_dialog',
    'db_exporter',
    'classify_words',
    'update_word_count',
    'scripts.migrate_dictionary_senses',
    'Levenshtein',
    'Levenshtein.levenshtein_cpp',
    'webview.platforms.edgechromium',
    'webview.platforms.winforms',
]
hiddenimports += collect_submodules('webview')
hiddenimports += collect_submodules('Levenshtein')

excluded_optional_modules = [
    'webui_backend.translation_service',
    'webui_backend.similarity_matcher',
    'text2vec',
    'torch',
    'transformers',
    'sentence_transformers',
    'datasets',
    'numpy',
    'pandas',
    'pyarrow',
    'scipy',
    'sklearn',
    'jieba',
]

a = Analysis(
    ['toolkit.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('webui', 'webui'),
        ('translated.db', '.'),
        ('word_checker_config.json', '.'),
        ('AlicianRegular.ttf', '.'),
        ('alice_app.ico', '.'),
        ('alice.ico', '.'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_optional_modules,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AlicianDictionaryLite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='alice_app.ico',
)
