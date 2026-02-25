import json
import os
import sys
from typing import Dict

def base_path():
    if hasattr(sys, "_MEIPASS"):   # PyInstaller 打包后
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(__file__))  # 正常开发时

def load_lang(lang_code: str) -> Dict[str, str]:
    path = os.path.join(base_path(), "i18n", f"{lang_code}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)