import json
import sys
from pathlib import Path
from urllib.parse import quote

from src.core.config import CONFIG_PATH, load_toml, parse_app_entries, parse_config
from src.core.logger import abort

README_PATH = Path("README.md")
START = "<!-- APPS_TABLE_START -->"
END = "<!-- APPS_TABLE_END -->"
REPO_URL = "https://github.com/Chiehx0220/builder-for-morphe"
REPO_AUTHOR = "Chiehx0220"

# Android package IDs aren't stored in config.toml (the build system discovers
# them at build time), so this table is maintained by hand for the Obtainium links.
# Use the INSTALLED (post-patch) package ID, not the stock one — some patch
# sources rename the package (e.g. Gboard's "Package Rename" patch) so the
# patched app can be installed alongside the original.
PKG_NAMES = {
    "YouTube": "com.google.android.youtube",
    "YT-Music": "com.google.android.apps.youtube.music",
    "Reddit": "com.reddit.frontpage",
    "X-Twitter": "com.twitter.android",
    "Instagram": "com.instagram.android",
    "Niagara-Launcher": "bitpit.launcher",
    "Proton-Mail_rushi": "ch.protonmail.android",
    "Projectivy-Launcher": "com.spocky.projengmenu",
    "KineStop": "com.urbandroid.kinestop",
    "Facebook": "com.facebook.katana",
    "Gboard": "dev.jason.com.google.android.inputmethod.latin",
    "LINE": "jp.naver.line.android",
    "Google-Photos": "app.morphe.android.apps.photos",
    "Duolingo": "com.duolingo",
    "TikTok_icysymmetra": "com.zhiliaoapp.musically",
    "Messenger": "app.morphe.messenger.orca",
    "Twitch": "tv.twitch.android.app",
    "IMDb": "com.imdb.mobile",
    "SketchBook": "com.adsk.sketchbook",
    "AccuWeather": "com.accuweather.android",
    "PictureThis": "cn.danatech.xingseus",
}

# Fallback icon for the README table's icon column, when an app has no
# real brand icon on Simple Icons (see BRAND_ICONS below).
CATEGORIES = {
    "YouTube": "🎥",
    "YT-Music": "🎵",
    "Reddit": "🗨️",
    "X-Twitter": "🐦",
    "Instagram": "📸",
    "Facebook": "📘",
    "LINE": "💬",
    "Gboard": "⌨️",
    "Proton-Mail_rushi": "📧",
    "Niagara-Launcher": "🚀",
    "Projectivy-Launcher": "🚀",
    "KineStop": "🏃",
    "Google-Photos": "📷",
    "Duolingo": "🦉",
    "TikTok_icysymmetra": "🎶",
    "Messenger": "📩",
    "Twitch": "🎮",
    "IMDb": "🎬",
    "SketchBook": "🎨",
    "AccuWeather": "🌦️",
    "PictureThis": "🌿",
}

# Real per-app brand icon (Simple Icons slug) + official brand color, used for
# the icon column and the Download badge. Apps without a Simple Icons entry
# fall back to CATEGORIES / a generic grey badge.
BRAND_ICONS = {
    "YouTube": ("youtube", "FF0000"),
    "YT-Music": ("youtubemusic", "FF0000"),
    "Reddit": ("reddit", "FF4500"),
    "X-Twitter": ("x", "000000"),
    "Instagram": ("instagram", "E4405F"),
    "Facebook": ("facebook", "1877F2"),
    "LINE": ("line", "00C300"),
    "Proton-Mail_rushi": ("protonmail", "6D4AFF"),
    "Google-Photos": ("googlephotos", "FBBC04"),
    "Duolingo": ("duolingo", "58CC02"),
    "TikTok_icysymmetra": ("tiktok", "000000"),
    "Messenger": ("messenger", "0084FF"),
    "Twitch": ("twitch", "9146FF"),
    "IMDb": ("imdb", "F5C518"),
    "AccuWeather": ("accuweather", "EF4023"),
}


def _load_entries() -> list:
    data = load_toml(CONFIG_PATH)
    return parse_app_entries(data, parse_config(data))


_HOSTS = {"github": "https://github.com", "gitlab": "https://gitlab.com"}


def _patches_url(patches: dict[str, dict]) -> str | None:
    key = next(iter(patches), None)
    if not key or ":" not in key:
        return None
    host, path = key.split(":", 1)
    base = _HOSTS.get(host)
    return f"{base}/{path}" if base else None


def _badge_text(s: str) -> str:
    return s.replace("-", "--").replace(" ", "_")


def _source_badge(brand: str, url: str | None) -> str:
    badge = f"![{brand}](https://img.shields.io/badge/{_badge_text(brand)}-555?style=flat-square&logo=github&logoColor=white)"
    return f"[{badge}]({url})" if url else badge


