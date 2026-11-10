"""Mémoire de traduction : pré-remplit une liste de travail avec les traductions déjà existantes.

Sources, de la plus sûre à la moins sûre :
  - notre traduction (paires VO ancienne / FR données par --nous) ;
  - les traductions officielles d'EA : BFME1 1.08 (+ campagne patchée), RotWK, BFME II.
Une proposition « clé » (même clé et même texte anglais) passe avant une proposition « texte »
(même texte anglais, autre clé). Les propositions dont les placeholders ne correspondent pas à la VO
ou qui ne passent pas en Windows-1252 sont marquées dans la colonne « alerte ».

Usage : python tools/memoire.py <liste.csv> [<liste.csv>…] --nous <vo> <fr> [--nous <vo> <fr>…]
  <vo>/<fr> : deux fichiers .str, ou deux dossiers de maps (<dossier>/<map>/map.str).
  Écrit <liste>_tm.csv à côté de chaque liste (colonnes de diff_versions.py + FR proposée, source, alerte).
"""
import csv
import os
import re
import struct
import sys
import tempfile

import rules
import strfile
from bigfile import BigFile

BFME1 = r'C:\BFME1'
AOTR = r'C:\AgeoftheRing'
EA = r'C:\Program Files (x86)\Electronic Arts'
# (nom, (archive VO, fichier interne), (archive FR, fichier interne))
# (la table « french » de _patch108.big est une copie de l'anglais : ne pas l'utiliser)
EA_SOURCES = [
    ('BFME1', (os.path.join(BFME1, '_patch108english.big'), 'data/lotr.str'),
              (os.path.join(BFME1, '_patch108french.big'), 'data/lotr.str')),
    ('BFME1', (os.path.join(BFME1, '_wspatch108campaigneng.big'), 'data/lotr.str'),
              (os.path.join(BFME1, '_wwspatch108campaignefr.big'), 'data/lotr.str')),
    ('BFME1', (os.path.join(BFME1, '_patch106.big'), 'data/lotr.str'),
              (os.path.join(BFME1, '_frenchpatch106.big'), 'lotr.csf')),
    ('BFME1', (os.path.join(BFME1, '_patch106.big'), 'data/lotr.str'),
              (os.path.join(BFME1, 'lang', 'french.big'), 'lotr.csf')),
    ('RotWK', (os.path.join(AOTR, 'rotwk', 'lang', 'English.big'), 'data/lotr.str'),
              (os.path.join(EA, "L'Avènement du Roi-sorcier", 'lang', 'french.big'), 'lotr.csf')),
    ('BFME2', (os.path.join(AOTR, 'bfme2', 'lang', 'English.big'), 'data/lotr.str'),
              (os.path.join(EA, 'La Bataille pour la Terre du Milieu II', 'lang', 'French.big'), 'lotr.csf')),
]


def read_csf(data):
    """Table de chaînes compilée d'EA : clé en minuscules -> texte (sauts de ligne en \\n)."""
    count = struct.unpack('<I', data[8:12])[0]
    pos, out = 24, {}
    for _ in range(count):
        nstr, size = struct.unpack('<II', data[pos + 4:pos + 12])
        label = data[pos + 12:pos + 12 + size].decode('latin1')
        pos += 12 + size
        for i in range(nstr):
            tag, size = data[pos:pos + 4], struct.unpack('<I', data[pos + 4:pos + 8])[0]
            pos += 8
            text = bytes(b ^ 0xFF for b in data[pos:pos + 2 * size]).decode('utf-16-le')
            pos += 2 * size
            if tag == b'WRTS':
                pos += 4 + struct.unpack('<I', data[pos:pos + 4])[0]
            if i == 0:
                out[label.lower()] = text.replace('\r', '').replace('\n', '\\n')
    return out


def read_table(big_path, inner):
    """clé -> texte d'un .csf ou d'un .str contenu dans une archive .big."""
    big = BigFile(big_path)
    name = next(k for k in big.files if k.endswith(inner))
    data = big.read(name)
    if inner.endswith('.csf'):
        return read_csf(data)
    with tempfile.NamedTemporaryFile(suffix='.str', delete=False) as f:
        f.write(data)
    try:
        return {k: e.text for k, e in strfile.read(f.name).index().items()}
    finally:
        os.unlink(f.name)


def read_pairs(vo, fr):
    """Paires (VO, FR) de notre traduction : deux .str ou deux dossiers de maps."""
    if os.path.isdir(vo):
        for m in sorted(os.listdir(vo)):
            v, f = os.path.join(vo, m, 'map.str'), os.path.join(fr, m, 'map.str')
            if os.path.exists(v) and os.path.exists(f):
                yield from read_pairs(v, f)
        return
    v, f = strfile.read(vo).index(), strfile.read(fr).index()
    for k, e in v.items():
        if k in f and f[k].text.strip():
            yield k, e.text, f[k].text


