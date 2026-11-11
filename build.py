#!/usr/bin/env python3
"""Build a static image gallery from images/ into output/.

Standard library only. Produces:
  output/images/<file>        copies of every source image
  output/<slug>.html          one page per image
  output/index.html           gallery grid
  output/rss.xml              Pinterest RSS auto-pin feed
  output/sitemap.xml          sitemap for search engines
"""

import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote, urljoin
from xml.sax.saxutils import escape as xml_escape

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.json")
TEMPLATE_PATH = os.path.join(ROOT, "templates", "image-page.html")
IMAGES_DIR = os.path.join(ROOT, "images")
OUTPUT_DIR = os.path.join(ROOT, "docs")  # GitHub Pages serves docs/ from main
OUTPUT_IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")

# Optional: when set (e.g. https://pics.example.com, an R2 public bucket domain),
# images are linked from there and NOT copied into output/, so git never stores them.
EXTERNAL_IMAGE_URL = os.environ.get("R2_PUBLIC_URL", "").strip().rstrip("/")


def image_src(filename):
    """Path used in the gallery grid: root-relative locally, absolute when external."""
    if EXTERNAL_IMAGE_URL:
        return f"{EXTERNAL_IMAGE_URL}/{quote(filename)}"
    return f"/images/{quote(filename)}"


def image_abs(config, filename):
    """Absolute image URL for pages, RSS (Pinterest) and structured data."""
    if EXTERNAL_IMAGE_URL:
        return f"{EXTERNAL_IMAGE_URL}/{quote(filename)}"
    return f"{config['base_url']}/images/{quote(filename)}"

EXTENSIONS = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".png": "image/png", ".webp": "image/webp"}
REQUIRED_CONFIG = ["site_title", "base_url", "author_name", "site_description"]


def log(msg):
    print(msg, flush=True)


def load_config():
    if not os.path.isfile(CONFIG_PATH):
        sys.exit(f"ERROR: config.json not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    missing = [k for k in REQUIRED_CONFIG if not str(config.get(k, "")).strip()]
    if missing:
        sys.exit(f"ERROR: config.json is missing values for: {', '.join(missing)}")
    config["base_url"] = config["base_url"].rstrip("/")
    if not config["base_url"].startswith(("http://", "https://")):
        sys.exit("ERROR: base_url must start with https:// (e.g. https://gallery.example.com)")
    config.setdefault("pinterest_handle", "")
    return config


RESERVED_SLUGS = {"index", "rss", "sitemap", "images"}


def slugify(name):
    """Turn a file name into a lowercase, ASCII, hyphen-separated URL slug.

    'My Summer Product (1)' -> 'my-summer-product-1'
    'Café Été!'             -> 'cafe-ete'
    """
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "image"


def title_from_slug(slug):
    return slug.replace("-", " ").strip().title() or "Untitled"


def find_images():
    """Return sorted list of (source_path, filename, slug, ext) with unique slugs."""
    if not os.path.isdir(IMAGES_DIR):
        return []
    paths = glob.glob(os.path.join(IMAGES_DIR, "*"))
    results, used = [], {}
    for path in sorted(paths):
        if not os.path.isfile(path):
            continue
        stem, ext = os.path.splitext(os.path.basename(path))
        ext = ext.lower()
        if ext not in EXTENSIONS:
            continue
        base_slug = slugify(stem)
        slug = base_slug
        counter = 1
        # Keep slugs unique and away from generated file names (index.html, rss.xml...).
        while slug in used or slug in RESERVED_SLUGS:
            counter += 1
            slug = f"{base_slug}-{counter}"
        used[slug] = True
        results.append((path, slug + ext, slug, ext))
    return results


def clean_output():
    """Remove previously generated files but keep .gitkeep files."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for name in os.listdir(OUTPUT_DIR):
        full = os.path.join(OUTPUT_DIR, name)
        if name == ".gitkeep":
            continue
        if os.path.isdir(full):
            shutil.rmtree(full)
        else:
            os.remove(full)
    os.makedirs(OUTPUT_IMAGES_DIR, exist_ok=True)


def file_timestamp(path):
    """When the picture was added. Git's add date for committed files; otherwise the
    file's modification time (sync_r2.sh sets this to the R2 upload time in CI)."""
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%cI", "--", path],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()
        if out:
            return datetime.fromisoformat(out[-1]).astimezone(timezone.utc)
    except (OSError, subprocess.CalledProcessError, ValueError):
        pass
    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)


