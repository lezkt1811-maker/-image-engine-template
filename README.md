# image-engine-template

A zero-cost static image gallery generator. Put pictures in `images/`, run `build.py`, and it produces a gallery, one page per image, a Pinterest RSS feed, and a sitemap in `output/`.

This repository is meant to be used as a **GitHub Template repository**. Each client gets their own copy.

## What it generates

| File | Purpose |
|---|---|
| `output/index.html` | Gallery grid linking to every image page |
| `output/<slug>.html` | One page per image with Open Graph, Twitter Card and JSON-LD metadata |
| `output/rss.xml` | RSS 2.0 feed for Pinterest auto-pinning |
| `output/sitemap.xml` | Sitemap for Google Search Console |
| `output/images/` | Copies of the source images |

## Setup for a new client

1. Click **Use this template → Create a new repository**.
2. Edit `config.json`:
   - `site_title`, `site_description`, `author_name`, `pinterest_handle`
   - `base_url`: the final site address, with `https://` and no trailing slash.
3. In the repository, go to **Settings → Pages**, set the source to the branch and the folder `/output`, or connect it to Cloudflare Pages with the build output directory set to `output`.
4. Add pictures to `images/` and commit. The workflow rebuilds `output/` automatically.

## Local build

Requires Python 3.9 or newer. No packages are needed.

```bash
python3 build.py
```

The script prints a summary of each page it writes. Generated files are replaced on every run. Files in `images/` are never changed.

## Image naming

- Supported types: `.jpg`, `.jpeg`, `.png`, `.webp`.
- The file name becomes the page slug and the title. `blue-vase.jpg` becomes `blue-vase.html` with the title "Blue Vase".
- Names are lowercased, and characters other than letters and numbers become hyphens. Duplicate names get a numeric suffix.

## Deployment

`.github/workflows/build.yml` runs on pushes to `main` that change `images/`, `config.json`, `build.py` or `templates/`. It runs the build and commits `output/` back to the repository with `[skip ci]`. Cloudflare Pages then deploys `output/` on its own schedule. Set the Cloudflare build command to none and the output directory to `output`.

## Files

```
config.json            client settings
build.py               the generator (standard library only)
templates/image-page.html   per-image page template
images/                source pictures (you add these)
output/                generated site (committed for deployment)
.github/workflows/build.yml auto-build workflow
CLIENT-GUIDE.md        non-technical guide for the client
```