def _app_icon(table: str) -> str:
    if brand_icon := BRAND_ICONS.get(table):
        slug, _ = brand_icon
        return f'<img src="https://cdn.simpleicons.org/{slug}" width="20" height="20" alt="">'
    return CATEGORIES.get(table, "📦")


def _download_badge(table: str) -> str:
    slug, color = BRAND_ICONS.get(table, ("github", "4c72c9"))
    badge = f"![Download](https://img.shields.io/badge/Download-{color}?style=flat-square&logo={slug}&logoColor=white)"
    return f"[{badge}]({REPO_URL}/releases?q={quote(table)}&expanded=true)"


def _obtainium_link(table: str, app_name: str, brand: str) -> str | None:
    pkg_name = PKG_NAMES.get(table)
    if not pkg_name:
        return None

    brand_lower = brand.lower().replace(" ", "-")
    apk_prefix = f"{app_name.lower().replace(' ', '-')}-{brand_lower}-"
    additional_settings = {
        "includePrereleases": False,
        "fallbackToOlderReleases": True,
        "filterReleaseTitlesByRegEx": f"-{brand_lower}$",
        "filterReleaseNotesByRegEx": app_name,
        "verifyLatestTag": False,
        "sortMethodChoice": "date",
        "useLatestAssetDateAsReleaseDate": False,
        "releaseTitleAsVersion": False,
        "trackOnly": False,
        "versionExtractionRegEx": "",
        "matchGroupToUse": "",
        "versionDetection": False,
        "releaseDateAsVersion": False,
        "useVersionCodeAsOSVersion": False,
        "apkFilterRegEx": apk_prefix,
        "invertAPKFilter": False,
        "autoApkFilterByArch": True,
        "appName": app_name,
        "appAuthor": "",
        "shizukuPretendToBeGooglePlay": False,
        "allowInsecure": False,
        "exemptFromBackgroundUpdates": False,
        "skipUpdateNotifications": False,
        "about": "",
        "refreshBeforeDownload": False,
        "includeZips": False,
        "zippedApkFilterRegEx": "",
        "dontSortReleasesList": False,
        "github-creds": "",
    }
    payload = {
        "id": pkg_name,
        "url": REPO_URL,
        "author": REPO_AUTHOR,
        "name": app_name,
        "preferredApkIndex": 0,
        "additionalSettings": json.dumps(additional_settings, separators=(",", ":")),
        "overrideSource": "GitHub",
    }
    encoded = quote(json.dumps(payload, separators=(",", ":")))
    return f"https://apps.obtainium.imranr.dev/redirect?r=obtainium://app/{encoded}"


def _build_table() -> str:
    entries = [e for e in _load_entries() if e.enabled]
    rows = sorted(
        (
            (e.table, e.brand, e.app_name, _patches_url(e.patches), _obtainium_link(e.table, e.app_name, e.brand))
            for e in entries
        ),
        key=lambda r: (r[1].lower(), r[2].lower()),
    )
    brand_count = len({brand for _, brand, _, _, _ in rows})

    lines = [
        '<div align="center">',
        "",
        f"![Apps](https://img.shields.io/badge/apps-{len(rows)}-4c9c4c?style=flat-square)"
        f" ![Sources](https://img.shields.io/badge/sources-{brand_count}-4c72c9?style=flat-square)",
        "",
        "| | App | Download | Source | |",
        "|:---:|---|:---:|---|---|",
    ]
    for table, brand, app_name, patches_url, ob_link in rows:
        icon = _app_icon(table)
        download = _download_badge(table)
        source = _source_badge(brand, patches_url)
        obtainium = f"[![Obtainium](https://img.shields.io/badge/Add_to-Obtainium-4500FF?style=flat-square&logo=obtainium)]({ob_link})" if ob_link else ""
        lines.append(f"| {icon} | {app_name} | {download} | {source} | {obtainium} |")
    lines += ["", "</div>"]
    return "\n".join(lines)


def update_table() -> None:
    content = README_PATH.read_text(encoding="utf-8")
    if START not in content or END not in content:
        abort(f"README markers {START!r}/{END!r} not found")
    before, rest = content.split(START, 1)
    _, after = rest.split(END, 1)
    new_content = f"{before}{START}\n{_build_table()}\n{END}{after}"
    if new_content == content:
        print("unchanged")
        return
    README_PATH.write_text(new_content, encoding="utf-8")
    print("updated")


def main() -> None:
    match sys.argv[1:]:
        case []:
            update_table()
        case _:
            abort("Usage: readme.py")


if __name__ == "__main__":
    main()