def norm(text):
    """Texte comparable : casse, espaces et « * » des sous-titres BFME1 ignorés."""
    return ' '.join(text.replace('\\n', ' \\n ').split()).lower().lstrip('*').strip()


class Memoire:
    def __init__(self):
        self.by_key = {}    # clé -> [(texte normalisé, FR, source)]
        self.by_text = {}   # texte normalisé -> (FR, source), première source gagnante

    def add(self, source, key, en, fr):
        if not en.strip() or not fr.strip():
            return
        n = norm(en)
        self.by_key.setdefault(key, []).append((n, fr, source))
        self.by_text.setdefault(n, (fr, source))

    def propose(self, key, en):
        n = norm(en)
        for text, fr, source in self.by_key.get(key.lower(), []):
            if text == n:
                return fr, f'{source} clé'
        if n in self.by_text:
            fr, source = self.by_text[n]
            return fr, f'{source} texte'
        return '', ''


SPEAKER = re.compile(r'^[A-ZÀ-Ý][A-ZÀ-Ý \'-]+\s?:\s')   # « LEGOLAS : » en tête d'un dialogue de map
MOJIBAKE = re.compile(r'Ã[\x80-\xbf©¨ª«´¹®¯§¢]|â€')


def unmojibake(text):
    """Répare un texte UTF-8 relu en Windows-1252 (« cachÃ©s » -> « cachés »)."""
    if not MOJIBAKE.search(text):
        return text

    def fix(m):
        try:
            return m.group().encode('cp1252').decode('utf-8')
        except UnicodeError:
            return m.group()
    text = re.sub(r'Ã[ \xa0](?=\w)', 'à ', text)      # « à » dont l'octet A0 est devenu une espace
    return re.sub(r'[ÂÃÅâ][\x80-\xbf€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ¡-¿]{1,2}', fix, text)


def adapt(vo, fr):
    """Aligne la proposition sur la VO : mojibake, « * » des sous-titres BFME1 et préfixe du locuteur."""
    fr = unmojibake(fr)
    if fr.startswith('*') and not vo.startswith('*'):
        fr = fr[1:]
    if SPEAKER.match(fr) and not SPEAKER.match(vo):
        fr = SPEAKER.sub('', fr, count=1)
    return fr


def alert(vo, fr):
    issues = []
    if MOJIBAKE.search(fr):
        issues.append('mojibake')
    if sorted(rules.placeholders(vo)) != sorted(rules.placeholders(fr)):
        issues.append('placeholders')
    if rules.hotkeys(vo) != rules.hotkeys(fr):
        issues.append('raccourci &')
    try:
        fr.encode(strfile.ENCODING)
    except UnicodeEncodeError:
        issues.append('hors cp1252')
    if '"' in fr:
        issues.append('guillemet')
    return ', '.join(issues)


def build(ours):
    mem = Memoire()
    for vo, fr in ours:
        for k, en, f in read_pairs(vo, fr):
            mem.add('nous', k, en, f)
    for name, (vo_big, vo_in), (fr_big, fr_in) in EA_SOURCES:
        if not (os.path.exists(vo_big) and os.path.exists(fr_big)):
            print('absent :', vo_big if not os.path.exists(vo_big) else fr_big)
            continue
        en, fr = read_table(vo_big, vo_in), read_table(fr_big, fr_in)
        for k, t in en.items():
            if k in fr:
                mem.add(name, k, t, fr[k])
    return mem


def main(argv):
    lists, ours, i = [], [], 0
    while i < len(argv):
        if argv[i] == '--nous':
            ours.append((argv[i + 1], argv[i + 2]))
            i += 3
        else:
            lists.append(argv[i])
            i += 1
    mem = build(ours)
    for path in lists:
        with open(path, encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f, delimiter=';'))
        stats = {}
        for r in rows:
            fr, source = ('', '') if r['statut'] == 'supprimée' else mem.propose(r['clé'], r['VO nouvelle'])
            r['FR proposée'], r['source'] = adapt(r['VO nouvelle'], fr), source
            r['alerte'] = alert(r['VO nouvelle'], r['FR proposée']) if fr else ''
            if r['statut'] != 'supprimée':
                key = source.split(' ')[0] if source else 'aucune'
                stats[key] = stats.get(key, 0) + 1
        out = re.sub(r'\.csv$', '', path) + '_tm.csv'
        with open(out, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [], delimiter=';')
            w.writeheader()
            w.writerows(rows)
        print(f'{os.path.basename(path)}: {stats}')


if __name__ == '__main__':
    main(sys.argv[1:])
