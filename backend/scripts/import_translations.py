#!/usr/bin/env python3
"""
import_translations.py — Prisma-free replacement for frontend/scripts/import-translations.ts.

Functional clone (2026-08-19), for the open-source (Python) side of the
Prisma-removal design (see workbench-documents/workbench-removing-prisma-design.html).
Running either importer delivers the same result: identical flatten semantics,
identical language-name matrix injection (A3.5), identical console output, and
an identical upsert end-state in the "Translation" table.

Declared deviation from the TS (flagged): all upserts run inside ONE asyncpg
transaction (AGENTS.md SQL transaction rule for multi-row writes). The TS
performs N independent upserts. Success-path behaviour, console output and the
final table state are identical; the difference is only all-or-nothing on
failure.

keyOrigin: each row records which codebase the key came from — F frontend,
P Python backend, G Go backend, X not attributed. The importer resolves it from
the YAML's location (frontend/locales/<lang>.yaml vs
backend/locales/<lang>-backend.yaml) and prints what it resolved. --origin
overrides that for a file the inference does not recognise, and a recognised
path that contradicts the override is an error rather than a guess.

Usage (from the repo root):
    backend/venv/bin/python backend/scripts/import_translations.py <language> <yaml-file>
    backend/venv/bin/python backend/scripts/import_translations.py es backend/locales/es-backend.yaml
    backend/venv/bin/python backend/scripts/import_translations.py es <file> --origin P

Requires: PyYAML + asyncpg (both present in backend/venv), and DATABASE_URL
in backend/.env (or the environment).
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / "frontend" / "locales" / "lang-names.json"
BACKEND_ENV = REPO_ROOT / "backend" / ".env"


# Complete ISO 639-1 language names (native) — transcribed from the TS.
LANGUAGE_NAME_MAP = {
    "aa": "Afaraf", "ab": "Аҧсшәа", "ae": "Avestan", "af": "Afrikaans",
    "ak": "Akan", "am": "አማርኛ", "an": "Aragonés", "ar": "العربية",
    "as": "অসমীয়া", "av": "Авар", "ay": "Aymar", "az": "Azərbaycan",
    "ba": "Башҡорт", "be": "Беларуская", "bg": "Български", "bh": "भोजपुरी",
    "bi": "Bislama", "bm": "Bamanankan", "bn": "বাংলা", "bo": "བོད་ཡིག",
    "br": "Brezhoneg", "bs": "Bosanski", "ca": "Català", "ce": "Нохчийн",
    "ch": "Chamoru", "co": "Corsu", "cr": "ᓀᐦᐃᔭᐍᐏᐣ", "cs": "Čeština",
    "cu": "ѩзыкъ словѣньскъ", "cv": "Чӑваш", "cy": "Cymraeg", "da": "Dansk",
    "de": "Deutsch", "dv": "ދިވެހި", "dz": "རྫོང་ཁ", "ee": "Eʋegbe",
    "el": "Ελληνικά", "en": "English", "eo": "Esperanto", "es": "Español",
    "et": "Eesti", "eu": "Euskara", "fa": "فارسی", "ff": "Fulfulde",
    "fi": "Suomi", "fj": "Vakaviti", "fo": "Føroyskt", "fr": "Français",
    "fy": "Frysk", "ga": "Gaeilge", "gd": "Gàidhlig", "gl": "Galego",
    "gn": "Avañe'ẽ", "gu": "ગુજરાતી", "gv": "Gaelg", "ha": "هَوُسَ",
    "he": "עברית", "hi": "हिन्दी", "ho": "Hiri Motu", "hr": "Hrvatski",
    "ht": "Kreyòl ayisyen", "hu": "Magyar", "hy": "Հայերեն", "hz": "Otjiherero",
    "ia": "Interlingua", "id": "Bahasa Indonesia", "ie": "Interlingue", "ig": "Igbo",
    "ii": "ꆈꌠ꒿ Nuosuhxop", "ik": "Iñupiatun", "io": "Ido", "is": "Íslenska",
    "it": "Italiano", "iu": "ᐃᓄᒃᑎᑐᑦ", "ja": "日本語", "jv": "Basa Jawa",
    "ka": "ქართული", "kg": "Kikongo", "ki": "Gĩkũyũ", "kj": "Kuanyama",
    "kk": "Қазақша", "kl": "Kalaallisut", "km": "ខ្មែរ", "kn": "ಕನ್ನಡ",
    "ko": "한국어", "kr": "Kanuri", "ks": "कॉशुर", "ku": "Kurdî",
    "kv": "Коми", "kw": "Kernewek", "ky": "Кыргызча", "la": "Latina",
    "lb": "Lëtzebuergesch", "lg": "Luganda", "li": "Limburgs", "ln": "Lingála",
    "lo": "ລາວ", "lt": "Lietuvių", "lu": "Tshiluba", "lv": "Latviešu",
    "mg": "Malagasy", "mh": "Kajin M̧ajeļ", "mi": "Māori", "mk": "Македонски",
    "ml": "മലയാളം", "mn": "Монгол", "mr": "मराठी", "ms": "Melayu",
    "mt": "Malti", "my": "ဗမာစာ", "na": "Dorerin Naoero", "nb": "Norsk bokmål",
    "nd": "isiNdebele", "ne": "नेपाली", "ng": "Owambo", "nl": "Nederlands",
    "nn": "Norsk nynorsk", "no": "Norsk", "nr": "isiNdebele", "nv": "Diné bizaad",
    "ny": "ChiCheŵa", "oc": "Occitan", "oj": "Anishinaabemowin", "om": "Afaan Oromoo",
    "or": "ଓଡ଼ିଆ", "os": "Ирон", "pa": "ਪੰਜਾਬੀ", "pi": "पालि",
    "pl": "Polski", "ps": "پښتو", "pt": "Português", "qu": "Runa Simi",
    "rm": "Rumantsch", "rn": "Ikirundi", "ro": "Română", "ru": "Русский",
    "rw": "Ikinyarwanda", "sa": "संस्कृतम्", "sc": "Sardu", "sd": "سنڌي",
    "se": "Davvisámegiella", "sg": "Yângâ tî Sängö", "si": "සිංහල", "sk": "Slovenčina",
    "sl": "Slovenščina", "sm": "Gagana fa'a Sāmoa", "sn": "chiShona", "so": "Soomaali",
    "sq": "Shqip", "sr": "Српски", "ss": "SiSwati", "st": "Sesotho",
    "su": "Basa Sunda", "sv": "Svenska", "sw": "Kiswahili", "ta": "தமிழ்",
    "te": "తెలుగు", "tg": "Тоҷикӣ", "th": "ไทย", "ti": "ትግርኛ",
    "tk": "Türkmençe", "tl": "Tagalog", "tn": "Setswana", "to": "Faka Tonga",
    "tr": "Türkçe", "ts": "Xitsonga", "tt": "Татар", "tw": "Twi",
    "ty": "Reo Tahiti", "ug": "ئۇيغۇرچە", "uk": "Українська", "ur": "اردو",
    "uz": "Oʻzbek", "ve": "Tshivenḓa", "vi": "Tiếng Việt", "vo": "Volapük",
    "wa": "Walon", "wo": "Wolof", "xh": "isiXhosa", "yi": "ייִדיש",
    "yo": "Yorùbá", "za": "Sawcuengh", "zh": "中文", "zu": "isiZulu",
}


def js_string(value):
    """Mirror JavaScript String() coercion for YAML scalars."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ",".join(js_string(v) for v in value)
    return str(value)


