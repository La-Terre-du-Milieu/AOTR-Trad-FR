"""Clés du jeu de base (RotWK) absentes du lotr.str d'AotR : le jeu les lit alors dans le lotr.str anglais
de la base du launcher (English.big), donc toujours en anglais. On en fait lotr_base.str avec la VF officielle
de RotWK ; build_submod.py l'ajoute à la fin du lotr.str du submod.

Usage : python tools/base_vf.py [vo_aotr]      (défaut : la dernière VO de English_folder_str)
"""
import os
import sys
import tempfile

import doublage
import memoire
import rules
import strfile
from bigfile import BigFile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'lotr_base.str')
BASE_EN = (os.path.join(memoire.AOTR, 'rotwk', 'lang', 'English.big'), 'data/lotr.str')
ROTWK_FR = os.path.join(memoire.EA, "L'Avènement du Roi-sorcier", 'lang')
# du plus ancien au plus récent : le dernier patch l'emporte
FR_TABLES = [('french.big', 'lotr.csf'), ('frenchpatch201.big', 'lotr.csf'), ('frenchpatch202.big', 'data/lotr.str')]


def base_entries():
    with tempfile.NamedTemporaryFile(suffix='.str', delete=False) as f:
        f.write(BigFile(BASE_EN[0]).read(BASE_EN[1]))
    try:
        return strfile.read(f.name).entries
    finally:
        os.unlink(f.name)


def main(vo_path):
    vo = strfile.read(vo_path).index()
    fr = {}
    for big, inner in FR_TABLES:
        fr.update(memoire.read_table(os.path.join(ROTWK_FR, big), inner))
    lines, missing = ['// Clés du jeu de base absentes du lotr.str d\'AotR (VF officielle de RotWK) : tools/base_vf.py', ''], []
    for e in base_entries():
        if e.lkey in vo:
            continue
        text = fr.get(e.lkey)
        if not text:
            missing.append(e.key)
            continue
        text = rules.french_typography(text.replace('"', '«', 1).replace('"', '»', 1).replace('"', "'"))
        lines += [e.key, f'"{text}"', 'END', '']
    with open(OUT, 'w', encoding=strfile.ENCODING, newline='\r\n') as f:
        f.write('\n'.join(lines))
    print(f'{(len(lines) - 2) // 4} clés -> {OUT}' + (f' ; sans VF : {", ".join(missing)}' if missing else ''))


if __name__ == '__main__':
    vo = sys.argv[1] if len(sys.argv) > 1 else doublage.latest_vo()
    main(vo)
