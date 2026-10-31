"""Contrôle d'un .str FR par rapport à sa VO.

Usage : python tools/check.py <fr.str> <vo.str> [rapport.csv]
"""
import csv
import re
import sys

import strfile
from rules import NBSP, hotkeys, placeholders

_LONG_WORDS = re.compile(r'[A-Za-z]{4,} [A-Za-z]{3,}')


def check(fr_path, en_path):
    fr, en = strfile.read(fr_path), strfile.read(en_path)
    fi, ei = fr.index(), en.index()
    rows = []
    for line, msg in fr.problems:
        rows.append(('format', f'ligne {line}', '', '', msg))
    for d in fr.duplicates():
        first = fi[d.lkey]
        if first.text != d.text:
            rows.append(('doublon_different', d.key, '', first.text, f'ligne {d.line} : {d.text[:80]}'))
        else:
            rows.append(('doublon', d.key, '', '', f'lignes {first.line} et {d.line}'))
    for k, e in ei.items():
        f = fi.get(k)
        if f is None:
            rows.append(('manquante', e.key, e.text, '', ''))
            continue
        if placeholders(e.text) != placeholders(f.text):
            rows.append(('placeholder', e.key, e.text, f.text, f'{placeholders(e.text)} != {placeholders(f.text)}'))
        if hotkeys(e.text) != hotkeys(f.text):
            rows.append(('raccourci_&', e.key, e.text, f.text, f'{hotkeys(e.text)} & en VO, {hotkeys(f.text)} en FR'))
        if f.text == e.text and _LONG_WORDS.search(e.text):
            rows.append(('identique_vo', e.key, e.text, f.text, ''))
    for k, f in fi.items():
        if k not in ei:
            rows.append(('obsolete', f.key, '', f.text, ''))
    typo = {
        'insécable': sum(t.count(NBSP + c) for t in (f.text for f in fr.entries) for c in '?!:;'),
        'espace normale': sum(t.count(' ' + c) for t in (f.text for f in fr.entries) for c in '?!'),
    }
    return rows, typo


if __name__ == '__main__':
    rows, typo = check(sys.argv[1], sys.argv[2])
    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    for k, v in sorted(counts.items()):
        print(f'{k:20} {v}')
    print('typographie        ', typo)
    if len(sys.argv) > 3:
        with open(sys.argv[3], 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['type', 'clé', 'VO', 'FR', 'détail'])
            w.writerows(rows)
        print('rapport :', sys.argv[3])
