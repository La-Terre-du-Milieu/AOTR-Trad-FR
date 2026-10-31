"""Différences entre deux VO : clés ajoutées, modifiées, supprimées (avec la FR actuelle).

C'est la liste de travail d'une mise à jour : seules les lignes « ajoutée » et « modifiée »
sont à traduire.

Usage : python tools/diff_versions.py <ancienne_vo.str> <nouvelle_vo.str> <fr.str> [sortie.csv]
"""
import csv
import sys

import strfile


def diff(old_path, new_path, fr_path):
    old, new, fr = (strfile.read(p).index() for p in (old_path, new_path, fr_path))
    rows = []
    for k, e in new.items():
        f = fr[k].text if k in fr else ''
        if k not in old:
            rows.append(('ajoutée', e.key, '', e.text, f))
        elif old[k].text != e.text:
            rows.append(('modifiée', e.key, old[k].text, e.text, f))
    for k, e in old.items():
        if k not in new:
            rows.append(('supprimée', e.key, e.text, '', fr[k].text if k in fr else ''))
    return rows


if __name__ == '__main__':
    rows = diff(*sys.argv[1:4])
    for status in ('ajoutée', 'modifiée', 'supprimée'):
        print(f'{status:10} {sum(r[0] == status for r in rows)}')
    if len(sys.argv) > 4:
        with open(sys.argv[4], 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['statut', 'clé', 'VO ancienne', 'VO nouvelle', 'FR actuelle'])
            w.writerows(rows)
        print('liste :', sys.argv[4])
    else:
        for r in rows:
            print(' | '.join(x[:120] for x in r))
