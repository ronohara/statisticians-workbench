// frontend/lib/rtl.ts
// ============================================================
// RTL LANGUAGE CODES
// Languages whose document direction is right-to-left.
//
// This is the complete curated set of ISO 639-1 right-to-left
// language codes. Codes without shipped translations have no
// effect — a language can only become active once its
// translations exist in the database — so listing them all means
// shipping a new RTL language never requires a code change here.
//
//   ar  Arabic          dv  Divehi (Thaana script)
//   fa  Farsi/Persian   he  Hebrew
//   ku  Kurdish         ps  Pashto
//   sd  Sindhi          ug  Uyghur
//   ur  Urdu            yi  Yiddish
// ============================================================

export const RTL_LANGS = [
    "ar", "dv", "fa", "he", "ku", "ps", "sd", "ug", "ur", "yi",
];
