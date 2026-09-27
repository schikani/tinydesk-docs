"""check_links.py - check the relative links (and #anchors) of the Docsify site.

    python tools/check_links.py [site folder, default: ../site]
"""
import os
import re

import sys

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'site')).replace(os.sep, '/')


def slug(h):
    # Docsify's slugify: lower case, drop HTML tags and most punctuation, spaces to '-'
    s = re.sub(r'<[^>]+>', '', h).strip().lower()
    s = re.sub(r'[\s]+', '-', s)
    s = re.sub(r'[^\w\-\u4e00-\u9fa5]', '', s)
    return s


def headings(path):
    ids = set()
    in_code = False
    for line in open(path, encoding='utf-8'):
        if line.startswith('```'):
            in_code = not in_code
        if in_code:
            continue
        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            ids.add(slug(m.group(2).replace('`', '')))
    return ids


pages = {}
for d, _, files in os.walk(ROOT):
    for f in files:
        if f.endswith('.md'):
            p = os.path.join(d, f).replace('\\', '/')
            pages[p] = headings(p)

bad = 0
for p in pages:
    text = open(p, encoding='utf-8').read()
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    for m in re.finditer(r'\]\(([^)\s]+)\)', text):
        href = m.group(1)
        if re.match(r'^(https?:|mailto:)', href) or href == '/':
            continue
        target, _, anchor = href.partition('#')
        if '?id=' in target:
            target, _, anchor = target.partition('?id=')
        if target.startswith('/'):
            full = ROOT + target
        elif target == '':
            full = p
        else:
            full = os.path.normpath(os.path.join(os.path.dirname(p), target)).replace('\\', '/')
        if not full.endswith('.md'):
            continue
        if full not in pages:
            print('%s: missing page %s' % (p[len(ROOT) + 1:], href))
            bad += 1
        elif anchor and anchor not in pages[full]:
            print('%s: missing anchor %s' % (p[len(ROOT) + 1:], href))
            bad += 1
print('%d pages, %d problems' % (len(pages), bad))
sys.exit(1 if bad else 0)
