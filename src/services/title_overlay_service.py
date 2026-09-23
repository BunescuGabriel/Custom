from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont

from src.config import (
    TITLE_OVERLAY_DIR,
    VIDEO_TITLE_FONT_PATH,
    VIDEO_TITLE_FONT_SIZE,
    VIDEO_TITLE_MAX_LINES,
    VIDEO_TITLE_MAX_TEXT_WIDTH,
    VIDEO_TITLE_MIN_FONT_SIZE,
)


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


def _load_font(font_size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(VIDEO_TITLE_FONT_PATH), font_size)
    except OSError as error:
        raise TitleOverlayError(
            f"Fontul pentru titlu nu este disponibil: {VIDEO_TITLE_FONT_PATH}"
        ) from error


def _make_title_layout(title: str) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    measurement_image = Image.new("RGBA", (1, 1))
    measurement_draw = ImageDraw.Draw(measurement_image)
    for font_size in range(VIDEO_TITLE_FONT_SIZE, VIDEO_TITLE_MIN_FONT_SIZE - 1, -2):
        font = _load_font(font_size)
        lines = _wrap_title(title, measurement_draw, font, VIDEO_TITLE_MAX_TEXT_WIDTH)
        if len(lines) <= VIDEO_TITLE_MAX_LINES:
            return font, lines

    font = _load_font(VIDEO_TITLE_MIN_FONT_SIZE)
    lines = _wrap_title(title, measurement_draw, font, VIDEO_TITLE_MAX_TEXT_WIDTH)
    return font, lines


def create_title_overlay(title: str) -> Path:
    font, lines = _make_title_layout(title)
    measurement_image = Image.new("RGBA", (1, 1))
    measurement_draw = ImageDraw.Draw(measurement_image)
    line_height = font.getbbox("Ag")[3] - font.getbbox("Ag")[1]
    line_spacing = 14
    text_width = max(_measure_text(measurement_draw, line, font) for line in lines)
    text_height = line_height * len(lines) + line_spacing * (len(lines) - 1)

    border = 22
    padding_x = 58
    padding_y = 42
    image_width = text_width + (padding_x + border) * 2
    image_height = text_height + (padding_y + border) * 2
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
    image.save(output_path, "PNG")
    return output_path
