from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Optional


MODEL_NAME = "shibing624/text2vec-base-chinese"
MODEL_REVISION = "183bb99aa7af74355fb58d16edf8c13ae7c5433e"
MODEL_ENVIRONMENT_VARIABLE = "ALICIAN_TEXT2VEC_MODEL_PATH"
MODEL_REGISTRY_KEY = r"Software\Meartraep\AlicianDictionary"
MODEL_REGISTRY_VALUE = "ModelPath"

MODEL_FILES: Dict[str, Dict[str, Any]] = {
    "config.json": {
        "size": 856,
        "sha256": "fdf4d96b74a9e2dc8ae752d74bcfbbf8b3a754b3d97412477f8768ef65a7db36",
    },
    "model.safetensors": {
        "size": 409098104,
        "sha256": "0c855515479137398ce4ea985628548d4e8ed8c5764656dac966d6a24f39e721",
    },
    "special_tokens_map.json": {
        "size": 112,
        "sha256": "303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3",
    },
    "tokenizer_config.json": {
        "size": 319,
        "sha256": "3da14b28cdfd6bcb24aef5e16a37c868bc6e8428b4180833d5e0ef9cc19931df",
    },
    "vocab.txt": {
        "size": 109540,
        "sha256": "45bbac6b341c319adc98a532532882e91a9cefc0329aa57bac9ae761c27b291c",
    },
}


def normalize_model_path(value: Any) -> str:
    raw = str(value or "").strip().strip('"')
    if not raw:
        return ""
    expanded = os.path.expandvars(os.path.expanduser(raw))
    return os.path.abspath(expanded)


def default_model_path() -> str:
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / "AppData" / "Local"
    return str(base / "AlicianDictionary" / "Models" / "text2vec-base-chinese")


def get_registered_model_path() -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, MODEL_REGISTRY_KEY) as key:
            value, _ = winreg.QueryValueEx(key, MODEL_REGISTRY_VALUE)
        return normalize_model_path(value)
    except (FileNotFoundError, OSError, TypeError):
        return ""


def set_registered_model_path(path: Any) -> bool:
    normalized = normalize_model_path(path)
    if not normalized or os.name != "nt":
        return False
    try:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, MODEL_REGISTRY_KEY) as key:
            winreg.SetValueEx(key, MODEL_REGISTRY_VALUE, 0, winreg.REG_SZ, normalized)
        return True
    except OSError:
        return False


def resolve_configured_model_path(saved_path: Any = "") -> str:
    environment_path = normalize_model_path(
        os.environ.get(MODEL_ENVIRONMENT_VARIABLE, "")
    )
    if environment_path:
        return environment_path
    registered_path = get_registered_model_path()
    if registered_path:
        return registered_path
    normalized_saved_path = normalize_model_path(saved_path)
    if normalized_saved_path:
        return normalized_saved_path
    return default_model_path()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_model_path(path: Any, verify_hashes: bool = False) -> Dict[str, Any]:
    normalized = normalize_model_path(path)
    if not normalized:
        return {
            "ok": False,
            "path": "",
            "message": "尚未设置模型目录。",
            "missing": list(MODEL_FILES),
            "mismatched": [],
        }

    root = Path(normalized)
    if not root.is_dir():
        return {
            "ok": False,
            "path": normalized,
            "message": "模型目录不存在。请重新运行安装器或选择已有模型目录。",
            "missing": list(MODEL_FILES),
            "mismatched": [],
        }

    missing = []
    mismatched = []
    for name, metadata in MODEL_FILES.items():
        candidate = root / name
        if not candidate.is_file():
            missing.append(name)
            continue
        try:
            if candidate.stat().st_size != int(metadata["size"]):
                mismatched.append(name)
                continue
            if verify_hashes and _sha256(candidate).lower() != metadata["sha256"]:
                mismatched.append(name)
        except OSError:
            mismatched.append(name)

    ok = not missing and not mismatched
    if ok:
        message = "模型文件完整。"
    elif missing:
        message = "模型文件不完整，缺少：" + "、".join(missing)
    else:
        message = "模型文件校验失败：" + "、".join(mismatched)
    return {
        "ok": ok,
        "path": normalized,
        "message": message,
        "missing": missing,
        "mismatched": mismatched,
    }


def configure_model_environment(saved_path: Any = "") -> str:
    resolved = resolve_configured_model_path(saved_path)
    os.environ[MODEL_ENVIRONMENT_VARIABLE] = resolved
    return resolved


def find_cached_model_snapshot() -> Optional[Path]:
    """Return the pinned Hugging Face snapshot when it is present locally."""
    try:
        from huggingface_hub import snapshot_download

        return Path(
            snapshot_download(
                MODEL_NAME,
                revision=MODEL_REVISION,
                local_files_only=True,
            )
        )
    except Exception:
        return None
