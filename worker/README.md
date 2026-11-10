# Client photo upload (Worker + R2)

A client opens `https://<their-site>/upload` on a phone, enters the upload code, picks a picture and taps **Upload**. The picture goes to a private Cloudflare R2 bucket, and GitHub rebuilds the site with it. Pictures never enter git history.

```
phone → Worker (/upload) → R2 bucket
                 └─ repository_dispatch → GitHub Action → sync R2 to images/ → build.py → output/ → Cloudflare Pages
```

## What the Worker checks
- **Upload code first:** a 32+ character secret checked in constant time, before the body is read.
- **Size:** 10 MB per picture, rejected by declared length and again by file size.
- **Real file type:** JPG, PNG or WEBP, detected from the file's first bytes. The name and browser-declared type are ignored.
- **Clean name:** the same slug rules as `build.py`, so `My Summer Product (1).JPG` becomes `my-summer-product-1.jpg`. An existing name is never overwritten.
- **Build trigger:** a `image-uploaded` dispatch to GitHub. If it fails, the picture is still saved and the scheduled build (every 6 hours) picks it up.

## One-time setup

1. **Create the R2 bucket** in the Cloudflare dashboard (R2 → Create bucket). Name it for the client, e.g. `acme-pictures`.
2. **Make the bucket's files public** for the site. Either attach a custom domain such as `pics.clientdomain.com` (R2 → bucket → Settings → Public access), or enable the `r2.dev` public URL. Note the address; this is `R2_PUBLIC_URL`.
3. **Create an R2 API token** (R2 → Manage R2 API tokens → Object Read & Write, limited to that bucket). Note the Access Key ID, Secret Access Key and the S3 endpoint `https://<account-id>.r2.cloudflarestorage.com`.
4. **Create a GitHub token for the dispatch.** Use a fine-grained token limited to the client's repo with **Contents: Read and write**. (A repository_dispatch needs write access to contents.)
5. **Edit `wrangler.toml`:** set `bucket_name` to the bucket from step 1 and `GITHUB_REPO` to `owner/repo`.
6. **Set the Worker secrets** (run from `worker/`, with Wrangler logged in):
   ```bash
   npx wrangler secret put UPLOAD_TOKEN   # paste a long random code, e.g. from: openssl rand -base64 24
   npx wrangler secret put GITHUB_TOKEN   # the token from step 4
   npx wrangler deploy
   ```
7. **Route `/upload` on the client's site domain** to this Worker. In Workers → your Worker → Settings → Domains & Routes, add `clientdomain.com/upload*` (the site's Pages project keeps serving everything else).
8. **Set the GitHub repo secrets and variable** (Settings → Secrets and variables → Actions):
   - Secrets: `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`
   - Variable: `R2_PUBLIC_URL` (the public address from step 2, no trailing slash)
9. **Turn on rate limiting** for `/upload` in Cloudflare (Security → WAF → Rate limiting rules), e.g. 10 requests per minute per IP. This is in addition to the upload code.
10. **Run the Build gallery workflow once** by hand (Actions → Build gallery → Run workflow) to confirm it syncs and builds with no errors.

## Testing
```bash
npm test          # Worker unit tests (Node 22+); includes a slug check against build.py
```

## Limits to know about
- **iPhone photos:** iPhones often save photos as HEIC. The upload form asks for JPG/PNG/WEBP, and iOS usually converts when the picker is limited this way, but if a client gets "Only JPG, PNG or WEBP", have them choose **Settings → Camera → Formats → Most Compatible**.
- **10 MB per picture.** Raise `MAX_BYTES` in `src/index.js` if clients need more, and check the Worker request limits in the Cloudflare docs.
- **The code is shared by hand.** Anyone with it can upload until you change `UPLOAD_TOKEN` (`wrangler secret put UPLOAD_TOKEN`).
