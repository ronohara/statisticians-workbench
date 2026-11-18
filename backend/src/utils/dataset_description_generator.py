import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.utils.ai_limits import AILimits
from src.utils.llm_connection import LLM
from src.utils.logger import Logger

logger = Logger("dataset_description_generator", see_time=False, console_log=True)

# This module no longer holds a bound. It used to: DESCRIPTION_TIMEOUT_SECONDS was a
# module constant because there was nowhere to put the value. Now there is — the
# pair's own tuning, the workbench default, and a per-request override, resolved by
# src/utils/ai_limits.py and passed in. A constant here would be a fourth home for a
# number that three tiers already answer.
#
# The measurement that first justified 600 s stands and is recorded in the litellm
# plan: deepseek-r1:8b on leno took 345 s, so any bound below that fails the request
# outright. The migration's workbench default is 120 s, which is deliberately NOT
# enough for that model — the pair is where a slow local model is given more.


@dataclass
class Field:
    """One field of a prompt signature: its name and the description of it.

    Mirrors Go's ``llm.field``.
    """

    name: str
    desc: str


@dataclass
class Signature:
    """A prompt signature as plain data: instruction, inputs, one output.

    Mirrors Go's ``llm.signature``. The prompt is built from this by
    ``build_prompt``; nothing here needs a library.
    """

    instruction: str
    input_fields: List[Field]
    output_field: Field


DATASET_DESCRIPTION_AGENT = Signature(
    instruction="Generate a concise, informative description of a dataset based on its structure and sample data.",
    input_fields=[
        Field("existing_description", "Existing description to improve upon (optional)"),
        Field("dataset", "Markdown representation of the dataset with column names, types, and sample rows"),
    ],
    output_field=Field("description", "A clear, detailed description of the dataset, including what it represents, key columns, and potential use cases"),
)

DATA_CONTEXT_GEN = Signature(
    instruction="Generate a comprehensive data context description for multiple datasets.",
    input_fields=[
        Field("user_description", "User-provided description or context"),
        Field("dataset_view", "Combined markdown view of all datasets"),
    ],
    output_field=Field("data_context", "A coherent description of the datasets, their relationships, and their intended use"),
)

# Full ISO 639-1 mapping of language codes to English names
ISO_639_1_LANGUAGES = {
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
    "zu": "Zulu"
}

def _dataset_columns(rows: List[dict]) -> List[str]:
    """Column names in first-appearance order (union of the row dicts' keys)."""
    columns = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    return columns


def _infer_dtype(values) -> str:
    """Return the pandas-style dtype string for a column's values (None = missing).

    Mirrors pd.DataFrame(list_of_dicts) inference: all-int → int64 (float64 once
    a None forces NaN), int/float mix or any float → float64, all-bool → bool
    (object once a None forces NaN), otherwise object.
    """
    non_null = [v for v in values if v is not None]
    has_none = len(non_null) < len(values)
    if not non_null:
        return "object"
    if all(isinstance(v, bool) for v in non_null):
        return "bool" if not has_none else "object"
    if all(isinstance(v, int) for v in non_null):
        return "float64" if has_none else "int64"
    if all(isinstance(v, (int, float)) for v in non_null):
        return "float64"
    return "object"


def _to_markdown(columns: List[str], rows: List[dict]) -> str:
    """Pipe markdown table (no index column), mirroring the Go port."""
    header = "| " + " | ".join(str(c) for c in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(c)) for c in columns) + " |")
    return "\n".join(lines)


def build_prompt(sig: Signature, inputs: Dict[str, str]) -> str:
    """Render the prompt for a signature.

    Mirrors Go's ``buildPrompt`` in ``internal/llm/dataset_description.go`` — the
    single-message ``field: value`` form that plan D2 (resolved as option (b))
    made the template for both backends. No ``[[ ## field ## ]]`` markers: with
    none in the prompt, no model is asked to produce them and neither backend
    needs a parser.

    The two implementations must stay byte-identical. Both suites assert the
    same expected literal — this module's test in ``test_dataset_description.py``
    and Go's in ``dataset_description_test.go`` — so a change to either side
    fails its own test rather than silently diverging.
    """
    parts = [sig.instruction + "\n\n", "Follow the following format.\n\n"]
    for f in sig.input_fields:
        parts.append(f"{f.name}: {f.desc}\n")
    parts.append(f"{sig.output_field.name}: {sig.output_field.desc}\n\n")
    for f in sig.input_fields:
        parts.append(f"{f.name}: {inputs[f.name]}\n")
    parts.append(f"{sig.output_field.name}:")
    return "".join(parts)


