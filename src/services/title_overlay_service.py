from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont

from src.config import (
    TITLE_OVERLAY_DIR,
    VIDEO_HEIGHT,
    VIDEO_TITLE_FONT_PATH,
    VIDEO_TITLE_FONT_SIZE,
    VIDEO_TITLE_MAX_LINES,
    VIDEO_TITLE_MAX_TEXT_WIDTH,
    VIDEO_TITLE_MIN_FONT_SIZE,
    VIDEO_WIDTH,
)
from src.services.storage import safe_unlink


class TitleOverlayError(RuntimeError):
    pass


def _measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def _wrap_title(
    title: str,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    words = title.upper().split()
    if not words:
        return ["VIDEO FARA TITLU"]

    lines: list[str] = []
    current_line = ""
    for word in words:
        while _measure_text(draw, word, font) > max_width:
            if current_line:
                lines.append(current_line)
                current_line = ""
            split_at = 1
            while (
                split_at < len(word)
                and _measure_text(draw, word[: split_at + 1], font) <= max_width
            ):
                split_at += 1
            lines.append(word[:split_at])
            word = word[split_at:]
        candidate = f"{current_line} {word}".strip()
        if _measure_text(draw, candidate, font) <= max_width:
            current_line = candidate
            continue

        if current_line:
            lines.append(current_line)
            current_line = word
        else:
            lines.append(word)

    if current_line:
        lines.append(current_line)
    return lines


@lru_cache(maxsize=1)
def resolve_font() -> str:
    candidates = (
        [VIDEO_TITLE_FONT_PATH]
        if VIDEO_TITLE_FONT_PATH
        else [
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "DejaVuSans-Bold.ttf",
        ]
    )
    for candidate in candidates:
        try:
            font = ImageFont.truetype(candidate, VIDEO_TITLE_FONT_SIZE)
            return str(font.path)
        except OSError:
            continue
    raise TitleOverlayError(
        "Instalează DejaVu Sans sau setează VIDEO_TITLE_FONT_PATH la un font cu diacritice și chirilice."
    )


def _load_font(font_size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(resolve_font(), font_size)


def _make_title_layout(title: str) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    measurement_image = Image.new("RGBA", (1, 1))
    measurement_draw = ImageDraw.Draw(measurement_image)
    for font_size in range(VIDEO_TITLE_FONT_SIZE, VIDEO_TITLE_MIN_FONT_SIZE - 1, -2):
        font = _load_font(font_size)
        lines = _wrap_title(title, measurement_draw, font, VIDEO_TITLE_MAX_TEXT_WIDTH)
        if len(lines) <= VIDEO_TITLE_MAX_LINES and all(
            _measure_text(measurement_draw, line, font) <= VIDEO_TITLE_MAX_TEXT_WIDTH
            for line in lines
        ):
            return font, lines

    raise TitleOverlayError("Titlul nu încape în cadru. Scurtează titlul.")


def create_title_overlay(title: str) -> Path:
    font, lines = _make_title_layout(title)
    measurement_image = Image.new("RGBA", (1, 1))
    measurement_draw = ImageDraw.Draw(measurement_image)
    ascent, descent = font.getmetrics()
    line_height = ascent + descent
    line_spacing = 14
    text_width = max(_measure_text(measurement_draw, line, font) for line in lines)
    text_height = line_height * len(lines) + line_spacing * (len(lines) - 1)

    border = 22
    padding_x = 58
    padding_y = 42
    image_width = text_width + (padding_x + border) * 2
    image_height = text_height + (padding_y + border) * 2
    if image_width > VIDEO_WIDTH - 80 or image_height > VIDEO_HEIGHT - 160:
        raise TitleOverlayError("Titlul nu încape în cadrul vertical.")
    image = Image.new("RGBA", (image_width, image_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    cyan = (0, 223, 238, 255)
    red = (255, 24, 79, 255)
    black = (0, 0, 0, 255)
    draw.rectangle((0, 0, image_width - 45, border), fill=cyan)
    draw.rectangle((0, 0, border, image_height - 45), fill=cyan)
    draw.rectangle((45, image_height - border, image_width, image_height), fill=red)
    draw.rectangle((image_width - border, 45, image_width, image_height), fill=red)
    draw.rectangle((border, border, image_width - border, image_height - border), fill=black)

    text_y = border + padding_y
    for line in lines:
        text_width = _measure_text(draw, line, font)
        draw.text(
            ((image_width - text_width) // 2, text_y),
            line,
            fill=(255, 255, 255, 255),
            font=font,
        )
        text_y += line_height + line_spacing

    TITLE_OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TITLE_OVERLAY_DIR / f"title-{uuid4().hex}.png"
    try:
        image.save(output_path, "PNG")
    except BaseException:
        safe_unlink(output_path)
        raise
    return output_path
