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
    "Proton-Mail_hxreborn": "ch.protonmail.android",
    "Projectivy-Launcher": "com.spocky.projengmenu",
    "KineStop": "com.urbandroid.kinestop",
    "Facebook": "com.facebook.katana",
    "Gboard": "dev.jason.com.google.android.inputmethod.latin",
    "LINE": "jp.naver.line.android",
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
            (e.brand, e.app_name, _patches_url(e.patches), _obtainium_link(e.table, e.app_name, e.brand))
            for e in entries
        ),
        key=lambda r: (r[0].lower(), r[1].lower()),
    )
    brand_count = len({brand for brand, _, _, _ in rows})

    lines = [
        '<div align="center">',
        "",
        f"*{len(rows)} apps across {brand_count} patch sources*",
        "",
        "| Patch Source | App | |",
        "|---|---|---|",
    ]
    for brand, app_name, patches_url, ob_link in rows:
        source = f"[{brand}]({patches_url})" if patches_url else brand
        obtainium = f"[![Obtainium](https://img.shields.io/badge/Add_to-Obtainium-4500FF?logo=obtainium)]({ob_link})" if ob_link else ""
        lines.append(f"| {source} | {app_name} | {obtainium} |")
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
