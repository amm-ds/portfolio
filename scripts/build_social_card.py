"""Compose the 1200x630 social card: dimmed zone-demand map backdrop + mono text overlay.

Two modes:

- default: the site card ("$ amm-ds" / "ML/AI Engineering Portfolio" / subtitle).
- ``--story PROJECT_ID``: a per-project card whose body is the story's
  ``short_version`` (the single plain-text source baked by
  scripts/gen_story_short.py) under the project's manifest title, with a
  first-person subtitle by default (override with ``--subtitle``).

Examples:

    uv run python scripts/build_social_card.py
    uv run python scripts/build_social_card.py --story 07-open-data-mobility
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from portfolio_core.manifest import load_project
from portfolio_core.story import load_story

W, H = 1200, 630
BG = (15, 23, 42)  # #0f172a site background
ACCENT = (45, 212, 191)  # #2dd4bf teal
SECONDARY = (56, 189, 248)  # #38bdf8 cyan
TEXT = (226, 232, 240)  # #e2e8f0
MUTED = (148, 163, 184)  # #94a3b8

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/assets/projects/07-open-data-mobility/zone_demand_map.png"
OUT_WEB = ROOT / "apps/showcase-web/public/social-card.png"
OUT_DOCS = ROOT / "docs/assets/social-card.png"

FONT = "/System/Library/Fonts/Menlo.ttc"

TEXT_X = 80
TEXT_WIDTH = W - 2 * TEXT_X
SUBTITLE_Y = 505

# First-person positioning line — the default subtitle everywhere on the card.
DEFAULT_SUBTITLE = "I build reproducible ML/AI systems — measured results, published code."


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    # Menlo.ttc: index 0 = regular, 1 = bold
    return ImageFont.truetype(FONT, size, index=1 if bold else 0)


def backdrop() -> Image.Image:
    """Cover-crop the map, dim it toward the site bg, scrim the text zone."""
    map_img = Image.open(SRC).convert("RGB")
    scale = max(W / map_img.width, H / map_img.height)
    map_img = map_img.resize(
        (round(map_img.width * scale), round(map_img.height * scale)),
        Image.LANCZOS,
    )
    left = (map_img.width - W) // 2
    top = (map_img.height - H) // 2
    map_img = map_img.crop((left, top, left + W, top + H))
    map_img = ImageEnhance.Brightness(map_img).enhance(0.45)
    map_img = ImageEnhance.Color(map_img).enhance(0.8)

    card = Image.new("RGB", (W, H), BG)
    card.paste(map_img, (0, 0))

    # Dark scrim, heavier at the bottom-left where text sits.
    scrim = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(scrim)
    d.rectangle((0, 0, W, H), fill=140)
    d.rectangle((0, int(H * 0.25), W, H), fill=190)
    scrim = scrim.filter(ImageFilter.GaussianBlur(120))
    return Image.composite(Image.new("RGB", (W, H), BG), card, scrim)


def frame(draw: ImageDraw.ImageDraw) -> None:
    """Accent frame details shared by both modes."""
    draw.rectangle((0, 0, W, 6), fill=ACCENT)  # top teal rule
    draw.rectangle((80, 478, 200, 482), fill=SECONDARY)  # small cyan tick above subtitle


def shrink_to_fit(
    draw: ImageDraw.ImageDraw,
    text: str,
    start_size: int,
    min_size: int,
    bold: bool = False,
) -> ImageFont.FreeTypeFont:
    """Largest font (>= min_size) whose single line fits the text column."""
    size = start_size
    while size > min_size:
        f = font(size, bold=bold)
        if draw.textlength(text, font=f) <= TEXT_WIDTH:
            return f
        size -= 1
    return font(min_size, bold=bold)


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont) -> list[str]:
    """Greedy word-wrap at the text column width."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=f) <= TEXT_WIDTH:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines


def draw_subtitle(draw: ImageDraw.ImageDraw, subtitle: str) -> None:
    """Subtitle line above the bottom edge — shrink to fit the text column."""
    f_sub = shrink_to_fit(draw, subtitle, start_size=30, min_size=12)
    draw.text((TEXT_X, SUBTITLE_Y), subtitle, font=f_sub, fill=MUTED)


def build_default_card(subtitle: str) -> Image.Image:
    """The site card: prompt + two-line title + subtitle."""
    card = backdrop()
    draw = ImageDraw.Draw(card)
    frame(draw)

    draw.text((TEXT_X, 140), "$ amm-ds", font=font(40, bold=True), fill=ACCENT)

    f_title = font(72, bold=True)
    draw.text((TEXT_X, 205), "ML/AI Engineering", font=f_title, fill=TEXT)
    draw.text((TEXT_X, 295), "Portfolio", font=f_title, fill=TEXT)

    draw_subtitle(draw, subtitle)
    return card


def build_story_card(project_id: str, subtitle: str) -> Image.Image:
    """A per-project card: title + the story's short_version body + subtitle."""
    story = load_story(ROOT / "projects" / project_id)
    if story is None or not story.short_version:
        raise SystemExit(f"build_social_card: no story/short_version for {project_id}")
    info = load_project(ROOT / "projects" / project_id)
    title = info.title if info is not None else project_id

    card = backdrop()
    draw = ImageDraw.Draw(card)
    frame(draw)

    draw.text((TEXT_X, 110), "$ amm-ds", font=font(34, bold=True), fill=ACCENT)

    f_title = shrink_to_fit(draw, title, start_size=64, min_size=36, bold=True)
    draw.text((TEXT_X, 165), title, font=f_title, fill=TEXT)

    # Body: the story short_version, wrapped — largest size that fits the band
    # between the title block and the subtitle tick.
    body_top = 250
    body_bottom = 468
    f_body = font(16)
    for size in range(30, 15, -1):
        f_body = font(size)
        lines = wrap_lines(draw, story.short_version, f_body)
        line_h = f_body.size + 8
        if len(lines) * line_h <= body_bottom - body_top:
            break
    y = body_top
    for line in lines:
        draw.text((TEXT_X, y), line, font=f_body, fill=TEXT)
        y += line_h

    draw_subtitle(draw, subtitle)
    return card


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--story",
        metavar="PROJECT_ID",
        help="render a per-project card from the story's short_version",
    )
    parser.add_argument(
        "--subtitle",
        help="subtitle line (default: the first-person positioning line)",
    )
    args = parser.parse_args()

    subtitle = args.subtitle or DEFAULT_SUBTITLE
    card = build_story_card(args.story, subtitle) if args.story else build_default_card(subtitle)
    card.save(OUT_WEB)
    card.save(OUT_DOCS)
    mode = f"story:{args.story}" if args.story else "site"
    print(f"wrote {OUT_WEB} and {OUT_DOCS} ({card.size[0]}x{card.size[1]}, mode {mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