def first(*values):
    """Mirror the JS ?? chain: first value that is not None (nullish)."""
    for value in values:
        if value is not None:
            return value
    return None


def flatten(obj, prefix=""):
    """Mirror the TS flatten(): nested dicts → dot keys; scalars stringified.

    JS semantics preserved: null values are dropped (for-in over null is a
    no-op); a value wrapped in single quotes has them stripped and '' is
    unescaped to ' (the extraction script's quoting convention).
    """
    result = {}
    for key, value in obj.items():
        new_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten(value, new_key))
        elif value is None:
            continue
        else:
            s = js_string(value)
            if s.startswith("'") and s.endswith("'"):
                s = s[1:-1]
                s = s.replace("''", "'")
            result[new_key] = s
    return result


def apply_matrix(flat, lang):
    """A3.5 — inject the full language-name matrix for this viewer language.

    locales/lang-names.json is authoritative for language.name.* keys and
    overwrites YAML-supplied name keys. Missing localized rows fall back to
    the autonym; codes absent from the matrix fall back to the ISO map.
    Failure is non-fatal (warn and continue), matching the TS.
    """
    try:
        matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        codes = matrix.get("languages") or []
        autonyms = matrix.get("autonyms") or {}
        viewer_row = (matrix.get("localized") or {}).get(lang) or {}
        for code in codes:
            if code == lang:
                value = first(autonyms.get(code), LANGUAGE_NAME_MAP.get(code))
            else:
                value = first(viewer_row.get(code), autonyms.get(code),
                              LANGUAGE_NAME_MAP.get(code))
            if value:
                flat[f"language.name.{code}"] = value
    except Exception as error:
        print(f"⚠️ Language-name matrix not applied: {error}", file=sys.stderr)


