import base64
import io
import json
import re
import urllib.request
from pathlib import Path

from src.core.logger import abort, pr, wpr
from src.scripts.readme import PKG_NAMES, _load_entries

try:
    from PIL import Image, ImageDraw
except ImportError:
    abort("This script needs Pillow, install it separately with: pip install pillow")

BANNER_PATH = Path("images/apps-marquee.svg")
ICONS_DIR = Path("images/icons")
MANIFEST_PATH = ICONS_DIR / "manifest.json"

# Play Store package for apps whose PKG_NAMES holds a renamed/patched id
# instead of the stock one (renamed apps aren't listed on the Play Store).
STOCK_PKG_OVERRIDE = {
    "Google-Photos": "com.google.android.apps.photos",
    "Gboard": "com.google.android.inputmethod.latin",
    "Messenger": "com.facebook.orca",
}

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]+)"')

_SIZE = 56
_GAP = 24
_STEP = _SIZE + _GAP
_ROW_H = 84


def _fetch_icon(pkg: str) -> bytes | None:
    url = f"https://play.google.com/store/apps/details?id={pkg}"
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    m = _OG_IMAGE.search(html)
    if not m:
        return None

    icon_url = f"{m.group(1).split('=')[0]}=s128"
    req2 = urllib.request.Request(icon_url, headers=_HEADERS)
    with urllib.request.urlopen(req2, timeout=15) as resp2:
        return resp2.read()


def _circle_crop(data: bytes, size: int = 128) -> Image.Image:
    img = Image.open(io.BytesIO(data)).convert("RGBA").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(img, (0, 0), mask)
    return out


def _collect_icons() -> list[tuple[str, str, str, Image.Image]]:
    """Returns (table, app_name, playstore_url, circle_cropped_image) for each app whose icon was fetched."""
    entries = sorted((e for e in _load_entries() if e.enabled), key=lambda e: e.app_name.lower())
    icons: list[tuple[str, str, str, Image.Image]] = []
    for e in entries:
        pkg = STOCK_PKG_OVERRIDE.get(e.table, PKG_NAMES.get(e.table))
        if not pkg:
            wpr(f"No package name for '{e.table}', skipping icon")
            continue
        try:
            if data := _fetch_icon(pkg):
                url = f"https://play.google.com/store/apps/details?id={pkg}"
                icons.append((e.table, e.app_name, url, _circle_crop(data)))
            else:
                wpr(f"No Play Store icon found for '{e.table}' ({pkg}), skipping icon")
        except Exception as exc:
            wpr(f"Failed to fetch icon for '{e.table}' ({pkg}): {exc}")
    return icons


def _write_icon_files(icons: list[tuple[str, str, str, Image.Image]]) -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    kept = {"manifest.json"}
    for table, _, url, img in icons:
        path = ICONS_DIR / f"{table}.png"
        img.save(path)
        kept.add(path.name)
        manifest[table] = url
    for stale in ICONS_DIR.iterdir():
        if stale.name not in kept:
            stale.unlink()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def _image_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


def _build_row(items: list[tuple[str, str]], direction: str) -> tuple[str, int]:
    seq = items + items
    total_w = _STEP * len(items)
    g_items = []
    for i, (name, uri) in enumerate(seq):
        x = i * _STEP
        g_items.append(
            f'<g transform="translate({x},0)">'
            f'<image href="{uri}" x="0" y="0" width="{_SIZE}" height="{_SIZE}"/>'
            f"<title>{name}</title></g>"
        )
    return f'<g class="row row-{direction}">' + "".join(g_items) + "</g>", total_w


def _build_svg(icons: list[tuple[str, str, str, Image.Image]]) -> str:
    pairs = [(name, _image_data_uri(img)) for _, name, _, img in icons]
    half = len(pairs) // 2 + 1
    row1, row2 = pairs[:half], pairs[half:] or pairs[:1]
    canvas_w, canvas_h = 900, _ROW_H * 2
    row1_svg, row1_w = _build_row(row1, "left")
    row2_svg, row2_w = _build_row(row2, "right")

    # CSS @keyframes, not SMIL <animateTransform> — SMIL animation support is
    # inconsistent for SVGs loaded via <img>, CSS animation is reliable there.
    style = (
        "<style>"
        f"@keyframes scrollLeft{{from{{transform:translate(0px,4px)}}to{{transform:translate(-{row1_w}px,4px)}}}}"
        f"@keyframes scrollRight{{from{{transform:translate(-{row2_w}px,{_ROW_H + 4}px)}}to{{transform:translate(0px,{_ROW_H + 4}px)}}}}"
        ".row-left{animation:scrollLeft 26s linear infinite}"
        ".row-right{animation:scrollRight 32s linear infinite}"
        "</style>"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {canvas_h}" width="100%" height="{canvas_h}">\n'
        f"{style}\n"
        f'<defs><clipPath id="clip"><rect x="0" y="0" width="{canvas_w}" height="{canvas_h}" rx="12"/></clipPath></defs>\n'
        f'<g clip-path="url(#clip)">\n'
        f"{row1_svg}\n"
        f"{row2_svg}\n"
        f"</g>\n</svg>\n"
    )


def generate_banner() -> None:
    icons = _collect_icons()
    if not icons:
        wpr("No icons fetched, nothing written")
        return
    BANNER_PATH.write_text(_build_svg(icons), encoding="utf-8")
    pr(f"Wrote {BANNER_PATH} with {len(icons)} icons")
    _write_icon_files(icons)
    pr(f"Wrote {len(icons)} icon files + manifest to {ICONS_DIR}")


if __name__ == "__main__":
    generate_banner()
