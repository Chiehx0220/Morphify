"""Generates the self-hosted SVG "unified card" assets used by the README:
one continuous card per app (icon+name header / repo row / Download+Obtainium
buttons), rounded only on the outer corners. This is a manual, network-heavy
script (fetches every app icon from Play Store) — like banner.py, it is NOT
run by CI. Run it by hand whenever an app is added/renamed, then commit the
generated images/cards/*.svg files; readme.py just references them from disk.
"""

import base64
import io
import re
import urllib.request
from pathlib import Path

from src.core.logger import abort, pr, wpr
from src.scripts.readme import BRAND_ICONS, PKG_NAMES, STOCK_PKG_OVERRIDE, _load_entries, _patches_url

try:
    from PIL import Image, ImageDraw
except ImportError:
    abort("This script needs Pillow, install it separately with: pip install pillow")

CARDS_DIR = Path("images/cards")

# Accent color per app. Reuses BRAND_ICONS' official brand color where one is
# already tracked there; the rest are hand-picked (no official Simple Icons
# entry exists for these).
ACCENT_OVERRIDE = {
    "Niagara-Launcher": "#00BFA5",
    "Projectivy-Launcher": "#7C4DFF",
    "KineStop": "#FF6F00",
    "Gboard": "#4285F4",
    "SketchBook": "#0696D7",
    "PictureThis": "#4CAF50",
    "Mimo": "#6C5CE7",
    "Sleep-as-Android": "#3F51B5",
    "Parallel-Space-Pro": "#2196F3",
    "AccuBattery": "#43A047",
    "Athena": "#8E44AD",
    "Proton-Pass": "#6D4AFF",
    "SD-Maid-SE": "#009688",
    "CrazyGames": "#FF6D00",
}


def _accent_for(table: str) -> str:
    if brand_icon := BRAND_ICONS.get(table):
        return f"#{brand_icon[1]}"
    return ACCENT_OVERRIDE.get(table, "#7C8CF8")


_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]+)"')

SURFACE = "#FAF6ED"
SURFACE_HIGH = "#F0E9D8"
TEXT = "#2B2620"
TEXT_MUTED = "#867E6E"
DOWNLOAD_COLOR = "#24292F"  # GitHub's own dark brand color — download always comes from GitHub Releases
OBTAINIUM_COLOR = "#7C5CBF"
FONT = "'Roboto','Segoe UI',Helvetica,Arial,sans-serif"

# 119px is the widest a card can be and still sit two-per-row without
# wrapping on the narrowest common mobile viewport (360px, tested against
# GitHub's own README <td> padding) — see images/cards width tuning notes.
W = 119
RADIUS = 10