def load_database_url():
    """DATABASE_URL from the environment, else from backend/.env."""
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    for line in BACKEND_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("DATABASE_URL not found in backend/.env or the environment")


def describe_cluster(url: str) -> str:
    """Return 'host:port' for the workbench cluster the DSN points at.

    Printed before connecting so a run states which cluster it wrote to. The
    migration moved the product from 5432 to 9431, and an import into the wrong
    cluster reports success while changing nothing anyone can see -- so the
    cluster is named rather than inferred.
    """
    parsed = urlparse(url)
    return f"{parsed.hostname}:{parsed.port or 5432}"


# ---- keyOrigin --------------------------------------------------------------
# Which codebase a key came from. The vocabulary matches the database CHECK
# constraint, so an override can never write a value the column would reject.
VALID_ORIGINS = ("F", "P", "G", "X")


def infer_origin(file_path):
    """The origin a locale file's location declares, or None if unrecognised.

    The two extractors write exactly two shapes, recognised by the directory
    pair plus the file name:
        <repo>/frontend/locales/<lang>.yaml          -> F
        <repo>/backend/locales/<lang>-backend.yaml   -> P
    A bare file name is deliberately not enough — any stray en.yaml would
    otherwise be attributed to the frontend.
    """
    path = Path(file_path)
    if path.parent.name != "locales":
        return None
    repo_dir = path.parent.parent.name
    if repo_dir == "frontend" and not path.name.endswith("-backend.yaml"):
        return "F"
    if repo_dir == "backend" and path.name.endswith("-backend.yaml"):
        return "P"
    return None


def resolve_origin(file_path, override=None):
    """(origin, explanation) for this file. Raises ValueError rather than guess.

    An override wins — that is what it is for — but a recognised path that
    contradicts it is an error: one of the two signals is a caller bug, and
    honouring either silently would mis-attribute a whole locale.
    """
    if override is not None and override not in VALID_ORIGINS:
        raise ValueError(
            f"--origin must be one of {'|'.join(VALID_ORIGINS)}, not {override!r}"
        )
    inferred = infer_origin(file_path)
    if override is None:
        if inferred is None:
            raise ValueError(
                f"cannot infer the key origin from {file_path!r} — pass --origin F|P"
            )
        return inferred, f"inferred from {file_path}"
    if inferred is not None and inferred != override:
        raise ValueError(
            f"--origin {override} contradicts {file_path!r}, which indicates "
            f"{inferred} — refusing to guess"
        )
    if inferred is not None:
        return override, "--origin override; path also indicates " + (
            "frontend" if inferred == "F" else "backend"
        )
    return override, "--origin override; input path not recognised"


