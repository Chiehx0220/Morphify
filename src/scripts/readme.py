import json
import re
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
    "Proton-Mail_hxreborn": "ch.protonmail.android",
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
    "Mimo": "com.getmimo",
    "Sleep-as-Android": "com.urbandroid.sleep",
    "Parallel-Space-Pro": "com.parallel.space.pro",
    "AccuBattery": "com.digibites.accubattery",
    "Athena": "com.kin.athena",
    "Proton-Pass": "proton.android.pass",
    "SD-Maid-SE": "eu.darken.sdmse",
    "CrazyGames": "com.crazygames.crazygamesapp",
    "KakaoTalk": "com.kakao.talk",
    "SoundCloud": "com.soundcloud.android",
}

# Real per-app brand icon (Simple Icons slug) + official brand color, used for
# the Download badge. Apps without a Simple Icons entry fall back to a
# generic grey badge.
BRAND_ICONS = {
    "YouTube": ("youtube", "FF0000"),
    "YT-Music": ("youtubemusic", "FF0000"),
    "Reddit": ("reddit", "FF4500"),
    "X-Twitter": ("x", "000000"),
    "Instagram": ("instagram", "E4405F"),
    "Facebook": ("facebook", "1877F2"),
    "LINE": ("line", "00C300"),
    "Proton-Mail_hxreborn": ("protonmail", "6D4AFF"),
    "Google-Photos": ("googlephotos", "FBBC04"),
    "Duolingo": ("duolingo", "58CC02"),
    "KakaoTalk": ("kakaotalk", "FFCD00"),
    "SoundCloud": ("soundcloud", "FF5500"),
    "TikTok_icysymmetra": ("tiktok", "000000"),
    "Messenger": ("messenger", "0084FF"),
    "Twitch": ("twitch", "9146FF"),
    "IMDb": ("imdb", "F5C518"),
    "AccuWeather": ("accuweather", "EF4023"),
}

# Display order for the grouped README table; apps not listed here fall
# into an "Other" group appended at the end.
CATEGORY_ORDER = [
    "Media & Entertainment",
    "Social & Messaging",
    "Privacy & Security",
    "Utilities",
    "Education",
    "Creativity",
    "Launchers",
]

CATEGORY_ICONS = {
    "Media & Entertainment": "🎬",
    "Social & Messaging": "💬",
    "Privacy & Security": "🔒",
    "Utilities": "🛠️",
    "Education": "📚",
    "Creativity": "🎨",
    "Launchers": "🚀",
    "Other": "📦",
}

# Accent color per category, used for the nav badges in _build_table().
CATEGORY_COLORS = {
    "Media & Entertainment": "EF5350",
    "Social & Messaging": "5C6BC0",
    "Privacy & Security": "26A69A",
    "Utilities": "78909C",
    "Education": "FFA726",
    "Creativity": "AB47BC",
    "Launchers": "29B6F6",
    "Other": "8D6E63",
}