GITHUB_PATH = "M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fetch_icon_b64(pkg: str, size: int = 160) -> str | None:
    req = urllib.request.Request(f"https://play.google.com/store/apps/details?id={pkg}", headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    m = _OG_IMAGE.search(html)
    if not m:
        return None
    icon_url = f"{m.group(1).split('=')[0]}=s{size}"
    req2 = urllib.request.Request(icon_url, headers=_HEADERS)
    with urllib.request.urlopen(req2, timeout=15) as resp2:
        data = resp2.read()
    img = Image.open(io.BytesIO(data)).convert("RGBA").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(img, (0, 0), mask)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _rounded_shapes(x: float, y: float, w: float, h: float, radius: float, rounded_corners: set[str]) -> str:
    """A native rx-rounded rect (guaranteed smooth — no hand-rolled arc
    math) plus a same-size square patch over every corner that should stay
    square, flattening it back out."""
    positions = {
        "tl": (x, y),
        "tr": (x + w - radius, y),
        "bl": (x, y + h - radius),
        "br": (x + w - radius, y + h - radius),
    }
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" ry="{radius}"/>']
    # Iterate a fixed order (not a set) — output must be reproducible so
    # re-running this script doesn't produce a spurious diff on every corner
    # combination, since Python's set iteration order isn't stable across runs.
    for c in ("tl", "tr", "bl", "br"):
        if c in rounded_corners:
            continue
        px, py = positions[c]
        parts.append(f'<rect x="{px}" y="{py}" width="{radius}" height="{radius}"/>')
    return "".join(parts)


def _header_svg(name: str, icon_b64: str, accent: str, uid: str) -> str:
    H = 38
    ICON = 26
    icon_x, icon_y = 8, (H - ICON) / 2
    text_x = icon_x + ICON + 7
    name_e = esc(name)
    shape = _rounded_shapes(0, 0, W, H, RADIUS, {"tl", "tr"})
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
<clipPath id="ic{uid}"><circle cx="{icon_x+ICON/2}" cy="{icon_y+ICON/2}" r="{ICON/2}"/></clipPath>
<radialGradient id="glow{uid}" cx="50%" cy="50%" r="50%">
<stop offset="0%" stop-color="{accent}" stop-opacity="0.18"/>
<stop offset="100%" stop-color="{accent}" stop-opacity="0"/>
</radialGradient>
<clipPath id="shape{uid}">{shape}</clipPath>
</defs>
<g clip-path="url(#shape{uid})">
<rect x="0" y="0" width="{W}" height="{H}" fill="{SURFACE}"/>
<circle cx="{icon_x+ICON/2}" cy="{icon_y+ICON/2}" r="{ICON/2+3}" fill="url(#glow{uid})"/>
<image x="{icon_x}" y="{icon_y}" width="{ICON}" height="{ICON}" href="data:image/png;base64,{icon_b64}" clip-path="url(#ic{uid})"/>
<text x="{text_x}" y="{H/2 + 4}" font-family="{FONT}" font-size="12" font-weight="700" fill="{TEXT}">{name_e}</text>
</g>
</svg>'''


def _repo_svg(repo_url: str) -> str:
    short = repo_url.split("github.com/", 1)[-1] if repo_url else ""
    owner, _, name = short.partition("/")
    H = 28
    icon_size = 9
    icon_x = 8
    icon_y = H / 2 - icon_size / 2
    scale = icon_size / 24
    text_x = icon_x + icon_size + 4
    owner_e = esc(owner)
    name_e = esc(name)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<rect x="0" y="0" width="{W}" height="{H}" fill="{SURFACE_HIGH}"/>
<g transform="translate({icon_x},{icon_y}) scale({scale})"><path d="{GITHUB_PATH}" fill="{TEXT_MUTED}"/></g>
<text x="{text_x}" y="{H/2 - 2}" font-family="{FONT}" font-size="7.5" fill="{TEXT_MUTED}">{owner_e}</text>
<text x="{text_x}" y="{H/2 + 9}" font-family="{FONT}" font-size="7.5" fill="{TEXT_MUTED}">{name_e}</text>
</svg>'''


def _text_color_for(bg_hex: str) -> str:
    bg_hex = bg_hex.lstrip("#")
    r, g, b = int(bg_hex[0:2], 16), int(bg_hex[2:4], 16), int(bg_hex[4:6], 16)
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    return "#101214" if luma > 150 else "#FFFFFF"


def _action_svg(text: str, side: str, kind: str, obtainium_b64: str | None = None) -> str:
    bw = W / 2
    h = 22
    gap = 1
    inset = gap / 2
    if side == "left":
        rect_x, rect_w = 0, bw - inset
        rounded = {"bl"}
    else:
        rect_x, rect_w = inset, bw - inset
        rounded = {"br"}
    shape = _rounded_shapes(rect_x, 0, rect_w, h, RADIUS, rounded)

    fill = DOWNLOAD_COLOR if kind == "download" else OBTAINIUM_COLOR
    fg = _text_color_for(fill)

    icon_size = 9
    font_size = 7.5
    content_w = icon_size + 3 + len(text) * font_size * 0.5
    content_x = rect_x + (rect_w - content_w) / 2
    icon_y = (h - icon_size) / 2
    text_x = content_x + icon_size + 3

    if kind == "obtainium":
        icon_el = f'<image x="{content_x}" y="{icon_y}" width="{icon_size}" height="{icon_size}" href="data:image/png;base64,{obtainium_b64}"/>'
    else:
        scale = icon_size / 24
        icon_el = f'<g transform="translate({content_x},{icon_y}) scale({scale})"><path d="{GITHUB_PATH}" fill="{fg}"/></g>'

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{bw}" height="{h}" viewBox="0 0 {bw} {h}">
<g fill="{fill}">{shape}</g>
{icon_el}
<text x="{text_x}" y="{h/2 + 2.5}" font-family="{FONT}" font-size="{font_size}" font-weight="600" fill="{fg}">{text}</text>
</svg>'''


def generate_cards() -> None:
    obtainium_req = urllib.request.Request(
        "https://raw.githubusercontent.com/ImranR98/Obtainium/main/assets/graphics/icon_small.png", headers=_HEADERS
    )
    with urllib.request.urlopen(obtainium_req, timeout=15) as resp:
        obtainium_b64 = base64.b64encode(resp.read()).decode("ascii")

    entries = sorted((e for e in _load_entries() if e.enabled), key=lambda e: e.app_name.lower())
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    kept: set[str] = set()
    written = 0
    for i, e in enumerate(entries):
        pkg = STOCK_PKG_OVERRIDE.get(e.table, PKG_NAMES.get(e.table))
        if not pkg:
            wpr(f"No package name for '{e.table}', skipping card")
            continue
        try:
            icon_b64 = _fetch_icon_b64(pkg)
            if not icon_b64:
                wpr(f"No Play Store icon found for '{e.table}' ({pkg}), skipping card")
                continue
        except Exception as exc:
            wpr(f"Failed to fetch icon for '{e.table}' ({pkg}): {exc}")
            continue

        repo_url = _patches_url(e.patches) or ""
        accent = _accent_for(e.table)
        uid = str(i)

        for suffix, svg in (
            ("header", _header_svg(e.app_name, icon_b64, accent, uid)),
            ("repo", _repo_svg(repo_url)),
            ("download", _action_svg("Download", "left", "download")),
            ("obtainium", _action_svg("Obtainium", "right", "obtainium", obtainium_b64=obtainium_b64)),
        ):
            fname = f"{e.table}-{suffix}.svg"
            (CARDS_DIR / fname).write_text(svg, encoding="utf-8")
            kept.add(fname)
            written += 1

        pr(f"Wrote card for '{e.table}'")

    for stale in CARDS_DIR.iterdir():
        if stale.name not in kept:
            stale.unlink()

    pr(f"Wrote {written} card files ({len(kept)//4} apps) to {CARDS_DIR}")


if __name__ == "__main__":
    generate_cards()