async def import_language(language_code, file_path, origin_override=None, check_only=False):
    """Import one locale YAML file into the Translation table.

    Returns True when the database differed from the YAML (rows were added or
    updated), False when every row already matched. With `check_only` the
    reporting is identical but nothing is written, so a caller can ask "is this
    file already imported?" without any side effect.

    The key origin is resolved from the file's location unless `origin_override`
    is given; an unresolvable or contradictory origin raises rather than writing
    a guess.
    """
    origin, origin_note = resolve_origin(file_path, origin_override)
    print(f"📥 Importing translations for: {language_code}")
    print(f"📄 Source file: {file_path}")
    print(f"🏷️ origin: {origin}  ({origin_note})")

    # Read and parse YAML
    data = yaml.safe_load(Path(file_path).read_text(encoding="utf-8"))
    flat = flatten(data or {})

    # Keys the YAML itself declares. Anything present only after the injections
    # below was generated by this importer rather than declared by a codebase, so
    # it carries no origin — those rows stay at 'X'.
    declared = set(flat)

    # Inject language name
    if LANGUAGE_NAME_MAP.get(language_code):
        flat[f"language.name.{language_code}"] = LANGUAGE_NAME_MAP[language_code]

    # A3.5 language-name matrix
    apply_matrix(flat, language_code)

    injected = set(flat) - declared

    total_keys = len(flat)
    print(f"📊 Found {total_keys} keys in YAML file")

    database_url = load_database_url()
    print(f"🗄️  Workbench database cluster: {describe_cluster(database_url)}")
    conn = await asyncpg.connect(database_url)
    try:
        # Get existing translations for this language
        existing = await conn.fetch(
            'SELECT key, value, "keyOrigin" FROM "Translation" WHERE language = $1',
            language_code,
        )
        # The origin is part of the comparison: a row whose text matches but
        # whose origin does not is still a row this import will write, and
        # --check must agree with what the import would do.
        existing_map = {row["key"]: (row["value"], row["keyOrigin"]) for row in existing}
        existing_count = len(existing_map)
        print(f"📊 Existing translations in database: {existing_count}")

        # Each key's origin: the file's, except the injected keys — generated by
        # this importer rather than declared by a codebase, so they hold none.
        rows = [
            (key, value, "X" if key in injected else origin)
            for key, value in flat.items()
        ]

        # Count keys that will be added vs updated
        added = updated = skipped = 0
        for key, value, row_origin in rows:
            current = existing_map.get(key)
            if current is None:
                added += 1
            elif current != (value, row_origin):
                updated += 1
            else:
                skipped += 1
        print(f"📊 Changes: {added} new, {updated} updated, {skipped} unchanged")

        changed = (added + updated) > 0

        # --check: report only, never write. Exits 1 when the database is behind
        # the YAML and 0 when every row already matches, so a build or a
        # pipeline can gate on it without parsing output.
        if check_only:
            if changed:
                print(f"❌ {language_code} is out of date — {added + updated} of "
                      f"{total_keys} rows would change ({added} new, {updated} updated)")
                print(f"   --check: leaving the database untouched.")
            else:
                print(f"✅ No changes — {language_code} is already up to date "
                      f"({skipped} rows match)")
            return changed

        # Upserts — one transaction (declared deviation from the TS, which
        # performs N independent upserts; AGENTS.md SQL transaction rule).
        async with conn.transaction():
            for key, value, row_origin in rows:
                await conn.execute(
                    'INSERT INTO "Translation" (key, language, value, "keyOrigin", "updatedAt") '
                    "VALUES ($1, $2, $3, $4, NOW()) "
                    "ON CONFLICT (key, language) "
                    'DO UPDATE SET value = $3, "keyOrigin" = $4, "updatedAt" = NOW()',
                    key, language_code, value, row_origin,
                )

        # Get final count
        final_count = await conn.fetchval(
            'SELECT COUNT(*) FROM "Translation" WHERE language = $1',
            language_code,
        )

        print(f"✅ Imported {total_keys} translations for {language_code}")
        print(f"📊 Final database count for {language_code}: {final_count} translations")
        print(f"   ({added} added, {updated} updated, {skipped} unchanged)")
        return changed
    finally:
        await conn.close()


def main():
    # --check may appear anywhere in the argument list; the two positional
    # arguments keep their existing order. --origin takes a value.
    check_only = "--check" in sys.argv[1:]
    rest = [a for a in sys.argv[1:] if a != "--check"]

    origin_override = None
    args = []
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--origin":
            if i + 1 >= len(rest):
                print("❌ --origin needs a value (F|P|G|X)", file=sys.stderr)
                sys.exit(1)
            origin_override = rest[i + 1]
            i += 2
            continue
        if arg.startswith("--origin="):
            origin_override = arg.split("=", 1)[1]
            i += 1
            continue
        args.append(arg)
        i += 1

    if len(args) < 2:
        print("❌ Usage: python backend/scripts/import_translations.py <language> <yaml-file>",
              file=sys.stderr)
        print("   Example: python backend/scripts/import_translations.py es backend/locales/es-backend.yaml",
              file=sys.stderr)
        print("   --origin F|P|G|X  override the origin inferred from the file's location",
              file=sys.stderr)
        print("   --check  report whether the database is behind the YAML; write nothing",
              file=sys.stderr)
        sys.exit(1)

    language = args[0]
    file_path = args[1]

    try:
        changed = asyncio.run(
            import_language(language, file_path, origin_override, check_only=check_only)
        )
    except Exception as error:
        print(f"❌ Import failed: {error}", file=sys.stderr)
        sys.exit(1)

    # Default: always exit 0. --check: exit 1 when the database is out of date.
    if check_only:
        sys.exit(1 if changed else 0)


if __name__ == "__main__":
    main()
