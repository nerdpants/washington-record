# The Washington Record

Source for **https://washingtonrecord.net**, hosted on Netlify, edited through Decap CMS.

## For editors

1. Go to **https://washingtonrecord.net/admin/** and sign in.
2. **Articles → New Article.** Fill in headline, subheadline, summary, desk, byline, date and the story.
3. Click **Save**. The story is now a *Draft* (on the **Workflow** tab).
4. Move it to **In review** when it's ready for an editor, then **Ready**.
5. Open it and click **Publish → Publish now**. The site updates in about a minute.

Newest stories lead the homepage (4 in the sidebar, the next 6 as cards) and appear on
Newsroom, Investigations, site search and the RSS feed automatically.

Linking a case file: select text, click the link button, enter `/cases/C030.html`.

## How it works

```
content/articles/*.md   ← stories (what the editor writes)
static/                 ← everything else on the site, copied as-is
static/admin/           ← the editor (Decap CMS) and its settings (config.yml)
tools/build.py          ← turns stories into pages; Netlify runs it on every publish
tools/templates/        ← the article page layout
public/                 ← build output (not committed)
```

Pages that list stories contain `<!--wr:name-->…<!--/wr:name-->` markers; `build.py`
fills them. Don't remove those markers when editing `index.html`, `newsroom.html` or
`investigations.html`.

If a story is missing a required field the build stops and the live site stays as it was;
the reason is shown in Netlify under **Deploys**.

Build locally:

```
pip install -r requirements.txt
python3 tools/build.py      # output in public/
```

## One-time Netlify setup

1. **Site configuration → Build & deploy → Continuous deployment → Link repository** →
   pick this GitHub repo. Build settings are read from `netlify.toml`.
2. **Project configuration → Identity → Enable Identity.**
   - Registration: **Invite only**.
   - Services → **Git Gateway → Enable**.
3. **Identity → Invite users** for each editor. They get an email, set a password and land in `/admin/`.
