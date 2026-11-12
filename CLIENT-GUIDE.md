# Your Visual Archive: Client Guide

This guide explains how to add pictures to your website and Pinterest. No technical skills are needed.

## 1. Set your site details (config.json)

Your site's name and details are stored in one file, `config.json`. You change it on GitHub; no software is needed.

1. Open the project page on GitHub and tap or click **config.json**.
2. Tap the **pencil** icon (Edit this file).
3. Change only the text inside the quotation marks, for example:
   ```json
   {
     "site_title": "Harbor Ceramics",
     "author_name": "Harbor Ceramics Studio",
     "pinterest_handle": "harborceramics",
     "site_description": "Handmade stoneware, made in Kansas City."
   }
   ```
   - **site_title**: the name shown at the top of your website and in search results.
   - **author_name**: your business name, shown on each picture page.
   - **pinterest_handle**: your Pinterest username, without the @.
   - **site_description**: one or two sentences about your work. Keep the quotation marks.
4. Tap **Commit changes**. The site rebuilds in about a minute.

**Be careful with:** the quotation marks, the commas between lines, and the curly braces `{ }`. Leave out a comma or quote and the site will not update. If that happens, ask your web helper.

Do **not** change `base_url`. Your web helper sets it to your site's address.

## 2. Add a picture

You can do this from a computer or from a phone.

**From a computer or phone browser (GitHub website):**
1. Open the project page on GitHub.
2. Open the folder named **images**.
3. Tap **Add file → Upload files**.
4. Choose your picture (JPG, PNG or WEBP). Use a clear file name such as `blue-ceramic-vase.jpg`. The file name becomes the web address and the picture title.
5. Tap **Commit changes**.

**Tips:**
- Use JPG, PNG or WEBP files only.
- Names with words (`moon-serpent.jpg`) work better than numbers (`IMG_9283.jpg`).
- Pictures saved only in the cloud (Google Photos, iCloud) may not upload. Download a copy to your phone first.
- Keep each picture under about 5 MB. Most phone photos are close to that size. GitHub refuses files over 25 MB.
- You can select several pictures at once. Each picture becomes its own page, and its file name becomes the page title, so give each one a clear name.

### Add a Buy button and description (optional, but this is what makes sales)
Next to your picture, upload a small text file with the **same name** ending in `.txt` (for `blue-ceramic-vase.jpg`, name it `blue-ceramic-vase.txt`). Put any of these lines at the top, then a blank line, then a sentence or two about the picture:

```
Shop: https://your-shop.com/blue-vase
Price: $24
Button: Buy this vase

A glossy blue stoneware vase, thrown by hand in Kansas City.
```

- **Shop** puts a big **Buy** button on the picture's page that goes to that link. It must start with `https://`.
- **Price** shows next to the button. **Button** changes the button's words. **Title** sets the page title yourself.
- Every line is optional. If you leave out the description, the robot writes one (see below).

If you use the **upload page** (`/upload`) instead, just fill in the Shop link, Price and Description boxes. They do the same thing.

### The robot writer
If your web helper turned it on, the site uses a free AI to look at each new picture and write a title and description for you. Its draft is saved as `name.ai.txt`. Your own `name.txt` always wins, so to change the robot's words, either edit the `.ai.txt` file or write your own `.txt`.

## 3. Wait for the update

After you commit, the website rebuilds automatically. This usually takes **1 to 3 minutes**. You can check progress on the **Actions** tab of the project page. A green checkmark means it's done.

## 4. Check your live website

1. Open your website address (for example, `https://gallery.yourdomain.com`).
2. Your picture should appear in the gallery grid.
3. Tap the picture to see its own page.

If the picture does not appear after 5 minutes, check the **Actions** tab for a red X and contact your web helper.

## 5. Pinterest and the 24-hour window

Your website publishes an RSS feed at `https://gallery.yourdomain.com/rss.xml`. Pinterest reads this feed and can create a pin for each new picture automatically.

- Pinterest checks the feed about **once every 24 hours**. A new picture can take **up to 24 hours** to appear as a pin.
- Each pin links back to the picture's page on your website.
- Pinterest can publish up to about **200 pins a day** from the feed.

### Connect the feed to Pinterest (one time)
Pinterest changes its menus from time to time, so the names below may differ slightly. Use Pinterest's help center if you get stuck.
1. Log in to Pinterest with a **business account**. If you have a personal account, convert it in your account settings.
2. Claim your website domain in Pinterest's website settings (Pinterest gives you a short code to add to the site, or a file to upload).
3. Set up automatic pin creation from an RSS feed in Pinterest's publishing tools.
4. Paste `https://gallery.yourdomain.com/rss.xml` and choose a board.
5. Test it first on a **secret board** before using a public one.

Pictures appear as pins after Pinterest reads the feed, which happens about once a day.

## 6. Quick checklist

- [ ] Picture uploaded to the `images` folder
- [ ] Shop link added (a `.txt` file or the upload page's Shop box), so the page has a Buy button
- [ ] Green checkmark on the Actions tab
- [ ] Picture visible on the website
- [ ] Pin appears on Pinterest within 24 hours

Questions? Contact your web helper and include the picture name and the time you uploaded it.