async def generate_dataset_description(
    lm: LLM,
    limits: AILimits,
    datasets: Dict[str, list],
    existing_description: str = "",
    dataset_names: Optional[List[str]] = None,
    language: str = "en",
    *,
    connect_timeout: float,
) -> str:
    """
    Generate an AI-powered description for one or more datasets using the provided LLM.

    Args:
        lm: A resolved LLM (provider and model) from create_llm.
        limits: The resolved limits for this (connection, model) pair. Required, not
            defaulted: a fallback here would be a fourth tier nobody can see, and the
            caller always knows the pair.
        datasets: Dictionary of dataset names to lists of row dicts (no pandas).
        existing_description: Existing description to improve upon (optional).
        dataset_names: List of dataset names to use in the description format (optional).
        language: Language code for the response (ISO 639-1, e.g., "en", "fr", "es").
        connect_timeout: The connect budget in force for this connection, in seconds.
            Required and keyword-only, for the same reason `limits` is required: a
            default here would silently substitute the compiled 10 s for a connection
            the administrator had configured, which is the defect plan Item 4a exists
            to remove. The caller always knows the connection.

    Returns:
        Generated description string with proper exact_python_name formatting.
    """
    try:
        if not datasets or len(datasets) == 0:
            return existing_description

        # Prepare language instruction
        language_instruction = ""
        if language and language.lower() != "en":
            lang_name = ISO_639_1_LANGUAGES.get(language.lower())
            if lang_name:
                language_instruction = f"Answer in {lang_name}. "
            else:
                # Fallback: use the code itself if not in the map
                language_instruction = f"Answer in {language}. "

        # Prepend language instruction to existing_description
        if language_instruction:
            if existing_description:
                existing_description = language_instruction + existing_description
            else:
                existing_description = language_instruction

        # Build dataset view for description generation
        dataset_view = ""
        count = 0
        for table_name, table_rows in datasets.items():
            head_rows = table_rows[:3]
            columns = _dataset_columns(head_rows)
            dtype_map = {col: _infer_dtype([r.get(col) for r in head_rows]) for col in columns}
            columns_repr = str([{col: dtype_map[col]} for col in columns])
            dataset_view += f"exact_table_name={table_name}\n:columns:{columns_repr}\n{_to_markdown(columns, head_rows)}\n"
            count += 1

        # Build the prompt for this signature and call the provider. The reply
        # is taken verbatim: the template instructs no markers, so there is
        # nothing to strip — the counterpart of Go's callPredict.
        if count == 1:
            sig = DATASET_DESCRIPTION_AGENT
            prompt = build_prompt(sig, {
                "existing_description": existing_description,
                "dataset": dataset_view,
            })
        elif count > 1:
            sig = DATA_CONTEXT_GEN
            prompt = build_prompt(sig, {
                "user_description": existing_description,
                "dataset_view": dataset_view,
            })
        else:
            sig = None
            prompt = None

        if sig is not None:
            response = await lm.provider.call(
                messages=[{"role": "user", "content": prompt}],
                model=lm.model,
                # From the resolver, not from this module: the pair's tuning wins over
                # the workbench default, and both win over the built-in. `lm` still
                # carries temperature and max_tokens from create_llm, but those are the
                # values create_llm was handed — the resolver is the one place that
                # knows what is actually in force.
                temperature=limits.temperature,
                max_tokens=limits.max_tokens,
                timeout=float(limits.timeout_seconds),
                connect_timeout=connect_timeout,
            )
            generated_desc = (response or {}).get("content", "")
        else:
            generated_desc = existing_description

        # Format the description with exact_python_name for all datasets
        if dataset_names and len(dataset_names) > 0:
            if len(dataset_names) == 1:
                formatted_desc = f" exact_python_name: `{dataset_names[0]}` Dataset: {generated_desc}"
            else:
                names_list = ", ".join([f"`{name}`" for name in dataset_names])
                formatted_desc = f" exact_python_name: {names_list} Dataset: {generated_desc}"
        else:
            dataset_keys = list(datasets.keys())
            if len(dataset_keys) == 1:
                formatted_desc = f" exact_python_name: `{dataset_keys[0]}` Dataset: {generated_desc}"
            else:
                names_list = ", ".join([f"`{name}`" for name in dataset_keys])
                formatted_desc = f" exact_python_name: {names_list} Dataset: {generated_desc}"

        logger.log_message(f"Successfully generated dataset description for {count} dataset(s) in language {language}", level=logging.INFO)
        return formatted_desc

    except Exception as e:
        logger.log_message(f"Failed to generate dataset description: {str(e)}", level=logging.WARNING)
        raise