CATEGORY_GROUP = {
    "YouTube": "Media & Entertainment",
    "YT-Music": "Media & Entertainment",
    "SoundCloud": "Media & Entertainment",
    "IMDb": "Media & Entertainment",
    "Twitch": "Media & Entertainment",
    "CrazyGames": "Media & Entertainment",
    "Google-Photos": "Media & Entertainment",
    "Instagram": "Social & Messaging",
    "Facebook": "Social & Messaging",
    "Messenger": "Social & Messaging",
    "X-Twitter": "Social & Messaging",
    "LINE": "Social & Messaging",
    "KakaoTalk": "Social & Messaging",
    "Reddit": "Social & Messaging",
    "TikTok_icysymmetra": "Social & Messaging",
    "Proton-Mail_hxreborn": "Privacy & Security",
    "Proton-Pass": "Privacy & Security",
    "Athena": "Privacy & Security",
    "SD-Maid-SE": "Privacy & Security",
    "Gboard": "Utilities",
    "AccuBattery": "Utilities",
    "AccuWeather": "Utilities",
    "Sleep-as-Android": "Utilities",
    "Parallel-Space-Pro": "Utilities",
    "KineStop": "Utilities",
    "Duolingo": "Education",
    "Mimo": "Education",
    "SketchBook": "Creativity",
    "PictureThis": "Creativity",
    "Niagara-Launcher": "Launchers",
    "Projectivy-Launcher": "Launchers",
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
    return s.replace("-", "--").replace(" ", "_").replace("&", "%26")


def _source_badge(brand: str, url: str | None) -> str:
    badge = f"![{brand}](https://img.shields.io/badge/{_badge_text(brand)}-555?style=flat-square&logo=github&logoColor=white)"
    return f"[{badge}]({url})" if url else badge


_CARDS_DIR = Path("images/cards")

# Play Store package for apps whose PKG_NAMES holds a renamed/patched id
# instead of the stock one (renamed apps aren't listed on the Play Store
# under that id). Shared with src/scripts/cards.py, which fetches icons.
STOCK_PKG_OVERRIDE = {
    "Google-Photos": "com.google.android.apps.photos",
    "Gboard": "com.google.android.inputmethod.latin",
    "Messenger": "com.facebook.orca",
}


def _play_store_url(table: str) -> str | None:
    pkg = STOCK_PKG_OVERRIDE.get(table, PKG_NAMES.get(table))
    return f"https://play.google.com/store/apps/details?id={pkg}" if pkg else None


def _has_card(table: str) -> bool:
    return (_CARDS_DIR / f"{table}-header.svg").exists()


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


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _card_row(table: str, app_name: str, repo_url: str | None, ob_link: str | None) -> str:
    base = f"{_CARDS_DIR.as_posix()}/{table}"
    play_url = _play_store_url(table) or "#"
    gh_dl_url = f"{REPO_URL}/releases?q={quote(table)}&expanded=true"
    obtainium_url = ob_link or "#"
    repo_url = repo_url or gh_dl_url
    # align="bottom" removes the residual baseline-alignment gap; each block
    # is its own <a><img> joined by <br> in one paragraph (not separate
    # blank-line paragraphs) so they sit visually flush as one card, and not
    # wrapped in a leading <div>/<p> with no blank line around it (that
    # makes GitHub's parser treat the whole thing as literal HTML instead of
    # markdown — confirmed the hard way earlier).
    return (
        '<div align="center">\n\n'
        f'<a href="{play_url}"><img align="bottom" src="{base}-header.svg" alt="{app_name}"></a><br>'
        f'<a href="{repo_url}"><img align="bottom" src="{base}-repo.svg" alt="repo"></a><br>'
        f'<a href="{gh_dl_url}"><img align="bottom" src="{base}-download.svg" alt="Download"></a>'
        f'<a href="{obtainium_url}"><img align="bottom" src="{base}-obtainium.svg" alt="Obtainium"></a>\n\n'
        "</div>"
    )


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

    groups: dict[str, list[tuple]] = {}
    for row in rows:
        groups.setdefault(CATEGORY_GROUP.get(row[0], "Other"), []).append(row)
    order = [c for c in (*CATEGORY_ORDER, "Other") if c in groups]

    lines = [
        '<div align="center">',
        "",
        f"![Apps](https://img.shields.io/badge/apps-{len(rows)}-4c9c4c?style=flat-square)"
        f" ![Sources](https://img.shields.io/badge/sources-{brand_count}-4c72c9?style=flat-square)",
        "",
    ]
    # GitHub prefixes hand-written heading `id`s with "user-content-" to avoid
    # colliding with its own page ids, so the anchor links must match that.
    # The emoji is baked into the badge image itself (rather than sitting next to
    # it as link text) so GitHub doesn't underline it and it renders at badge scale.
    navlinks = []
    for c in order:
        icon = CATEGORY_ICONS.get(c, "📦")
        label = quote(f"{icon} {c}", safe="")
        color = CATEGORY_COLORS.get(c, "8D6E63")
        badge = f"https://img.shields.io/badge/{label}-{len(groups[c])}-{color}?style=flat-square"
        navlinks.append(f"[![{icon} {c}]({badge})](#user-content-{_slugify(c)})")
    lines.append(" ".join(navlinks))
    lines.append("")
    lines.append("</div>")

    for category in order:
        anchor = _slugify(category)
        lines += [
            "",
            '<div align="center">',
            "",
            f'<h3 id="{anchor}">{CATEGORY_ICONS.get(category, "📦")} {category} ({len(groups[category])})</h3>',
            "",
            "</div>",
            "",
            "<details open>",
            "<summary>Show / hide</summary>",
            "",
        ]
        for table, brand, app_name, patches_url, ob_link in groups[category]:
            if _has_card(table):
                lines.append(_card_row(table, app_name, patches_url, ob_link))
            else:
                # Fallback for an app added since the last manual run of
                # src/scripts/cards.py (which fetches Play Store icons and
                # isn't run by CI) — a plain link line rather than a blank gap.
                download = _download_badge(table)
                source = _source_badge(brand, patches_url)
                obtainium = f" [![Obtainium](https://img.shields.io/badge/Add_to-Obtainium-4500FF?style=flat-square&logo=obtainium)]({ob_link})" if ob_link else ""
                lines.append(f"- **{app_name}** — {source} {download}{obtainium}")
        lines += ["", "</details>"]
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
