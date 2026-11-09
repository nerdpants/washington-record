#!/usr/bin/env python3
"""Build The Washington Record.

Copies static/ to public/, then generates everything that depends on the
articles in content/articles/*.md (written by editors through /admin):

  articles/<slug>.html, the homepage story lists, newsroom.html,
  investigations.html, feed.xml, sitemap.xml and assets/articles.js (site search).

Netlify runs this on every publish (see netlify.toml). Locally:
    pip install -r requirements.txt && python3 tools/build.py
"""
import html, json, re, shutil, sys
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo('America/New_York')
except Exception:  # tzdata missing
    LOCAL_TZ = timezone.utc

import markdown
import yaml

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / 'static'
CONTENT = ROOT / 'content' / 'articles'
OUT = ROOT / 'public'
TEMPLATE = ROOT / 'tools' / 'templates' / 'article.html'
DOMAIN = 'https://washingtonrecord.net'
BRAND = 'The Washington Record'
REQUIRED = ['title', 'dek', 'summary', 'section', 'date']
EVIDENCE_NOTE = ('<div class="article-notice"><strong>Evidence note:</strong> This article describes documented '
                 'official actions alongside allegations, disputes and unanswered questions. Mention does not imply '
                 'guilt. Follow the linked case files to review sources and qualifications.</div>')

esc = lambda v: html.escape(str(v if v is not None else ''), quote=True)


def fail(msg):
    print(f'\nBUILD FAILED: {msg}\n(The live site was left unchanged.)\n', file=sys.stderr)
    sys.exit(1)


def parse_date(v, where):
    if isinstance(v, datetime):
        d = v
    elif isinstance(v, date):
        d = datetime(v.year, v.month, v.day, 12)
    else:
        try:
            d = datetime.fromisoformat(str(v).strip().replace('Z', '+00:00'))
        except ValueError:
            fail(f'{where}: date "{v}" is not a valid date')
    d = d if d.tzinfo else d.replace(tzinfo=LOCAL_TZ)
    return d.astimezone(LOCAL_TZ)


def long_date(d):
    return f'{d:%B} {d.day}, {d.year}'


def render_markdown(text):
    out = markdown.markdown(text or '', extensions=['extra', 'sane_lists', 'smarty'], output_format='html')
    # External links open in a new tab; site links stay root-relative.
    out = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener noreferrer"', out)
    return out


def load_articles():
    arts = []
    for f in sorted(CONTENT.glob('*.md')):
        raw = f.read_text(encoding='utf-8')
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)$', raw, re.S)
        if not m:
            fail(f'{f.name}: missing the --- front matter block')
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            fail(f'{f.name}: {e}')
        if meta.get('draft'):
            continue
        missing = [k for k in REQUIRED if not str(meta.get(k) or '').strip()]
        if missing:
            fail(f'{f.name}: missing {", ".join(missing)}')
        slug = re.sub(r'[^a-z0-9-]+', '-', f.stem.lower()).strip('-')
        d = parse_date(meta['date'], f.name)
        arts.append({
            'slug': slug,
            'title': str(meta['title']).strip(),
            'dek': str(meta['dek']).strip(),
            'summary': str(meta['summary']).strip(),
            'section': str(meta['section']).strip(),
            'label': str(meta.get('label') or meta['section']).strip(),
            'author': str(meta.get('author') or 'The Washington Record staff').strip(),
            'date': d,
            'notice': meta.get('evidence_note', True) is not False,
            'weight': int(meta.get('weight') or 0),
            'body': render_markdown(m.group(2)),
            'url': f'articles/{slug}.html',
        })
    if not arts:
        fail('no articles found in content/articles')
    # Newest first; articles published at the same moment keep their weight order.
    arts.sort(key=lambda a: (-a['date'].timestamp(), a['weight'], a['title']))
    return arts


def replace_marker(s, name, value, page):
    pat = re.compile(rf'(<!--wr:{name}-->).*?(<!--/wr:{name}-->)', re.S)
    if not pat.search(s):
        fail(f'{page}: marker wr:{name} is missing')
    return pat.sub(lambda m: m.group(1) + value + m.group(2), s, count=1)


