"""
Language module — meertalige ondersteuning voor Server Up.

Biedt:
  - /api/i18n/available  → lijst van beschikbare talen
  - /api/i18n/<lang>     → vertaalstrings voor een taal (+ module-vertalingen)
  - /api/i18n/detect     → detecteer taal uit Accept-Language header

Module-vertalingen:
  Elke module kan een class-attribuut definiëren:
    TRANSLATIONS = {
        "en": {"my.key": "English text"},
        "nl": {"my.key": "Nederlandse tekst"},
    }
  Deze worden automatisch samengevoegd via /api/i18n/<lang>.
"""
from __future__ import annotations
import importlib
from pathlib import Path

from flask import Blueprint, jsonify, request

from modules.base import ModuleBase
from core import i18n


class LanguageModule(ModuleBase):
    MODULE_ID   = "language"
    MODULE_NAME = "Language"
    MODULE_ICON = "🌐"
    MODULE_DESC = "Multi-language support for the Server Up UI"
    VERSION     = "1.0.0"

    TRANSLATIONS = {
        "en": {
            "nav.language": "Language",
        },
        "nl": {
            "nav.language": "Taal",
        },
        "de": {"nav.language": "Sprache"},
        "fr": {"nav.language": "Langue"},
        "es": {"nav.language": "Idioma"},
        "pt": {"nav.language": "Idioma"},
    }

    def pages(self):
        # Geen eigen pagina — integreert in Instellingen
        return [
            {"id": "language", "label": "Language", "icon": "🌐",
             "group": "hidden", "default": False, "dashboard_widget": False},
        ]

    def on_load(self, app) -> None:
        i18n.load_all()
        print(f"  🌐 {len(i18n.available())} talen beschikbaar: "
              f"{', '.join(l['lang'] for l in i18n.available())}")

    def blueprint(self) -> Blueprint:
        bp = Blueprint("language", __name__)

        @bp.route("/api/i18n/available")
        def available_langs():
            return jsonify(languages=i18n.available())

        @bp.route("/api/i18n/detect")
        def detect_lang():
            accept = request.headers.get("Accept-Language", "")
            lang   = i18n.detect_lang(accept)
            langs  = i18n.available()
            meta   = next((l for l in langs if l["lang"] == lang), {})
            return jsonify(
                lang=lang,
                name=meta.get("name", lang),
                flag=meta.get("flag", ""),
                dir=meta.get("dir", "ltr"),
            )

        @bp.route("/api/i18n/<lang>")
        def get_lang(lang):
            # Verzamel module-vertalingen
            module_trans = _collect_module_translations(lang)
            strings      = i18n.get_strings(lang, module_trans)
            langs        = i18n.available()
            meta         = next((l for l in langs if l["lang"] == lang),
                                {"lang": lang, "name": lang})
            return jsonify(lang=lang, meta=meta, strings=strings)

        return bp


# ── Helpers ───────────────────────────────────────────────────────────────────

def _collect_module_translations(lang: str) -> dict:
    """
    Verzamel TRANSLATIONS van alle geladen modules.
    Geeft {lang: {key: val}} gecombineerd voor 'en' en target lang.
    """
    result: dict[str, dict] = {}
    modules_dir = Path(__file__).parent.parent

    for mod_dir in modules_dir.iterdir():
        if not mod_dir.is_dir() or mod_dir.name.startswith("_"):
            continue
        if not (mod_dir / "__init__.py").exists():
            continue
        try:
            pkg = importlib.import_module(f"modules.{mod_dir.name}")
            for name in dir(pkg):
                obj = getattr(pkg, name)
                if (isinstance(obj, type) and issubclass(obj, ModuleBase)
                        and obj is not ModuleBase):
                    trans = getattr(obj, "TRANSLATIONS", {})
                    for t_lang, strings in trans.items():
                        if t_lang not in result:
                            result[t_lang] = {}
                        result[t_lang].update(strings)
        except Exception:
            pass

    # Geef alleen en + target lang terug
    combined: dict[str, dict] = {}
    for t_lang in ("en", lang, lang.split("-")[0]):
        if t_lang in result:
            combined.setdefault(t_lang, {}).update(result[t_lang])
    return combined
