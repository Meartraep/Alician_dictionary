# -*- mode: python ; coding: utf-8 -*-
from huggingface_hub import snapshot_download
from PyInstaller.utils.hooks import collect_submodules


TEXT2VEC_MODEL_NAME = 'shibing624/text2vec-base-chinese'
try:
    text2vec_model_dir = snapshot_download(TEXT2VEC_MODEL_NAME, local_files_only=True)
except Exception as exc:
    raise RuntimeError(
        f'Full build requires a complete local cache of {TEXT2VEC_MODEL_NAME}. '
        'Load/download the model once before running PyInstaller.'
    ) from exc

hiddenimports = [
    'db_update_dialog',
    'db_exporter',
    'classify_words',
    'update_word_count',
    'scripts.migrate_dictionary_senses',
    'webui_backend.translation_service',
    'webui_backend.similarity_matcher',
    'webview.platforms.edgechromium',
    'webview.platforms.winforms',
]
hiddenimports += collect_submodules('webview')
hiddenimports += collect_submodules('text2vec')
hiddenimports += collect_submodules('transformers.models.bert')


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
        (text2vec_model_dir, 'text2vec_model'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='AlicianDictionaryFull',
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
