# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

added_files = [
    ('translated.db', '.'),
    ('word_checker_config.json', '.')
]

a = Analysis(['Dictionary_database_manager_main/run_app.py'],
             pathex=['C:/Users/25307/Desktop/Alician_dictionary-26_2_18', 'C:/Users/25307/Desktop/Alician_dictionary-26_2_18/Dictionary_database_manager_main'],
             binaries=[],
             datas=added_files,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='database_manager_new',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,  # 无控制台窗口
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None)
