"""Compose the 1200x630 social card: dimmed zone-demand map backdrop + mono text overlay."""

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

W, H = 1200, 630
BG = (15, 23, 42)  # #0f172a site background
ACCENT = (45, 212, 191)  # #2dd4bf teal
SECONDARY = (56, 189, 248)  # #38bdf8 cyan
TEXT = (226, 232, 240)  # #e2e8f0
MUTED = (148, 163, 184)  # #94a3b8

SRC = "docs/assets/projects/07-open-data-mobility/zone_demand_map.png"
OUT_WEB = "apps/showcase-web/public/social-card.png"
OUT_DOCS = "docs/assets/social-card.png"

FONT = "/System/Library/Fonts/Menlo.ttc"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    # Menlo.ttc: index 0 = regular, 1 = bold
    return ImageFont.truetype(FONT, size, index=1 if bold else 0)


# --- Backdrop: cover-crop the map, dim it toward the site bg -----------------
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
scrim = scrim.filter(__import__("PIL.ImageFilter", fromlist=["GaussianBlur"]).GaussianBlur(120))
card = Image.composite(Image.new("RGB", (W, H), BG), card, scrim)

draw = ImageDraw.Draw(card)

# --- Accent frame details ----------------------------------------------------
draw.rectangle((0, 0, W, 6), fill=ACCENT)  # top teal rule
draw.rectangle((80, 478, 200, 482), fill=SECONDARY)  # small cyan tick above subtitle

# --- Text overlay ------------------------------------------------------------
x = 80

# Prompt line: "$ amm-ds" in teal
f_prompt = font(40, bold=True)
draw.text((x, 140), "$ amm-ds", font=f_prompt, fill=ACCENT)

# Main title (two lines, bold)
f_title = font(72, bold=True)
draw.text((x, 205), "ML/AI Engineering", font=f_title, fill=TEXT)
draw.text((x, 295), "Portfolio", font=f_title, fill=TEXT)

# Subtitle — shrink to fit the 1040px text column
sub = "10 reproducible case studies · serving endpoints · measured results"
sub_size = 30
while sub_size > 12:
    f_sub = font(sub_size)
    if draw.textlength(sub, font=f_sub) <= W - 2 * x:
        break
    sub_size -= 1
draw.text((x, 505), sub, font=f_sub, fill=MUTED)

card.save(OUT_WEB)
card.save(OUT_DOCS)
print(f"wrote {OUT_WEB} and {OUT_DOCS} ({card.size[0]}x{card.size[1]})")
