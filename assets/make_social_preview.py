"""Generate the GitHub social-preview image for mnemos.

Run once (or whenever the hero treatment changes):

    python assets/make_social_preview.py

Output: ``assets/social-preview.png`` (1280x640, PNG).

Upload it via *Settings → Social preview → Edit* on the repo page.

The script uses Pillow only (installed as a dev extra) and system-available
fonts with graceful fallbacks, so it runs on Windows, macOS, and Linux
without extra setup.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


W, H = 1280, 640

# Palette — deep indigo → violet gradient, warm cream text. Riffs on
# the "memory palace" / Obsidian association without copying their brand.
BG_TOP = (22, 18, 40)         # near-black indigo
BG_BOTTOM = (48, 31, 78)      # deep violet
ACCENT = (190, 150, 255)      # soft lavender for the rule + hairline
TEXT = (245, 238, 220)        # warm cream
MUTED = (175, 168, 195)       # desaturated lavender for supporting text
URL = (140, 125, 175)         # slightly dimmer for the URL at the bottom


def _vertical_gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, top)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return img


def _load_font(candidates: Iterable[str], size: int) -> ImageFont.ImageFont:
    """Try several font files, fall back to Pillow's default if none work."""
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    # Pillow 10+ removed textsize(); use textbbox which is stable.
    left, _top, right, _bottom = draw.textbbox((0, 0), text, font=font)
    return right - left


def _draw_palace_motif(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int) -> None:
    """Five stylized 'wings' — thin vertical bars suggesting a memory palace floor plan."""
    bar_w = 10
    gap = (w - 5 * bar_w) // 4
    for i in range(5):
        bx = x + i * (bar_w + gap)
        # Each bar tapers from taller at the center to shorter at the edges for rhythm.
        dist = abs(i - 2)
        bh = int(h * (1.0 - 0.12 * dist))
        by = y + (h - bh) // 2
        draw.rectangle([bx, by, bx + bar_w, by + bh], fill=ACCENT)


def render(out_path: Path) -> None:
    img = _vertical_gradient((W, H), BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(img)

    # Subtle top rule and a matching bottom hairline — frames the composition.
    draw.rectangle([64, 54, W - 64, 56], fill=ACCENT)
    draw.rectangle([64, H - 56, W - 64, H - 54], fill=(90, 72, 140))

    # Fonts — prefer a serif for the title (memory palace vibe), sans for body.
    title_font = _load_font(
        [
            "C:/Windows/Fonts/georgiab.ttf",
            "C:/Windows/Fonts/georgia.ttf",
            "/Library/Fonts/Georgia.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        ],
        168,
    )
    tagline_font = _load_font(
        [
            "C:/Windows/Fonts/segoeui.ttf",
            "/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ],
        36,
    )
    small_font = _load_font(
        [
            "C:/Windows/Fonts/segoeui.ttf",
            "/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ],
        26,
    )

    # Title — centered horizontally, with a soft shadow for depth.
    title = "Mnemos"
    tw = _text_w(draw, title, title_font)
    tx = (W - tw) // 2
    ty = 140
    draw.text((tx + 2, ty + 3), title, fill=(0, 0, 0), font=title_font)
    draw.text((tx, ty), title, fill=TEXT, font=title_font)

    # Tagline — two lines, centered.
    line1 = "Turn your Claude Code history"
    line2 = "into a searchable memory palace."
    lw1 = _text_w(draw, line1, tagline_font)
    lw2 = _text_w(draw, line2, tagline_font)
    ly = 345
    draw.text(((W - lw1) // 2, ly), line1, fill=TEXT, font=tagline_font)
    draw.text(((W - lw2) // 2, ly + 52), line2, fill=TEXT, font=tagline_font)

    # Decorative palace motif under the tagline.
    motif_w, motif_h = 260, 30
    _draw_palace_motif(draw, (W - motif_w) // 2, 480, motif_w, motif_h)

    # Feature strip and URL at the bottom.
    features = "Obsidian-native  ·  Markdown-first  ·  MCP-ready"
    fw = _text_w(draw, features, small_font)
    draw.text(((W - fw) // 2, 538), features, fill=MUTED, font=small_font)

    url = "github.com/mnemos-dev/mnemos"
    uw = _text_w(draw, url, small_font)
    draw.text(((W - uw) // 2, 580), url, fill=URL, font=small_font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    print(f"wrote {out_path} ({W}x{H})")


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    render(here / "social-preview.png")
