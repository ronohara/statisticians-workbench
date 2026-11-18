"""
Language context management for chat.
Handles user language detection and system message generation for language context.
"""

import asyncpg
from typing import Dict, Any

# Full ISO 639-1 language codes and English names
LANGUAGE_NAMES = {
    "aa": "Afar",
    "ab": "Abkhazian",
    "ae": "Avestan",
    "af": "Afrikaans",
    "ak": "Akan",
    "am": "Amharic",
    "an": "Aragonese",
    "ar": "Arabic",
    "as": "Assamese",
    "av": "Avaric",
    "ay": "Aymara",
    "az": "Azerbaijani",
    "ba": "Bashkir",
    "be": "Belarusian",
    "bg": "Bulgarian",
    "bh": "Bihari",
    "bi": "Bislama",
    "bm": "Bambara",
    "bn": "Bengali",
    "bo": "Tibetan",
    "br": "Breton",
    "bs": "Bosnian",
    "ca": "Catalan",
    "ce": "Chechen",
    "ch": "Chamorro",
    "co": "Corsican",
    "cr": "Cree",
    "cs": "Czech",
    "cu": "Church Slavic",
    "cv": "Chuvash",
    "cy": "Welsh",
    "da": "Danish",
    "de": "German",
    "dv": "Divehi",
    "dz": "Dzongkha",
    "ee": "Ewe",
    "el": "Greek",
    "en": "English",
    "eo": "Esperanto",
    "es": "Spanish",
    "et": "Estonian",
    "eu": "Basque",
    "fa": "Persian",
    "ff": "Fulah",
    "fi": "Finnish",
    "fj": "Fijian",
    "fo": "Faroese",
    "fr": "French",
    "fy": "Western Frisian",
    "ga": "Irish",
    "gd": "Scottish Gaelic",
    "gl": "Galician",
    "gn": "Guarani",
    "gu": "Gujarati",
    "gv": "Manx",
    "ha": "Hausa",
    "he": "Hebrew",
    "hi": "Hindi",
    "ho": "Hiri Motu",
    "hr": "Croatian",
    "ht": "Haitian",
    "hu": "Hungarian",
    "hy": "Armenian",
    "hz": "Herero",
    "ia": "Interlingua",
    "id": "Indonesian",
    "ie": "Interlingue",
    "ig": "Igbo",
    "ii": "Sichuan Yi",
    "ik": "Inupiaq",
    "io": "Ido",
    "is": "Icelandic",
    "it": "Italian",
    "iu": "Inuktitut",
    "ja": "Japanese",
    "jv": "Javanese",
    "ka": "Georgian",
    "kg": "Kongo",
    "ki": "Kikuyu",
    "kj": "Kuanyama",
    "kk": "Kazakh",
    "kl": "Kalaallisut",
    "km": "Central Khmer",
    "kn": "Kannada",
    "ko": "Korean",
    "kr": "Kanuri",
    "ks": "Kashmiri",
    "ku": "Kurdish",
    "kv": "Komi",
    "kw": "Cornish",
    "ky": "Kirghiz",
    "la": "Latin",
    "lb": "Luxembourgish",
    "lg": "Ganda",
    "li": "Limburgan",
    "ln": "Lingala",
    "lo": "Lao",
    "lt": "Lithuanian",
    "lu": "Luba-Katanga",
    "lv": "Latvian",
    "mg": "Malagasy",
    "mh": "Marshallese",
    "mi": "Maori",
    "mk": "Macedonian",
    "ml": "Malayalam",
    "mn": "Mongolian",
    "mr": "Marathi",
    "ms": "Malay",
    "mt": "Maltese",
    "my": "Burmese",
    "na": "Nauru",
    "nb": "Bokmål, Norwegian",
    "nd": "Ndebele, North",
    "ne": "Nepali",
    "ng": "Ndonga",
    "nl": "Dutch",
    "nn": "Nynorsk, Norwegian",
    "no": "Norwegian",
    "nr": "Ndebele, South",
    "nv": "Navajo",
    "ny": "Chichewa",
    "oc": "Occitan",
    "oj": "Ojibwa",
    "om": "Oromo",
    "or": "Oriya",
    "os": "Ossetian",
    "pa": "Panjabi",
    "pi": "Pali",
    "pl": "Polish",
    "ps": "Pashto",
    "pt": "Portuguese",
    "qu": "Quechua",
    "rm": "Romansh",
    "rn": "Rundi",
    "ro": "Romanian",
    "ru": "Russian",
    "rw": "Kinyarwanda",
    "sa": "Sanskrit",
    "sc": "Sardinian",
    "sd": "Sindhi",
    "se": "Northern Sami",
    "sg": "Sango",
    "si": "Sinhala",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sm": "Samoan",
    "sn": "Shona",
    "so": "Somali",
    "sq": "Albanian",
    "sr": "Serbian",
    "ss": "Swati",
    "st": "Sotho, Southern",
    "su": "Sundanese",
    "sv": "Swedish",
    "sw": "Swahili",
    "ta": "Tamil",
    "te": "Telugu",
    "tg": "Tajik",
    "th": "Thai",
    "ti": "Tigrinya",
    "tk": "Turkmen",
    "tl": "Tagalog",
    "tn": "Tswana",
    "to": "Tonga",
    "tr": "Turkish",
    "ts": "Tsonga",
    "tt": "Tatar",
    "tw": "Twi",
    "ty": "Tahitian",
    "ug": "Uighur",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "uz": "Uzbek",
    "ve": "Venda",
    "vi": "Vietnamese",
    "vo": "Volapük",
    "wa": "Walloon",
    "wo": "Wolof",
    "xh": "Xhosa",
    "yi": "Yiddish",
    "yo": "Yoruba",
    "za": "Zhuang",
    "zh": "Chinese",
    "zu": "Zulu",
}