def edit(path, **markers):
    p = OUT / path
    s = p.read_text(encoding='utf-8')
    for k, v in markers.items():
        s = replace_marker(s, k.replace('_', '-'), v, path)
    p.write_text(s, encoding='utf-8')


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(STATIC, OUT)
    arts = load_articles()
    tpl = TEMPLATE.read_text(encoding='utf-8')
    (OUT / 'articles').mkdir(exist_ok=True)

    # ---- article pages ----
    for i, a in enumerate(arts):
        related = [arts[j] for j in (i - 1, i + 1) if 0 <= j < len(arts)]
        rel = ''.join(f'<li><a href="../{esc(r["url"])}">{esc(r["title"])}</a></li>' for r in related)
        jsonld = json.dumps({
            '@context': 'https://schema.org', '@type': 'NewsArticle', 'headline': a['title'],
            'description': a['summary'], 'datePublished': a['date'].isoformat(), 'dateModified': a['date'].isoformat(),
            'author': {'@type': 'Organization', 'name': a['author']},
            'mainEntityOfPage': f'{DOMAIN}/{a["url"]}',
            'publisher': {'@type': 'Organization', 'name': BRAND, 'url': DOMAIN}, 'isAccessibleForFree': True,
        }, ensure_ascii=False).replace('</', '<\\/')
        vals = {
            'title': esc(a['title']), 'summary': esc(a['summary']), 'url': esc(f'{DOMAIN}/{a["url"]}'),
            'jsonld': jsonld, 'section': esc(a['section']), 'label': esc(a['label']), 'dek': esc(a['dek']),
            'author': esc(a['author']), 'date_display': esc(long_date(a['date'])),
            'notice': EVIDENCE_NOTE if a['notice'] else '', 'body': a['body'], 'related': rel,
        }
        page = re.sub(r'\{\{(\w+)\}\}', lambda m: vals[m.group(1)], tpl)
        (OUT / a['url']).write_text(page, encoding='utf-8')

    # ---- homepage: 4 newest in the sidebar, next 6 as cards ----
    rail = arts[:4]
    cards = arts[4:10] if len(arts) > 4 else []
    edit('index.html',
         front_rail=''.join(
             f'<a class="headline-row" href="{esc(a["url"])}"><span class="kicker">{esc(a["section"])}</span>'
             f'<strong>{esc(a["title"])}</strong><span class="minor">{esc(a["summary"])}</span></a>' for a in rail),
         story_cards=''.join(
             f'<article class="story-card"><span class="eyebrow">{esc(a["section"])}</span><h3><a href="{esc(a["url"])}">'
             f'{esc(a["title"])}</a></h3><p>{esc(a["summary"])}</p><a class="story-card-link" href="{esc(a["url"])}">'
             f'Read the story <span aria-hidden="true">↗</span></a></article>' for a in cards),
         dateline=esc(f'{arts[0]["date"]:%A}, {long_date(arts[0]["date"])}'))

    edit('newsroom.html', newsroom=''.join(
        f'<a class="newsroom-story" href="{esc(a["url"])}"><span class="eyebrow">{esc(a["section"])}<br>'
        f'<small>{esc(long_date(a["date"]))}</small></span><div><h2>{esc(a["title"])}</h2><p>{esc(a["summary"])}</p></div>'
        f'<span class="story-arrow">↗</span></a>' for a in arts))

    edit('investigations.html', inv_count=str(len(arts)), inv_cards=''.join(
        f'<a class="inv-card" href="{esc(a["url"])}"><span class="eyebrow">{esc(a["section"])}</span><h3>{esc(a["title"])}</h3>'
        f'<p>{esc(a["summary"])}</p><span class="link-arrow">Read story ↗</span></a>' for a in arts))

    # ---- site search index ----
    idx = [['Where Business Meets Government', 'special-report.html', 'Cover investigation']] + \
          [[a['title'] + ' — ' + a['dek'], a['url'], a['label']] for a in arts]
    (OUT / 'assets' / 'articles.js').write_text(
        'window.WR_ARTICLES=' + json.dumps(idx, ensure_ascii=False).replace('</', '<\\/') + ';\n', encoding='utf-8')

    # ---- RSS ----
    items = ''.join(
        f'<item><title>{esc(a["title"])}</title><link>{DOMAIN}/{a["url"]}</link><guid>{DOMAIN}/{a["url"]}</guid>'
        f'<pubDate>{format_datetime(a["date"])}</pubDate><description>{esc(a["summary"])}</description></item>' for a in arts)
    (OUT / 'feed.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>The Washington Record</title>'
        f'<link>{DOMAIN}</link><description>Documentary public-record journalism</description><language>en-us</language>'
        f'{items}</channel></rss>', encoding='utf-8')

    # ---- sitemap: keep non-article URLs, regenerate article URLs ----
    sm = (OUT / 'sitemap.xml').read_text(encoding='utf-8')
    sm = re.sub(r'<url><loc>[^<]*/articles/[^<]*</loc>.*?</url>\n?', '', sm)
    new = ''.join(f'<url><loc>{DOMAIN}/{a["url"]}</loc><lastmod>{a["date"]:%Y-%m-%d}</lastmod></url>\n' for a in arts)
    sm = sm.replace('</urlset>', new + '</urlset>')
    (OUT / 'sitemap.xml').write_text(sm, encoding='utf-8')

    print(f'Built {len(arts)} articles into {OUT.relative_to(ROOT)}/')


if __name__ == '__main__':
    main()
