"""Construit glossaire.csv à partir de la traduction existante.

Prend les noms courts (unités, héros, bâtiments, améliorations, armées, cartes) et regroupe
les traductions d'un même terme VO. Un terme traduit de plusieurs façons est « à arbitrer » :
la variante la plus fréquente est proposée, les autres sont listées.

Usage : python tools/glossary.py <fr.str> <vo.str> [glossaire.csv]
"""
import csv
import re
import sys
from collections import Counter, defaultdict

import strfile

PREFIXES = ('object:', 'upgrade:', 'lwa:', 'bannerui:', 'campaignname:', 'tooltip:cahclasses_')
NAME = re.compile(r"^[^%\\\n&]{2,40}$")


def build(fr_path, en_path):
    fr, en = strfile.read(fr_path).index(), strfile.read(en_path).index()
    variants = defaultdict(Counter)
    for k, e in en.items():
        if k.startswith(PREFIXES) and k in fr and NAME.match(e.text) and len(e.text.split()) <= 5:
            f = fr[k].text.strip().rstrip('*')
            variants[e.text.strip().rstrip('*')][f] += 1
    rows = []
    for vo, c in variants.items():
        (best, n), *others = c.most_common()
        status = 'à arbitrer' if others else ('identique VO' if best == vo else 'ok')
        rows.append((vo, best, ' | '.join(f'{v} ({m})' for v, m in others), sum(c.values()), status))
    order = {'à arbitrer': 0, 'identique VO': 1, 'ok': 2}
    return sorted(rows, key=lambda r: (order[r[4]], -r[3], r[0].lower()))


if __name__ == '__main__':
    rows = build(sys.argv[1], sys.argv[2])
    for s in ('à arbitrer', 'identique VO', 'ok'):
        print(f'{s:13} {sum(r[4] == s for r in rows)}')
    out = sys.argv[3] if len(sys.argv) > 3 else 'glossaire.csv'
    with open(out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['VO', 'FR retenue', 'autres variantes (occurrences)', 'occurrences', 'statut'])
        w.writerows(rows)
    print('glossaire :', out)
