def clean_text(text: str) -> str:
    paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n\n".join(paragraphs)


def make_title(text: str, max_length: int = 70) -> str:
    cleaned_text = clean_text(text)
    if not cleaned_text:
        return "Audio fara titlu"

    first_line = cleaned_text.splitlines()[0]
    if len(first_line) <= max_length:
        return first_line

    return f"{first_line[: max_length - 3].rstrip()}..."
