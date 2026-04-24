from typing import Literal


LanguageCode = Literal["en", "ru"]


def normalize_language(value: str | None, *, default: LanguageCode = "en") -> LanguageCode:
    if value and value.lower() in {"ru", "russian", "русский"}:
        return "ru"
    if value and value.lower() in {"en", "english"}:
        return "en"
    return default


def detect_language(*texts: str | None, fallback: LanguageCode = "en") -> LanguageCode:
    combined = " ".join(text or "" for text in texts)
    letters = [character for character in combined if character.isalpha()]
    if not letters:
        return fallback
    cyrillic_count = sum("а" <= character.lower() <= "я" or character.lower() == "ё" for character in letters)
    if cyrillic_count / max(len(letters), 1) >= 0.2:
        return "ru"
    return "en"


def has_any(text: str, signals: tuple[str, ...]) -> bool:
    haystack = text.lower()
    return any(signal in haystack for signal in signals)
