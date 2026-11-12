# image-engine-template

A zero-cost static image gallery generator. Put pictures in `images/` and it produces a gallery, one search-friendly page per image (with an optional **Buy** button), a Pinterest RSS feed, and a sitemap in `docs/`. An optional free AI writer drafts each picture's title and description.

This repository is meant to be used as a **GitHub Template repository**. Each client gets their own copy.

## What it generates

| File | Purpose |
|---|---|
| `docs/index.html` | Gallery grid linking to every image page |
| `docs/<slug>.html` | One page per image with Open Graph, Twitter Card and JSON-LD metadata |
| `docs/rss.xml` | RSS 2.0 feed for Pinterest auto-pinning |
| `docs/sitemap.xml` | Sitemap for Google Search Console |
| `docs/images/` | Copies of the source images |

## Setup for a new client

1. Click **Use this template → Create a new repository**.
2. Edit `config.json`:
   - `site_title`, `site_description`, `author_name`, `pinterest_handle`
   - `base_url`: the final site address, with `https://` and no trailing slash. Leave it empty to use the repository's free GitHub Pages address automatically (`https://username.github.io/repo-name`).
   - `pinterest_verify` / `google_verify`: the codes Pinterest and Google Search Console give you when you claim the site with the HTML-tag method. They are added to the gallery page.
   - Optional: `shop_url` (a default Buy link for every picture, e.g. the client's shop), `shop_button_text` (default "Shop this"), `ai_context` (a sentence telling the AI writer what the business sells; defaults to `site_description`), `ai_model`.
3. In the repository, go to **Settings → Pages**, set the source to the `main` branch and the folder `/docs`, or connect it to Cloudflare Pages with the build output directory set to `docs`.
4. Add pictures to `images/` and commit. The workflow rebuilds `docs/` automatically.

## Buy buttons and descriptions (per picture)

Put a note file next to a picture with the same name: `blue-vase.jpg` → `blue-vase.txt`. Optional `Key: value` lines at the top, a blank line, then the description:

```
Title: Blue Stoneware Vase
Shop: https://shop.example.com/blue-vase
Price: $24
Button: Buy this vase

A glossy blue stoneware vase, thrown by hand in Kansas City.
```

- The description is used on the page, in the meta and social descriptions, in JSON-LD, and in the Pinterest feed. Its first sentence becomes the image alt text.
- `Shop` adds a Buy button (must start with `http://` or `https://`; anything else is ignored with a warning). Without it, `shop_url` from `config.json` is used; without either, there is no button.
- Without a note, the page falls back to the file name for the title and `site_description` for the text.

## AI writer (optional, free)

When a `GEMINI_API_KEY` repository secret is set, the workflow runs `scripts/describe.py` before each build. For any picture that is missing a description (or has a description but a meaningless file name like `IMG_1234` and no title), Google's free Gemini looks at it and writes a draft to `images/<name>.ai.txt`, which the workflow commits so it is only written once. The owner's `.txt` always overrides the `.ai.txt`. At most 10 pictures are described per run to stay inside the free allowance.

Setup: create a key at https://aistudio.google.com/apikey (do not turn on billing), then add it under **Settings → Secrets and variables → Actions** as `GEMINI_API_KEY`. Note that pictures are sent to Google for this step, and on the free plan Google may use them to improve its products. Tell clients before you turn it on.

## Client uploads from a phone (Option A: Worker + R2)

Clients can upload from `https://<their-site>/upload` without touching GitHub, and type an optional Shop link, Price and Description that are saved as the picture's `.txt` note. Pictures are stored in a private R2 bucket, not in git. The Action syncs them into `images/` on the build runner, and `build.py` links them from R2 when `R2_PUBLIC_URL` is set. See `worker/README.md` for the setup steps.

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

`.github/workflows/build.yml` runs on pushes to `main` that change `images/`, `config.json`, `build.py` or `templates/`. It runs the build and commits `docs/` back to the repository with `[skip ci]`. Cloudflare Pages then deploys `docs/` on its own schedule. Set the Cloudflare build command to none and the output directory to `docs`.

## Files

```
config.json            client settings
build.py               the generator (standard library only)
templates/image-page.html   per-image page template
images/                source pictures (you add these)
docs/                generated site (committed for deployment)
.github/workflows/build.yml auto-build workflow
CLIENT-GUIDE.md        non-technical guide for the client
worker/                upload Worker (R2 storage + build trigger)
scripts/sync_r2.sh     copies R2 pictures and notes into images/ on the runner
scripts/describe.py    optional AI writer (images/<name>.ai.txt)
```
