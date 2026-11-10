"""Test en jeu : fait charger une autre carte à une mission de campagne, via le submod.

Le Save Generator du launcher ne propose que deux départs (Les Deux Tours : Gué de l'Isen ; Le Retour du Roi :
mission « Le Seigneur des Anneaux »). On écrit dans le submod une copie de linearcampaignexpansion1.ini où la mission
de départ prend la carte, la cinématique et l'écran de chargement de la mission voulue.

Usage :
  python tools/saut_mission.py FordsofIsen HelmsDeep [--mod "Traduction FR"]
  python tools/saut_mission.py --annule [--mod "Traduction FR"]       (à faire après le test !)
  python tools/saut_mission.py --liste
Le prochain build_submod.py efface aussi le saut (il repart d'un dossier data/ propre).
"""
import os
import re
import sys

import build_submod

INI = os.path.join(build_submod.audio_vf.AOTR, 'aotr', 'data', 'ini', 'linearcampaignexpansion1.ini')
FIELDS = ('Map', 'IntroMovie', 'LoadScreenImage', 'LoadScreenMusicTrack')


def missions(text):
    """nom -> (début, fin) du bloc Mission dans le texte."""
    out = {}
    starts = [(m.start(), m[1]) for m in re.finditer(r'(?m)^\s*Mission\s+(\w+)', text)]
    for i, (pos, name) in enumerate(starts):
        out[name] = (pos, starts[i + 1][0] if i + 1 < len(starts) else len(text))
    return out


def field(block, name):
    m = re.search(rf'(?m)^\s*{name}\s*=\s*(.+?)\s*$', block)
    return m[1] if m else None


def jump(text, start, target):
    blocks = missions(text)
    for name in (start, target):
        if name not in blocks:
            sys.exit(f'Mission « {name} » inconnue. Missions : {", ".join(blocks)}')
    tgt = text[slice(*blocks[target])]
    a, b = blocks[start]
    block = text[a:b]
    for name in FIELDS:
        value = field(tgt, name)
        if value is not None:
            block = re.sub(rf'(?m)^(\s*{name}\s*=\s*).+?(\s*)$', lambda m: m[1] + value + m[2], block, count=1)
    return text[:a] + block + text[b:]


if __name__ == '__main__':
    args = sys.argv[1:]
    with open(INI, encoding='cp1252', newline='') as f:
        text = f.read()
    if '--liste' in args:
        for name, (a, b) in missions(text).items():
            print(f'{name:22} {field(text[a:b], "Map")}')
        sys.exit()
    mod = args[args.index('--mod') + 1] if '--mod' in args else 'Traduction FR'
    dest = os.path.join(build_submod.launcher_source(mod), 'data', 'ini', os.path.basename(INI))
    if '--annule' in args:
        if os.path.exists(dest):
            os.remove(dest)
        print(f'saut annulé : campagne normale ({dest} supprimé)')
        sys.exit()
    names = [a for a in args if not a.startswith('--') and a != mod]
    if len(names) != 2:
        sys.exit(__doc__)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'w', encoding='cp1252', newline='') as f:
        f.write(jump(text, *names))
    print(f'{names[0]} charge maintenant la carte de {names[1]} -> {dest}')
    print('Ne pas oublier : python tools/saut_mission.py --annule après le test.')
