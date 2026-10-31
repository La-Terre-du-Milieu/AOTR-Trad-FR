"""Remplace les guillemets non échappés à l'intérieur d'une valeur (le jeu y couperait le texte)
par des guillemets français « », et supprime les guillemets parasites en fin de valeur.

Une ligne qui contient plusieurs chaînes séparées (ex. "a" ; "b", héritée de la VO) n'est pas touchée.

Usage : python tools/quotes.py <fr.str> [--fix]
"""
import re
import sys

import strfile
from rules import NBSP

INNER = re.compile(r'(?<!\\)"')
SEPARATE_STRINGS = re.compile(r'"\s*;\s*"')


def fix_line(line):
    if SEPARATE_STRINGS.search(line):
        return line
    start, end = line.index('"'), line.rindex('"')
    text = line[start + 1:end]
    while len(INNER.findall(text)) % 2 and text.endswith('"'):
        text = text[:-1]                                  # guillemet parasite en fin de valeur
    if len(INNER.findall(text)) % 2:
        return None                                       # impair : à revoir à la main
    opening = True

    def swap(_):
        nonlocal opening
        opening = not opening
        return '«' + NBSP if not opening else NBSP + '»'
    return line[:start + 1] + INNER.sub(swap, text) + line[end:]


def run(path, fix=False):
    sf = strfile.read(path)
    changed, manual = [], []
    for e in sf.entries:
        for i, b in enumerate(e.body):
            s = b.strip()
            if s.startswith('"') and s.count('"') - s.count('\\"') > 2:
                new = fix_line(b)
                if new is None:
                    manual.append((e.key, s))
                elif new != b:
                    changed.append((e.key, s, new.strip()))
                    e.body[i] = new
    if fix:
        strfile.write(path, sf.items)
    return changed, manual


if __name__ == '__main__':
    changed, manual = run(sys.argv[1], fix='--fix' in sys.argv)
    for key, old, new in changed:
        print(f'{key}\n   {old[:110]}\n-> {new[:110]}')
    for key, s in manual:
        print(f'À REVOIR {key} : {s[:110]}')
    print(f'{len(changed)} corrigées, {len(manual)} à revoir')
