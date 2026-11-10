// Client upload endpoint: GET /upload serves a phone form, POST /upload stores a
// picture in R2 and asks GitHub to rebuild the site. Deployed with wrangler.

const MAX_BYTES = 10 * 1024 * 1024;     // 10 MB per picture
const OVERHEAD_BYTES = 64 * 1024;       // multipart envelope allowance
const ALLOWED = { jpg: "image/jpeg", png: "image/png", webp: "image/webp" };

// Must match slugify() in build.py so R2 names and the engine never drift.
// Python: unicodedata NFKD -> ascii (drop the rest) -> lowercase -> non [a-z0-9] runs to "-".
export function slugify(name) {
  const ascii = name.normalize("NFKD").replace(/[^\x00-\x7F]/g, "");
  const slug = ascii.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return slug || "image";
}

// Decide the real type from the file's first bytes, never from file.type or the name.
export function sniffType(bytes) {
  const b = bytes;
  if (b.length >= 3 && b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return "jpg";
  if (b.length >= 8 && [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a].every((v, i) => b[i] === v)) return "png";
  const tag = (from) => String.fromCharCode(...b.slice(from, from + 4));
  if (b.length >= 12 && tag(0) === "RIFF" && tag(8) === "WEBP") return "webp";
  return null;
}

export function buildKey(originalName, ext) {
  const stem = originalName.replace(/\.[^.]*$/, "");
  return `${slugify(stem)}.${ext}`;
}

// Constant-time comparison of two strings (both hashed so lengths never leak).
export async function tokenMatches(given, expected) {
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(given)),
    crypto.subtle.digest("SHA-256", enc.encode(expected)),
  ]);
  const x = new Uint8Array(a), y = new Uint8Array(b);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0 && given.length > 0;
}

async function uniqueKey(bucket, key) {
  if (!(await bucket.head(key))) return key;
  const dot = key.lastIndexOf(".");
  const suffix = [...crypto.getRandomValues(new Uint8Array(3))]
    .map((v) => v.toString(16).padStart(2, "0")).join("");
  return `${key.slice(0, dot)}-${suffix}${key.slice(dot)}`;
}

// Returns true when GitHub accepted the dispatch. A failure is not fatal:
// the picture is already in R2 and the scheduled build will pick it up.
async function dispatchBuild(env, key) {
  if (!env.GITHUB_TOKEN || !env.GITHUB_REPO) return false;
  const res = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "image-engine-upload",
    },
    body: JSON.stringify({ event_type: "image-uploaded", client_payload: { key } }),
  });
  return res.status === 204;
}

const text = (body, status) =>
  new Response(body, { status, headers: { "Content-Type": "text/plain;charset=UTF-8", "Cache-Control": "no-store" } });

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/upload") return text("Not found", 404);

    if (request.method === "GET") {
      return new Response(UPLOAD_HTML, {
        headers: { "Content-Type": "text/html;charset=UTF-8", "Cache-Control": "no-store" },
      });
    }
    if (request.method !== "POST") return text("Method not allowed", 405);

    // 1. Authenticate BEFORE reading the body, so strangers cannot make us parse uploads.
    const auth = request.headers.get("authorization") || "";
    const given = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
    if (!env.UPLOAD_TOKEN || !(await tokenMatches(given, env.UPLOAD_TOKEN))) {
      return text("Wrong or missing upload code.", 401);
    }

    // 2. Reject oversized bodies by declared length before reading anything.
    const declared = Number(request.headers.get("content-length") || 0);
    if (!declared || declared > MAX_BYTES + OVERHEAD_BYTES) {
      return text("That picture is too big. The limit is 10 MB.", 413);
    }

    try {
      const form = await request.formData();
      const file = form.get("image");
      if (!file || typeof file === "string") return text("No picture received.", 400);
      if (file.size > MAX_BYTES) return text("That picture is too big. The limit is 10 MB.", 413);

      // 3. Check the real file type from its bytes.
      const bytes = new Uint8Array(await file.arrayBuffer());
      const ext = sniffType(bytes);
      if (!ext) return text("Only JPG, PNG or WEBP pictures are accepted.", 415);

      // 4. Clean name, never overwrite an existing picture, store in R2.
      const key = await uniqueKey(env.IMAGE_BUCKET, buildKey(file.name || "image", ext));
      await env.IMAGE_BUCKET.put(key, bytes, { httpMetadata: { contentType: ALLOWED[ext] } });

      // 5. Ask GitHub to rebuild the site.
      const started = await dispatchBuild(env, key);
      return text(
        started
          ? "Uploaded. It should appear on the site within a few minutes."
          : "Uploaded. It will appear on the site at the next scheduled update.",
        200,
      );
    } catch (err) {
      console.error("upload failed:", err && err.message);
      return text("Upload failed. Please try again.", 500);
    }
  },
};

const UPLOAD_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex,nofollow">
<title>Upload a picture</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px;
         background: #f5f5f7; color: #1d1d1f; }
  .card { max-width: 420px; margin: 0 auto; background: #fff; padding: 22px; border-radius: 12px;
          box-shadow: 0 4px 14px rgba(0,0,0,.06); }
  label { display: block; font-weight: 600; margin-top: 16px; }
  input, button { width: 100%; box-sizing: border-box; font-size: 16px; padding: 12px; margin-top: 8px;
                  border: 1px solid #ccc; border-radius: 8px; }
  button { background: #111; color: #fff; border: none; font-weight: 600; margin-top: 22px; }
  button[disabled] { opacity: .5; }
  #msg { margin-top: 16px; min-height: 1.4em; }
  p.note { color: #6e6e73; font-size: 14px; }
</style>
</head>
<body>
<div class="card">
  <h2>Upload a picture</h2>
  <p class="note">JPG, PNG or WEBP, up to 10 MB. Ask your web helper for the upload code.</p>
  <form id="upload-form">
    <label for="code">Upload code</label>
    <input id="code" type="password" autocomplete="off" required>
    <label for="picture">Picture</label>
    <input id="picture" type="file" accept="image/jpeg,image/png,image/webp" required>
    <button id="send" type="submit">Upload</button>
  </form>
  <div id="msg" role="status"></div>
</div>
<script>
(function () {
  var form = document.getElementById("upload-form");
  var codeBox = document.getElementById("code");
  var pictureBox = document.getElementById("picture");
  var sendBtn = document.getElementById("send");
  var msg = document.getElementById("msg");
  try { codeBox.value = localStorage.getItem("uploadCode") || ""; } catch (e) {}

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var code = codeBox.value.trim();
    var file = pictureBox.files[0];
    if (!code || !file) { msg.textContent = "Enter the code and choose a picture."; return; }
    try { localStorage.setItem("uploadCode", code); } catch (err) {}
    var data = new FormData();
    data.append("image", file);
    sendBtn.disabled = true;
    msg.textContent = "Uploading… please keep this page open.";
    fetch("/upload", { method: "POST", headers: { Authorization: "Bearer " + code }, body: data })
      .then(function (res) { return res.text().then(function (t) { return { ok: res.ok, text: t }; }); })
      .then(function (r) { msg.textContent = r.text; if (r.ok) pictureBox.value = ""; })
      .catch(function () { msg.textContent = "Could not reach the server. Check your connection and try again."; })
      .then(function () { sendBtn.disabled = false; });
  });
})();
</script>
</body>
</html>`;
