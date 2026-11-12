#!/usr/bin/env python3
"""Robot writer: drafts a title and description for pictures that need one.

Uses Google's free Gemini service, only when a GEMINI_API_KEY secret is set.
The draft is saved as images/<name>.ai.txt. Your own images/<name>.txt always wins,
so the robot only fills in what you left out:
  - no description in your note          -> the AI looks at the picture and writes one
  - a description but no title, and a
    file name that says nothing (IMG_1234) -> the AI writes a title from your words
If anything goes wrong (no key, free limit reached, service down) it quietly skips,
and the page falls back to the file name and site description. It never stops the build.
"""
import base64
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import EXTENSIONS, parse_note, slugify  # noqa: E402  same rules as the site

IMAGES = ROOT / "images"
MAX_PER_RUN = 10  # protects the free daily allowance
API = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.5-flash-lite"
NOISE_WORDS = {"img", "image", "photo", "pic", "picture", "dsc", "dcim", "screenshot",
               "pxl", "mvimg", "whatsapp", "edited", "copy", "final", "untitled", "jpeg", "jpg", "png"}

PICTURE_PROMPT = (
    "You are writing the web page text for one picture on the website of {site}. "
    "About the business: {about}. Reply in exactly this format. Line 1: TITLE: followed by a "
    "page title of 2 to 7 words in Title Case that says what the picture shows, the way a "
    "shopper would search for it (no quotes, no trailing period, no clickbait, no keyword "
    "lists). Then a blank line, then the description: 2 or 3 sentences of plain, natural "
    "English describing only what you can actually see. The FIRST sentence must be under "
    "120 characters and work as alt text for a blind reader. If the picture shows a product, "
    "name the product type, colors and materials you can see. Mention readable text in the "
    "picture. No hashtags, markdown, prices, or invented facts."
)
TITLE_PROMPT = (
    "Write a page title for a picture on the website of {site} ({about}). Base it only on "
    "this description:\n\n{desc}\n\nThe title must be 2 to 7 words in Title Case and say "
    "specifically what the picture shows. No quotes, no trailing period, no clickbait, no "
    "keyword lists. Reply with the title only."
)


def meaningful_name(stem):
    """True if the file name already describes the picture (e.g. blue-ceramic-vase)."""
    words = [w for w in slugify(stem).split("-") if w]
    return any(len(w) >= 3 and w.isalpha() and w not in NOISE_WORDS for w in words)


def small_jpeg_b64(path):
    from PIL import Image, ImageOps  # installed by the workflow only when AI is on
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    img.thumbnail((1024, 1024), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def clean_title(t):
    t = re.sub(r"[*_#`>]+", "", t or "").strip()
    t = t.splitlines()[0] if t else ""
    t = re.sub(r"(?i)^title:\s*", "", t).strip(" \"'.")
    return t if 3 <= len(t) <= 70 else ""


def split_answer(text):
    """Return (title, description) from the AI's reply."""
    text = re.sub(r"[*_#`>]+", "", text or "").strip()
    title = ""
    m = re.match(r"(?i)\s*title:[ \t]*(.+?)[ \t]*(?:\n|$)", text)
    if m:
        title = clean_title(m.group(1))
        text = text[m.end():]
    body = " ".join(text.split()).strip(" \"'")
    if len(body) > 600:
        body = body[:600].rsplit(" ", 1)[0]
    return title, body


def generate(parts, model, key):
    req = urllib.request.Request(
        f"{API}/models/{model}:generateContent",
        data=json.dumps({"contents": [{"parts": parts}]}).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    return data["candidates"][0]["content"]["parts"][0]["text"]


def find_models(key):
    """Ask Google which fast models exist right now (in case the default is retired)."""
    req = urllib.request.Request(f"{API}/models?pageSize=200", headers={"x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=60) as resp:
        models = json.load(resp).get("models", [])
    found = []
    for m in models:
        name = m.get("name", "").replace("models/", "")
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        if not re.match(r"gemini-\d", name) or "flash" not in name:
            continue
        if re.search(r"image|tts|audio|live|embed|robot|computer|thinking|exp|learnlm|gemma", name):
            continue
        ver = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
        found.append((0 if "lite" in name else 1, 1 if "preview" in name else 0,
                      -(float(ver.group(1)) if ver else 0), name))
    return [f[-1] for f in sorted(found)][:3]


def run(parts, state, key):
    """Try the current model; if Google says it is gone or limited, find and try others."""
    last, i = None, 0
    while i < len(state["models"]):
        model = state["models"][i]
        i += 1
        try:
            text = generate(parts, model, key)
            state["models"] = [model] + [x for x in state["models"] if x != model]
            return text, None
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (404, 403, 429) and not state["discovered"]:
                state["discovered"] = True
                try:
                    extra = [x for x in find_models(key) if x not in state["models"]]
                    print(f"Model {model} not usable ({e.code}); also trying: {', '.join(extra) or 'nothing found'}")
                    state["models"] += extra
                except (urllib.error.URLError, ValueError, OSError) as e2:
                    print(f"Could not list models: {e2}")
        except (urllib.error.URLError, KeyError, IndexError, ValueError, OSError) as e:
            return "", e
    return "", last


def read(path):
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("No GEMINI_API_KEY set: skipping AI descriptions.")
        return
    if not IMAGES.is_dir():
        return
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    site = config.get("site_title", "this business")
    about = config.get("ai_context") or config.get("site_description", "")
    state = {"models": [config.get("ai_model") or DEFAULT_MODEL], "discovered": False}
    done = 0

    for img in sorted(IMAGES.iterdir()):
        if img.suffix.lower() not in EXTENSIONS or not img.is_file():
            continue
        stem = img.with_suffix("")
        ai_path = Path(str(stem) + ".ai.txt")
        mine = parse_note(read(Path(str(stem) + ".txt")))
        robot = parse_note(read(ai_path))
        have_desc = mine.get("description") or robot.get("description")
        have_title = mine.get("title") or robot.get("title") or meaningful_name(img.stem)
        if have_desc and have_title:
            continue
        if done >= MAX_PER_RUN:
            print("Reached the per-run limit; the rest will be done next time.")
            return

        if not have_desc:
            parts = [{"text": PICTURE_PROMPT.format(site=site, about=about)},
                     {"inline_data": {"mime_type": "image/jpeg", "data": small_jpeg_b64(img)}}]
            text, err = run(parts, state, key)
            title, desc = split_answer(text)
            if len(desc) < 20:
                print(f"Could not describe {img.name}: {err or 'answer too short'}. Skipping.")
                continue
            robot["description"] = desc
            if title and not have_title:
                robot["title"] = title
        else:
            text, err = run([{"text": TITLE_PROMPT.format(site=site, about=about, desc=have_desc)}], state, key)
            title = clean_title(text)
            if not title:
                print(f"Could not write a title for {img.name}: {err or 'no usable answer'}. Skipping.")
                continue
            robot["title"] = title

        lines = [f"Title: {robot['title']}"] if robot.get("title") else []
        lines += ["", robot["description"]] if robot.get("description") else []
        ai_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        print(f"Wrote {ai_path.name}")
        done += 1


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never break the website build
        print(f"AI descriptions skipped: {e}")