def iso_date(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def rfc822_date(dt):
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def build_json_ld(item, config, page_url, image_url):
    data = {
        "@context": "https://schema.org",
        "@type": "ImageObject",
        "name": item["title"],
        "description": config["site_description"],
        "contentUrl": image_url,
        "url": page_url,
        "license": f"{config['base_url']}/license",
        "acquireLicensePage": f"{config['base_url']}/license",
        "creditText": config["author_name"],
        "creator": {"@type": "Organization", "name": config["author_name"]},
        "copyrightNotice": f"© {config['author_name']}",
        "datePublished": iso_date(item["date"]),
    }
    # json.dumps output is safe inside <script>, except for "</", which we escape.
    return json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")


def render_page(template, values):
    """Replace {{KEY}} placeholders in one pass; values are inserted as-is."""
    return re.sub(r"\{\{(\w+)\}\}",
                  lambda m: values.get(m.group(1), m.group(0)),
                  template)


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def build_index(items, config):
    cards = []
    for item in items:
        cards.append(
            '    <a class="card" href="{href}">'
            '<img src="{src}" alt="{alt}" loading="lazy">'
            '<span>{title}</span></a>'.format(
                # Root-relative paths: output/ is the web root on Cloudflare Pages.
                href="/" + quote(item["slug"]) + ".html",
                src=image_src(item["file"]),
                alt=html.escape(item["title"], quote=True),
                title=html.escape(item["title"]),
            )
        )
    grid = "\n".join(cards) or "    <p>No images published yet.</p>"
    title = html.escape(config["site_title"])
    desc = html.escape(config["site_description"], quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Orbitron:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="canonical" href="{html.escape(config['base_url'])}/">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:url" content="{html.escape(config['base_url'])}/">
<style>
  :root {{ --cyan:#22D3EE; --blue:#2563FF; --violet:#A855F7; --magenta:#FF2ED1; --bg:#000000;
          --fg:#E9EFFF; --muted:#9DB0DE; --card:#0A0A0A; --line:rgba(34,211,238,.38); }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; min-height:100vh; color:var(--fg); font:17px/1.6 Inter,"Segoe UI",system-ui,-apple-system,sans-serif;
         background: #000; }}
  header {{ text-align:center; padding:1.6rem 1rem .6rem; }}
  header h1 {{ margin:0; font:700 clamp(1.4rem,4vw,2rem)/1.2 Orbitron,"Eurostile","Segoe UI",system-ui,sans-serif;
              letter-spacing:.08em; text-transform:uppercase; color:#fff;
              background:linear-gradient(90deg,#22D3EE,#2563FF 35%,#A855F7 70%,#FF2ED1);
              -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
              filter:drop-shadow(0 0 12px rgba(37,99,255,.6)); }}
  header p {{ margin:.4rem 0 0; color:var(--muted); }}
  .grid {{ display:grid; gap:1.1rem; padding:1rem; max-width:1200px; margin:0 auto;
          grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }}
  .card {{ display:block; background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden;
          text-decoration:none; color:var(--fg); transition: box-shadow .2s, border-color .2s, transform .2s; }}
  .card:hover {{ border-color:var(--magenta); transform:translateY(-2px);
                box-shadow:0 0 26px rgba(37,99,255,.6), 0 0 40px rgba(255,46,209,.25); }}
  .card img {{ display:block; width:100%; aspect-ratio: 1 / 1; object-fit: cover; }}
  .card span {{ display:block; padding:.7rem .9rem; font-size:.9rem; font-weight:600; }}
  footer {{ text-align:center; color:var(--muted); font-size:.85rem; padding:2rem 1rem; }}
  a {{ color:var(--cyan); }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <p>{desc}</p>
</header>
<main class="grid">
{grid}
</main>
<footer>&copy; {html.escape(config['author_name'])}</footer>
</body>
</html>
"""


def build_rss(items, config):
    base = config["base_url"]
    now = rfc822_date(datetime.now(timezone.utc))
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        f"  <title>{xml_escape(config['site_title'])}</title>",
        f"  <link>{xml_escape(base)}/</link>",
        f"  <description>{xml_escape(config['site_description'])}</description>",
        f"  <language>en</language>",
        f"  <lastBuildDate>{now}</lastBuildDate>",
        f'  <atom:link href="{xml_escape(base)}/rss.xml" rel="self" type="application/rss+xml"/>',
    ]
    for item in items:
        page_url = f"{base}/{quote(item['slug'])}.html"
        image_url = image_abs(config, item["file"])
        preview = (
            f'<p><a href="{xml_escape(page_url)}"><img src="{xml_escape(image_url)}" '
            f'alt="{xml_escape(item["title"])}" /></a></p>'
            f"<p>{xml_escape(config['site_description'])}</p>"
        )
        # A literal "]]>" would end the CDATA section early, so split it.
        preview = preview.replace("]]>", "]]]]><![CDATA[>")
        parts += [
            "  <item>",
            f"    <title>{xml_escape(item['title'])}</title>",
            f"    <link>{xml_escape(page_url)}</link>",
            f'    <guid isPermaLink="true">{xml_escape(page_url)}</guid>',
            f"    <pubDate>{rfc822_date(item['date'])}</pubDate>",
            f"    <description><![CDATA[{preview}]]></description>",
            f'    <enclosure url="{xml_escape(image_url)}" length="{item["size"]}" type="{item["mime"]}" />',
            "  </item>",
        ]
    parts += ["</channel>", "</rss>", ""]
    return "\n".join(parts)


def build_sitemap(items, config):
    base = config["base_url"]
    ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ET.register_namespace("", ns)
    urlset = ET.Element(f"{{{ns}}}urlset")
    now = iso_date(datetime.now(timezone.utc))

    def add(loc, lastmod):
        url = ET.SubElement(urlset, f"{{{ns}}}url")
        ET.SubElement(url, f"{{{ns}}}loc").text = loc
        ET.SubElement(url, f"{{{ns}}}lastmod").text = lastmod

    add(f"{base}/", now)
    for item in items:
        add(f"{base}/{quote(item['slug'])}.html", iso_date(item["date"]))
    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            + ET.tostring(urlset, encoding="unicode") + "\n")


def main():
    config = load_config()
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()

    sources = find_images()
    clean_output()
    base = config["base_url"]
    log(f"Site: {config['site_title']} ({base})")
    log(f"Found {len(sources)} image(s) in images/")

    items = []
    for src, filename, slug, ext in sources:
        if not EXTERNAL_IMAGE_URL:          # external images are served from R2, not git
            shutil.copy2(src, os.path.join(OUTPUT_IMAGES_DIR, filename))

        title = title_from_slug(slug)
        date = file_timestamp(src)
        image_url = image_abs(config, filename)
        page_url = f"{base}/{quote(slug)}.html"
        values = {
            "TITLE": html.escape(title, quote=True),
            "SITE_TITLE": html.escape(config["site_title"], quote=True),
            "SITE_DESCRIPTION": html.escape(config["site_description"], quote=True),
            "AUTHOR": html.escape(config["author_name"], quote=True),
            "IMAGE_URL": html.escape(image_url, quote=True),
            "PAGE_URL": html.escape(page_url, quote=True),
            "BASE_URL": html.escape(base, quote=True),
        }
        item = {"title": title, "slug": slug, "file": filename, "date": date,
                "size": os.path.getsize(src), "mime": EXTENSIONS[ext]}
        values["JSON_LD"] = build_json_ld(item, config, page_url, image_url)
        write_text(os.path.join(OUTPUT_DIR, slug + ".html"), render_page(template, values))
        items.append(item)
        log(f"  page  {slug}.html  <- images/{filename}")

    items.sort(key=lambda i: i["date"], reverse=True)

    write_text(os.path.join(OUTPUT_DIR, "index.html"), build_index(items, config))
    write_text(os.path.join(OUTPUT_DIR, "rss.xml"), build_rss(items, config))
    write_text(os.path.join(OUTPUT_DIR, "sitemap.xml"), build_sitemap(items, config))

    log("Generated: index.html, rss.xml, sitemap.xml")
    log(f"Done. {len(items)} page(s) written to docs/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
