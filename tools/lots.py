"""Découpe une mise à jour en lots de traduction, puis réinjecte les traductions.

  python tools/lots.py decoupe <dossier_lots> <liste_tm.csv>… --nous <vo> <fr> [--nous <vo> <fr>…]
      Entrées « ajoutée » / « modifiée » sans proposition sûre de memoire.py -> lot_NN.csv
      (clé ; fichier ; statut ; VO ancienne ; VO nouvelle ; FR actuelle ; réf VO ; réf FR)
      + lot_NN_glossaire.csv (termes du glossaire présents dans le lot).
      « réf » = traduction existante la plus proche (même formulation), pour garder le style.
      Les entrées d'un même fichier restent ensemble et dans l'ordre (contexte des dialogues).

  python tools/lots.py reinjecte <dossier_lots> <dossier_sortie> <liste_tm.csv>…
      Réunit les propositions de memoire.py et les lot_NN_fr.csv (clé ; fichier ; FR) en
      <sortie>/lotr.str et <sortie>/maps/<map>/map.str, à passer ensuite dans rebuild.py.

  python tools/lots.py verifie <dossier_lots>/lot_NN.csv
      Contrôle lot_NN_fr.csv : toutes les clés, placeholders, &, \\n, cp1252, guillemets.
"""
import csv
import glob
import os
import re
import sys

import rules
import strfile
from memoire import read_pairs

MAX_ENTRIES = 250
MAX_WORDS = 3000
WORD = re.compile(r"[a-zà-ÿ']{3,}")


def source_file(tm_path):
    """'lotr' pour la liste de lotr.str, sinon le nom de la map."""
    name = os.path.basename(tm_path)[:-len('_tm.csv')]
    return 'lotr' if name.startswith('diff_') else name


def read_tm(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return [r for r in csv.DictReader(f, delimiter=';') if r['statut'] != 'supprimée']


class Reference:
    """Traduction existante la plus proche d'un texte (similarité de Jaccard sur les mots)."""

    def __init__(self, pairs):
        self.pairs, self.index = [], {}
        seen = set()
        for _, en, fr in pairs:
            words = frozenset(WORD.findall(en.lower()))
            if len(words) < 2 or en in seen:
                continue
            seen.add(en)
            for w in words:
                self.index.setdefault(w, []).append(len(self.pairs))
            self.pairs.append((words, en, fr))

    def find(self, text, threshold=0.5):
        words = set(WORD.findall(text.lower()))
        scores = {}
        for w in words:
            ids = self.index.get(w, ())
            if len(ids) < 400:                     # mots trop fréquents : peu discriminants
                for i in ids:
                    scores[i] = scores.get(i, 0) + 1
        best, score = None, threshold
        for i, common in scores.items():
            s = common / len(words | self.pairs[i][0])
            if s >= score:
                best, score = i, s
        return self.pairs[best][1:] if best is not None else ('', '')


def glossary_terms(texts):
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'glossaire.csv'),
              encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f, delimiter=';'))
    blob = '\n'.join(texts).lower()
    return [r for r in rows if re.search(r'\b' + re.escape(r['VO'].lower()) + r'\b', blob)]


