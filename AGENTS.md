# Project instructions

## Packaging output policy

All newly built release executables must be written to these two canonical directories:

- Full: `C:\Users\meart\Desktop\Alician_dictionary-26_2_18\release\Full`
- Lite: `C:\Users\meart\Desktop\Alician_dictionary-26_2_18\release\Lite`

The expected deliverables are:

- `release\Full\AlicianDictionaryFull.exe`
- `release\Lite\AlicianDictionaryLite.exe`

Use separate build work directories so Full and Lite artifacts cannot be mixed:

```powershell
python -m PyInstaller --noconfirm --clean --workpath release_build\full --distpath release\Full AlicianDictionary.spec
python -m PyInstaller --noconfirm --clean --workpath release_build\lite --distpath release\Lite AlicianDictionaryLite.spec
```

Do not treat `dist`, `packages`, or their existing executables as current release artifacts. They may contain historical builds. Do not copy new releases into those directories unless the user explicitly requests it.

Before reporting a package as complete, verify the modification time, file size, and SHA-256 of both canonical executables. For Full, also verify that the archive contains the current Web UI, `webui_backend.translation_service`, `scripts.migrate_dictionary_senses`, `translated.db`, and the `text2vec_model` resources.
