from __future__ import annotations

import winreg

REG_ROOT = winreg.HKEY_CURRENT_USER
REG_SUBKEY = r"Software\Meartraep\AlicianDictionary"
REG_VALUE_NAME = "FirstLaunchCompleted"
REG_VALUE_DATA = "1"


def _ensure_key() -> None:
    winreg.CreateKey(REG_ROOT, REG_SUBKEY)


def is_first_launch() -> bool:
    try:
        key = winreg.OpenKey(REG_ROOT, REG_SUBKEY)
        try:
            winreg.QueryValueEx(key, REG_VALUE_NAME)
            return False
        except FileNotFoundError:
            return True
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        return True


def mark_launched() -> None:
    _ensure_key()
    key = winreg.OpenKey(REG_ROOT, REG_SUBKEY, 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, REG_VALUE_NAME, 0, winreg.REG_SZ, REG_VALUE_DATA)
    winreg.CloseKey(key)


def delete_launch_mark() -> bool:
    try:
        key = winreg.OpenKey(REG_ROOT, REG_SUBKEY, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, REG_VALUE_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        return False
