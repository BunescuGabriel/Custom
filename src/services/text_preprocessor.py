import re
import unicodedata


def clean_text(text: str) -> str:
    paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n\n".join(paragraphs)


def make_title(text: str, max_length: int = 140) -> str:
    cleaned_text = clean_text(text)
    if not cleaned_text:
        return "Audio fara titlu"

    first_line = cleaned_text.splitlines()[0]
    if len(first_line) <= max_length:
        return first_line

    return f"{first_line[: max_length - 3].rstrip()}..."


def make_file_stem(title: str, max_length: int = 80) -> str:
    normalized_title = unicodedata.normalize("NFKD", title)
    without_diacritics = "".join(
        character for character in normalized_title if not unicodedata.combining(character)
    )
    safe_title = re.sub(r"[^\w]+", "-", without_diacritics.casefold(), flags=re.UNICODE)
    safe_title = safe_title.strip(".-_")[:max_length].rstrip(".-_")
    if not safe_title:
        safe_title = "generare-audio"

    return safe_title