def get_language_name(lang_code: str) -> str:
    """
    Get the English name of a language from its ISO 639-1 code.
    
    Args:
        lang_code: The ISO 639-1 language code
        
    Returns:
        The English name of the language, or the code if not found
    """
    return LANGUAGE_NAMES.get(lang_code, lang_code)


#: Emitted for English, and for a session with no language set.
#:
#: This used to be "" — the doctrine being that English needs no telling. A
#: virtual-dataset session disproved it on 2026-11-11: with no language clause
#: anywhere, the model wrote a goal in Chinese (message 27 of chat
#: vdc_0d72adad56cf4b2d), then read its own Chinese back off the scoreboard the
#: next turn and answered in Chinese — and when asked, said correctly that it had
#: never been told a preference. The instruction was absent by design, and absence
#: is not neutral: it hands the language choice to whatever text the model saw last.
#:
#: The wording is deliberately one clause, not the full non-English instruction.
#: English is the common case, so this is on every concierge turn's token bill; a
#: clause that names the failure mode is enough, and it does not restate the
#: no-English rule that only makes sense for a non-English target.
_ENGLISH_INSTRUCTION = "Reply in the language the user writes in.\n\n"


def language_instruction(language: str) -> str:
    """Return the priming instruction telling the LLM which language to answer in.

    Never "" — see `_ENGLISH_INSTRUCTION` for why English is told something too.

    Keys on the ISO-639 code (the one reliable invariant) and resolves the
    English name from the static LANGUAGE_NAMES table. The code &rarr; name
    correlation is a fixed standard, so no runtime lookup is required; unknown
    codes fall back to the code itself. Callers splice the result in
    unconditionally (system_prompt = language_instruction(lang) + system_prompt).
    """
    if not language or language == "en":
        return _ENGLISH_INSTRUCTION
    name = get_language_name(language)
    return (
        f"Respond in {name} ({language}). "
        f"Do NOT include any English text in your response. "
        f"All labels, explanations, and JSON values must be in {name}.\n\n"
    )


async def get_user_language(
    db_pool: asyncpg.Pool,
    user_id: str
) -> str:
    """
    Get the user's preferred language from their settings.
    
    Args:
        db_pool: Database connection pool
        user_id: The user ID
        
    Returns:
        The user's language code, or 'en' if not set
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT language FROM "User" WHERE id = $1',
            user_id
        )
        if row and row["language"]:
            return row["language"]
        return "en"


async def get_language_context_message(
    db_pool: asyncpg.Pool,
    user_id: str
) -> str:
    """
    Get the language context system message for a user.
    
    Args:
        db_pool: Database connection pool
        user_id: The user ID
        
    Returns:
        The language context message, e.g.,
        "Respond in Spanish. Use Spanish for all answers unless I explicitly ask you to switch languages."
    """
    user_language = await get_user_language(db_pool, user_id)
    language_name = get_language_name(user_language)
    return f"Respond in {language_name}. Use {language_name} for all answers unless I explicitly ask you to switch languages."