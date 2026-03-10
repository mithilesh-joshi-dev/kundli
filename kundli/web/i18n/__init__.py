"""Multi-language support for Kundli web app."""

from importlib import import_module

_CACHE: dict[str, dict[str, str]] = {}

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "हिन्दी",
    "mr": "मराठी",
}


def _load_lang(lang: str) -> dict[str, str]:
    if lang not in _CACHE:
        try:
            mod = import_module(f".{lang}", package=__package__)
            _CACHE[lang] = mod.TRANSLATIONS
        except (ImportError, AttributeError):
            _CACHE[lang] = {}
    return _CACHE[lang]


def get_translator(lang: str = "mr"):
    """Return a T(key, **kwargs) function for the given language."""
    translations = _load_lang(lang)
    fallback = _load_lang("en") if lang != "en" else {}

    def T(key: str, **kwargs) -> str:
        val = translations.get(key) or fallback.get(key) or key
        if kwargs:
            try:
                val = val.format(**kwargs)
            except (KeyError, IndexError):
                pass
        return val

    return T
