import { test } from "node:test";
import assert from "node:assert/strict";
import worker, { slugify, sniffType, buildKey } from "../src/index.js";

const JPEG = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0, 16, 0x4a, 0x46, 0x49, 0x46, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0]);
const PNG = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 13, 0x49, 0x48, 0x44, 0x52]);
const WEBP = new Uint8Array([...Buffer.from("RIFF"), 0, 0, 0, 0, ...Buffer.from("WEBP"), 0, 0, 0, 0]);

function fakeBucket(existing = []) {
  const stored = {};
  return {
    stored,
    async head(key) { return existing.includes(key) || key in stored ? { key } : null; },
    async put(key, body, opts) { stored[key] = { body, opts }; },
  };
}

// Builds an upload as the Workers runtime sees it: a browser always sends Content-Length,
// which Node's Request hides, so the helper supplies it.
async function uploadRequest({ token = "good-token", bytes = JPEG, name = "photo.jpg", type = "image/jpeg" } = {}) {
  const form = new FormData();
  form.append("image", new File([bytes], name, { type }));
  const headers = {};
  if (token !== null) headers.Authorization = `Bearer ${token}`;
  const req = new Request("https://gallery.example.com/upload", { method: "POST", headers, body: form });
  const length = (await req.clone().arrayBuffer()).byteLength;
  return {
    method: req.method,
    url: req.url,
    headers: { get: (k) => (k.toLowerCase() === "content-length" ? String(length) : req.headers.get(k)) },
    formData: () => req.formData(),
  };
}

const env = (bucket, extra = {}) => ({ UPLOAD_TOKEN: "good-token", IMAGE_BUCKET: bucket, GITHUB_REPO: "", GITHUB_TOKEN: "", ...extra });

test("slugify matches the rules in build.py", () => {
  assert.equal(slugify("My Summer Product (1)"), "my-summer-product-1");
  assert.equal(slugify("Café Été!"), "cafe-ete");
  assert.equal(slugify("!!!"), "image");
  assert.equal(slugify("moon_serpent"), "moon-serpent");
});

test("slugify agrees with build.py on a batch of names", async () => {
  const names = ["My Summer Product (1)", "Café Été!", "IMG_9283", "serpent-bearer", "  spaced  out  ", "Ünïcödé 2026", "a.b.c", "x--y"];
  const { execFileSync } = await import("node:child_process");
  const py = `import json,sys,build;print(json.dumps([build.slugify(n) for n in json.loads(sys.stdin.read())]))`;
  const pyOut = JSON.parse(execFileSync("python3", ["-c", py], {
    input: JSON.stringify(names), cwd: new URL("../../", import.meta.url).pathname, encoding: "utf8",
  }));
  assert.deepEqual(names.map(slugify), pyOut);
});

test("sniffType reads real file signatures, not claimed types", () => {
  assert.equal(sniffType(JPEG), "jpg");
  assert.equal(sniffType(PNG), "png");
  assert.equal(sniffType(WEBP), "webp");
  assert.equal(sniffType(new TextEncoder().encode("<html>not a picture</html>")), null);
});

test("buildKey gives a clean name with the real extension", () => {
  assert.equal(buildKey("My Summer Product (1).JPG", "jpg"), "my-summer-product-1.jpg");
  assert.equal(buildKey("photo.exe", "png"), "photo.png");
  assert.equal(buildKey("", "webp"), "image.webp");
});

test("GET /upload serves the form", async () => {
  const res = await worker.fetch(new Request("https://gallery.example.com/upload"), env(fakeBucket()));
  assert.equal(res.status, 200);
  assert.match(await res.text(), /upload-form/);
});

test("rejects a missing or wrong token before reading the body", async () => {
  const bucket = fakeBucket();
  assert.equal((await worker.fetch(await uploadRequest({ token: null }), env(bucket))).status, 401);
  assert.equal((await worker.fetch(await uploadRequest({ token: "wrong" }), env(bucket))).status, 401);
  assert.deepEqual(bucket.stored, {});
});

test("refuses everything when no upload token is configured", async () => {
  const res = await worker.fetch(await uploadRequest({ token: "" }), env(fakeBucket(), { UPLOAD_TOKEN: "" }));
  assert.equal(res.status, 401);
});

test("rejects a disguised file: a text file named .jpg", async () => {
  const bucket = fakeBucket();
  const res = await worker.fetch(await uploadRequest({ bytes: new TextEncoder().encode("hello world, not an image"), name: "evil.jpg" }), env(bucket));
  assert.equal(res.status, 415);
  assert.deepEqual(bucket.stored, {});
});

test("stores a valid picture under a clean name, using the real type", async () => {
  const bucket = fakeBucket();
  // A PNG uploaded as "Summer Shot (2).JPG" is stored as .png, with the matching content type.
  const res = await worker.fetch(await uploadRequest({ bytes: PNG, name: "Summer Shot (2).JPG", type: "image/jpeg" }), env(bucket));
  assert.equal(res.status, 200);
  assert.ok(bucket.stored["summer-shot-2.png"], Object.keys(bucket.stored).join(","));
  assert.equal(bucket.stored["summer-shot-2.png"].opts.httpMetadata.contentType, "image/png");
});

test("never overwrites an existing picture", async () => {
  const bucket = fakeBucket(["photo.jpg"]);
  const res = await worker.fetch(await uploadRequest({ name: "photo.jpg" }), env(bucket));
  assert.equal(res.status, 200);
  const keys = Object.keys(bucket.stored);
  assert.equal(keys.length, 1);
  assert.match(keys[0], /^photo-[0-9a-f]{6}\.jpg$/);
});

test("rejects a declared body over the size limit", async () => {
  const req = new Request("https://gallery.example.com/upload", {
    method: "POST",
    headers: { Authorization: "Bearer good-token", "Content-Length": String(11 * 1024 * 1024) },
    body: "x",
  });
  assert.equal((await worker.fetch(req, env(fakeBucket()))).status, 413);
});

test("rejects a file over 10 MB even if the envelope is small", async () => {
  const big = new Uint8Array(10 * 1024 * 1024 + 1);
  big.set(JPEG, 0);
  const bucket = fakeBucket();
  const res = await worker.fetch(await uploadRequest({ bytes: big }), env(bucket));
  assert.equal(res.status, 413);
  assert.deepEqual(bucket.stored, {});
});

test("still succeeds when the GitHub dispatch fails, and says so", async () => {
  const bucket = fakeBucket();
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response("nope", { status: 500 });
  try {
    const res = await worker.fetch(await uploadRequest(), env(bucket, { GITHUB_REPO: "o/r", GITHUB_TOKEN: "t" }));
    assert.equal(res.status, 200);
    assert.match(await res.text(), /next scheduled update/);
    assert.equal(Object.keys(bucket.stored).length, 1);
  } finally {
    globalThis.fetch = realFetch;
  }
});

test("sends a repository_dispatch when configured", async () => {
  const bucket = fakeBucket();
  const realFetch = globalThis.fetch;
  let call;
  globalThis.fetch = async (url, init) => { call = { url, init }; return new Response(null, { status: 204 }); };
  try {
    const res = await worker.fetch(await uploadRequest(), env(bucket, { GITHUB_REPO: "o/r", GITHUB_TOKEN: "t" }));
    assert.match(await res.text(), /few minutes/);
    assert.equal(call.url, "https://api.github.com/repos/o/r/dispatches");
    assert.equal(JSON.parse(call.init.body).event_type, "image-uploaded");
  } finally {
    globalThis.fetch = realFetch;
  }
});
