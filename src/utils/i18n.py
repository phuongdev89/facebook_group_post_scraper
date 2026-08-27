import json
import os
import sys
from typing import Callable, Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Global current language state
_CURRENT_LANGUAGE = "vi"
_LISTENERS: List[Callable[[str], None]] = []
SUPPORTED_LANGUAGES = ["vi", "en"]

# Cache of loaded translations from JSON files (locales/vi.json and locales/en.json)
_LOADED_TRANSLATIONS: Dict[str, Dict[str, str]] = {}
TRANSLATIONS: Dict[str, Dict[str, str]] = {}


def get_locales_dir() -> str:
    """Return the absolute path to locales directory (src/locales or locales)"""
    base_dirs = []
    if hasattr(sys, '_MEIPASS') and sys._MEIPASS:
        base_dirs.append(sys._MEIPASS)
    if getattr(sys, 'frozen', False) and sys.executable:
        exe_dir = os.path.dirname(sys.executable)
        base_dirs.append(exe_dir)
        base_dirs.append(os.path.join(exe_dir, "_internal"))
    base_dirs.append(PROJECT_ROOT)
    base_dirs.append(os.path.abspath("."))

    for b in base_dirs:
        # Check src/locales first
        p_src = os.path.join(b, "src", "locales")
        if os.path.isdir(p_src):
            return p_src
        # Check root locales
        p = os.path.join(b, "locales")
        if os.path.isdir(p):
            return p
        # Check assets/locales
        p_assets = os.path.join(b, "assets", "locales")
        if os.path.isdir(p_assets):
            return p_assets
        # Check _internal/src/locales
        p_internal_src = os.path.join(b, "_internal", "src", "locales")
        if os.path.isdir(p_internal_src):
            return p_internal_src
    return os.path.join(PROJECT_ROOT, "src", "locales")


def load_translations_from_file(lang: str) -> Dict[str, str]:
    """Load translation dictionary from JSON file (e.g. locales/vi.json or locales/en.json)"""
    locales_dir = get_locales_dir()
    json_path = os.path.join(locales_dir, f"{lang}.json")

    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"[i18n] Error loading {json_path}: {e}")
    return {}


def reload_translations():
    """Reload all translation JSON files into memory cache"""
    global _LOADED_TRANSLATIONS, TRANSLATIONS
    for lang in SUPPORTED_LANGUAGES:
        _LOADED_TRANSLATIONS[lang] = load_translations_from_file(lang)
    TRANSLATIONS.clear()
    TRANSLATIONS.update(_LOADED_TRANSLATIONS)


# Initial load from locales/vi.json and locales/en.json
reload_translations()


def get_current_language() -> str:
    """Return active language code ('vi' or 'en')"""
    global _CURRENT_LANGUAGE
    return _CURRENT_LANGUAGE


def set_current_language(lang_code: str):
    """Set active language code ('vi' or 'en') and notify registered listeners"""
    global _CURRENT_LANGUAGE
    if lang_code in ("vi", "en"):
        _CURRENT_LANGUAGE = lang_code
        for callback in list(_LISTENERS):
            try:
                callback(_CURRENT_LANGUAGE)
            except Exception:
                pass


def register_language_listener(callback: Callable[[str], None]):
    """Register a callback function to be called whenever the language changes"""
    if callback not in _LISTENERS:
        _LISTENERS.append(callback)


def unregister_language_listener(callback: Callable[[str], None]):
    """Unregister a language change listener callback"""
    if callback in _LISTENERS:
        _LISTENERS.remove(callback)


def tr(key: str, lang: str = None, **kwargs) -> str:
    """
    Get translated text for given key in current or specified language.
    Supports Python str.format(**kwargs) interpolation.
    """
    l = lang or _CURRENT_LANGUAGE
    lang_dict = TRANSLATIONS.get(l, TRANSLATIONS["vi"])
    text = lang_dict.get(key, TRANSLATIONS["vi"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def get_flag_svg_path(lang: str) -> str:
    """Return absolute path to flag SVG asset"""
    base_dirs = []
    if hasattr(sys, '_MEIPASS') and sys._MEIPASS:
        base_dirs.append(sys._MEIPASS)
    if getattr(sys, 'frozen', False) and sys.executable:
        exe_dir = os.path.dirname(sys.executable)
        base_dirs.append(exe_dir)
        base_dirs.append(os.path.join(exe_dir, "_internal"))
    base_dirs.append(PROJECT_ROOT)
    base_dirs.append(os.path.abspath("."))

    flag_file = "vn.svg" if lang.lower() in ("vi", "vn") else "us.svg"
    for b in base_dirs:
        p = os.path.join(b, "assets", "flags", flag_file)
        if os.path.exists(p):
            return p
    return ""
