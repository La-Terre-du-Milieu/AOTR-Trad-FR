"""Aligne les raccourcis clavier (&) de la FR sur la VO.

- VO sans raccourci   -> on retire ceux de la FR ;
- FR sans raccourci   -> on ajoute [&X] (lettre de la VO, W -> Z pour l'AZERTY) ;
- FR avec trop de &   -> on garde celui qui correspond à la lettre VO (de préférence entre crochets).
Une FR qui a exactement un raccourci n'est jamais modifiée (lettre choisie par le traducteur).

Usage : python tools/hotkeys.py <fr.str> <vo.str> [--fix]
"""
import re
import sys
from collections import defaultdict

import strfile
from rules import AZERTY, HOTKEY

QUOTED = re.compile(r'"([^"]*)"')
FR_HOTKEY = re.compile(r'\s*[(\[]&(\w)[)\]]|&(\w)')


def align(text, vo_text):
    vo = HOTKEY.findall(vo_text)
    found = list(FR_HOTKEY.finditer(text))
    if len(found) == len(vo) or (vo and len(found) == 1) or (len(vo) > 1 and found):
        return text
    if not found:
        letter = vo[-1].upper()
        return f'{text.rstrip()} [&{AZERTY.get(letter, letter)}]'
    targets = {vo[-1].upper(), AZERTY.get(vo[-1].upper(), '')} if vo else set()
    keep = None
    if vo:
        def rank(m):
            letter = (m.group(1) or m.group(2)).upper()
            return (letter not in targets, m.group(1) is None)
        keep = min(found, key=rank)
    for m in reversed(found):
        if m is keep:
            continue
        cut = (m.start(), m.end()) if m.group(1) else (m.start(), m.start() + 1)
        text = text[:cut[0]] + text[cut[1]:]
    return text


def run(fr_path, en_path, fix=False):
    fr, en_file = strfile.read(fr_path), strfile.read(en_path)
    # clés en double : la n-ième occurrence FR correspond à la n-ième occurrence VO
    en, seen = defaultdict(list), defaultdict(int)
    for e in en_file.entries:
        en[e.lkey].append(e)
    changes = []
    for e in fr.entries:
        n = seen[e.lkey]
        seen[e.lkey] += 1
        if not en[e.lkey] or not e.values:
            continue
        vo = en[e.lkey][min(n, len(en[e.lkey]) - 1)]
        i = e.body.index(e.values[0])
        line = e.body[i]
        m = QUOTED.search(line)
        if not m:
            continue
        new = align(m.group(1), vo.text)
        if new != m.group(1):
            changes.append((e.key, m.group(1), new))
            e.body[i] = line[:m.start(1)] + new + line[m.end(1):]
    if fix:
        strfile.write(fr_path, fr.items)
    return changes


if __name__ == '__main__':
    changes = run(sys.argv[1], sys.argv[2], fix='--fix' in sys.argv)
    for key, old, new in changes:
        print(f'{key}\n   {old[:90]}\n-> {new[:90]}')
    print(f'{len(changes)} raccourcis {"corrigés" if "--fix" in sys.argv else "à corriger (--fix pour appliquer)"}')