def decoupe(out_dir, tm_paths, ours):
    ref = Reference(p for vo, fr in ours for p in read_pairs(vo, fr))
    todo = []
    for path in tm_paths:
        for r in read_tm(path):
            if r['FR proposée'] and not r['alerte']:
                continue
            r['fichier'] = source_file(path)
            r['réf VO'], r['réf FR'] = ref.find(r['VO nouvelle'])
            todo.append(r)
    lots, cur, words = [], [], 0
    for r in todo:
        n = len(r['VO nouvelle'].split())
        if cur and (len(cur) >= MAX_ENTRIES or words + n > MAX_WORDS):
            lots.append(cur)
            cur, words = [], 0
        cur.append(r)
        words += n
    if cur:
        lots.append(cur)
    os.makedirs(out_dir, exist_ok=True)
    cols = ['clé', 'fichier', 'statut', 'VO ancienne', 'VO nouvelle', 'FR actuelle', 'réf VO', 'réf FR']
    for i, lot in enumerate(lots, 1):
        base = os.path.join(out_dir, f'lot_{i:02d}')
        with open(base + '.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cols, delimiter=';', extrasaction='ignore')
            w.writeheader()
            w.writerows(lot)
        terms = glossary_terms(r['VO nouvelle'] for r in lot)
        with open(base + '_glossaire.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['VO', 'FR retenue', 'statut'])
            w.writerows((t['VO'], t['FR retenue'], t['statut']) for t in terms)
        files = sorted({r['fichier'] for r in lot})
        print(f'lot_{i:02d}: {len(lot):3} entrées, {sum(len(r["VO nouvelle"].split()) for r in lot):5} mots, '
              f'{len(terms):3} termes, {sum(1 for r in lot if r["réf FR"]):3} réf — {", ".join(files)[:80]}')
    print(f'{len(todo)} entrées à traduire en {len(lots)} lots')


def verifie(lot):
    """Contrôle lot_NN_fr.csv contre lot_NN.csv. Renvoie la liste des problèmes."""
    with open(lot + '.csv', encoding='utf-8-sig', newline='') as f:
        src = {(r['fichier'], r['clé']): r for r in csv.DictReader(f, delimiter=';')}
    try:
        with open(lot + '_fr.csv', encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f, delimiter=';'))
    except FileNotFoundError:
        return [f'{lot}_fr.csv absent']
    issues, seen = [], set()
    if rows and list(rows[0].keys()) != ['clé', 'fichier', 'FR']:
        issues.append(f'colonnes attendues clé;fichier;FR, trouvées {list(rows[0].keys())}')
    for r in rows:
        k = (r.get('fichier', ''), r.get('clé', ''))
        if k not in src:
            issues.append(f'{k[1]} ({k[0]}) : clé inconnue du lot')
            continue
        seen.add(k)
        vo, fr = src[k]['VO nouvelle'], (r.get('FR') or '').strip()
        bad = []
        if not fr:
            bad.append('FR vide')
        if rules.placeholders(vo) != rules.placeholders(fr):
            bad.append(f'placeholders {rules.placeholders(vo)} -> {rules.placeholders(fr)}')
        if rules.hotkeys(vo) != rules.hotkeys(fr):
            bad.append(f'{rules.hotkeys(vo)} & dans la VO, {rules.hotkeys(fr)} dans la FR')
        if vo.count('\\n') != fr.count('\\n'):
            bad.append(f'{vo.count(chr(92) + "n")} \\n dans la VO, {fr.count(chr(92) + "n")} dans la FR')
        if '\n' in fr or '\r' in fr:
            bad.append('vrai saut de ligne (écrire \\n)')
        if '"' in fr:
            bad.append('guillemet " (utiliser « »)')
        if re.search(r'%[a-zA-Z]', fr.replace('%d', '').replace('%s', '').replace('%ls', '')):
            bad.append('% collé à une lettre')
        try:
            fr.encode(strfile.ENCODING)
        except UnicodeEncodeError as e:
            bad.append(f'caractère hors cp1252 : {fr[e.start:e.end]!r}')
        if bad:
            issues.append(f'{k[1]} ({k[0]}) : ' + ' ; '.join(bad))
    for k in src:
        if k not in seen:
            issues.append(f'{k[1]} ({k[0]}) : non traduite')
    return issues


def entry(key, text):
    return strfile.Entry(key=key, line=0, body=[f'"{text}"'])


def reinjecte(lots_dir, out_dir, tm_paths):
    by_file = {}
    for path in tm_paths:
        for r in read_tm(path):
            if r['FR proposée'] and not r['alerte']:
                by_file.setdefault(source_file(path), {})[r['clé']] = r['FR proposée']
    missing = 0
    for path in sorted(glob.glob(os.path.join(lots_dir, 'lot_*_fr.csv'))):
        with open(path, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f, delimiter=';'):
                if r['FR'].strip():
                    by_file.setdefault(r['fichier'], {})[r['clé']] = r['FR'].strip()
                else:
                    missing += 1
    for name, entries in by_file.items():
        dest = os.path.join(out_dir, 'lotr.str') if name == 'lotr' else os.path.join(out_dir, 'maps', name, 'map.str')
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        strfile.write(dest, [entry(k, v) for k, v in entries.items()])
        print(f'{name}: {len(entries)} entrées -> {dest}')
    if missing:
        print(f'{missing} lignes sans FR dans les lots')


if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'decoupe':
        ours, rest, i = [], [], 0
        while i < len(args):
            if args[i] == '--nous':
                ours.append((args[i + 1], args[i + 2]))
                i += 3
            else:
                rest.append(args[i])
                i += 1
        decoupe(rest[0], rest[1:], ours)
    elif cmd == 'reinjecte':
        reinjecte(args[0], args[1], args[2:])
    elif cmd == 'verifie':
        found = verifie(re.sub(r'(_fr)?\.csv$', '', args[0]))
        print('\n'.join(found) if found else 'OK')
        sys.exit(1 if found else 0)
    else:
        sys.exit(__doc__)
