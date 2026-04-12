"""
Source-language detection + translation-risk mitigation.

Why this exists:
  PowerTrust's regulatory research spans 18-20 countries, many of which
  publish primary sources in Spanish (MX, CL, CO), Portuguese (BR),
  Bahasa Indonesia (ID), Vietnamese (VN), and other non-English languages.
  Relying on an LLM to silently translate legal Spanish/Portuguese into
  English summaries without flagging the translation hop risks numeric
  or legal-nuance errors (e.g., "fase de consulta" vs "fase de aprobación"
  mean very different things for permitting timelines).

What this does:
  1. Heuristically infers the source language from the URL/organization of
     each source. No external API call, no model inference — pure domain
     mapping so it is free, deterministic, and offline-safe.
  2. Surfaces a translation caveat for non-English sources into the RAG
     context block so the LLM is required to note the translation hop
     when citing.
  3. Exposes a badge label the dashboard can display next to source cards.
"""
from __future__ import annotations


# URL fragment or org-name fragment -> ISO 639-1 code.
# Ordered most-specific-first; first match wins.
_URL_LANG_HINTS: tuple[tuple[str, str], ...] = (
    # Portuguese (Brazil)
    ("planalto.gov.br", "pt"),
    ("gov.br/aneel", "pt"),
    ("gov.br/mme", "pt"),
    ("gov.br", "pt"),
    (".br/", "pt"),
    # Spanish — Mexico
    ("gob.mx", "es"),
    ("cenace.gob.mx", "es"),
    # Spanish — Chile
    ("bcn.cl", "es"),
    ("cne.cl", "es"),
    ("coordinador.cl", "es"),
    ("sea.gob.cl", "es"),
    ("sec.cl", "es"),
    ("energia.gob.cl", "es"),
    (".cl/", "es"),
    # Spanish — Colombia
    ("creg.gov.co", "es"),
    ("upme.gov.co", "es"),
    ("xm.com.co", "es"),
    ("anla.gov.co", "es"),
    ("isa.co", "es"),
    ("funcionpublica.gov.co", "es"),
    ("minenergia.gov.co", "es"),
    ("dnp.gov.co", "es"),
    (".gov.co", "es"),
    # Bahasa Indonesia
    ("esdm.go.id", "id"),
    ("jdih.esdm.go.id", "id"),
    ("pln.co.id", "id"),
    (".go.id", "id"),
    # Vietnamese
    ("moit.gov.vn", "vi"),
    ("evn.com.vn", "vi"),
    ("dautunuocngoai.gov.vn", "vi"),
    # English-with-Bahasa elements (Malaysia official portals are bilingual)
    ("st.gov.my", "en"),  # Energy Commission: bilingual EN/MS, EN primary
    ("tnb.com.my", "en"),
    ("seda.gov.my", "en"),
    # English (explicitly)
    (".gov.za", "en"),
    ("nersa.org.za", "en"),
    ("nerc.gov.ng", "en"),
    ("rea.gov.ng", "en"),
    ("cbn.gov.ng", "en"),
    ("epra.go.ke", "en"),
    ("kplc.co.ke", "en"),
    ("energy.go.ke", "en"),
    ("kenyalaw.org", "en"),
    ("nema.go.ke", "en"),
    ("ketraco.co.ke", "en"),
    ("en.evn.com.vn", "en"),
    ("moit.gov.vn/en", "en"),
    ("esdm.go.id/en", "en"),
)


_LANG_NAMES: dict[str, str] = {
    "en": "English",
    "pt": "Portuguese",
    "es": "Spanish",
    "id": "Bahasa Indonesia",
    "vi": "Vietnamese",
    "ms": "Bahasa Malaysia",
}


_ORG_LANG_HINTS: tuple[tuple[str, str], ...] = (
    ("aneel", "pt"),
    ("planalto", "pt"),
    ("presidencia da república", "pt"),
    ("presidencia da republica", "pt"),
    ("cenace", "es"),
    ("cre (", "es"),
    ("sener", "es"),
    ("creg", "es"),
    ("upme", "es"),
    ("coordinador", "es"),
    ("memr", "en"),  # official English portal
    ("esdm", "id"),
    ("moit", "en"),  # official English portal
    ("evn english", "en"),
    ("mpi vietnam", "en"),
)


def detect_language(url: str, organization: str = "") -> str:
    """Best-effort language detection. Returns ISO 639-1 code, default 'en'."""
    u = (url or "").lower()
    for hint, lang in _URL_LANG_HINTS:
        if hint in u:
            return lang
    o = (organization or "").lower()
    for hint, lang in _ORG_LANG_HINTS:
        if hint in o:
            return lang
    return "en"


def language_name(code: str) -> str:
    """Human-readable language name from ISO code."""
    return _LANG_NAMES.get((code or "").lower(), code.upper() if code else "Unknown")


def needs_caveat(code: str) -> bool:
    """True if a translation hop should be disclosed to the end user."""
    return (code or "en").lower() != "en"


def badge(code: str) -> str:
    """Short label for UI display next to a source card."""
    c = (code or "en").lower()
    return "EN" if c == "en" else c.upper()


def detect_languages_from_sources_str(sources_str: str) -> list[str]:
    """Parse the flat 'sources' metadata string (as produced by RAGEngine)
    and return the set of distinct ISO codes present, sorted by ISO code.

    The flat string is produced by src.rag_engine._flatten_metadata as:
        "{org}: {doc} ({accessed}) <{url}> | {org2}: ...".
    """
    if not sources_str:
        return []
    pieces = [p.strip() for p in sources_str.split("|") if p.strip()]
    langs: set[str] = set()
    for p in pieces:
        url = ""
        org = ""
        # Extract URL between the angle brackets
        lt = p.rfind("<")
        gt = p.rfind(">")
        if lt >= 0 and gt > lt:
            url = p[lt + 1:gt]
        # Extract org (everything before the first ': ')
        colon = p.find(": ")
        if colon > 0:
            org = p[:colon]
        langs.add(detect_language(url, org))
    return sorted(langs)


def caveat_for_languages(codes: list[str]) -> str:
    """Return a one-line caveat note for non-English codes, or '' if none."""
    non_en = [c for c in codes if needs_caveat(c)]
    if not non_en:
        return ""
    names = ", ".join(language_name(c) for c in non_en)
    return f"(Source language: {names} — verify quoted numbers against the original document.)"
