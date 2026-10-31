"""Reconstruit un .str FR propre à partir de la VO.

La VO sert de gabarit : ordre, clés, commentaires et doublons sont ceux de la VO ;
seules les lignes de valeur viennent de la FR. Les clés absentes de la VO (obsolètes)
disparaissent, celles absentes de la FR gardent le texte VO et sont listées.

Usage : python tools/rebuild.py <vo.str> <sortie.str> <fr.str> [fr2.str ...] [--typo]
        (plusieurs sources FR : la première qui contient la clé l'emporte)
"""
import sys
from collections import defaultdict

import strfile
from rules import french_typography


def occurrences(sf):
    """clé -> liste de (Entry, clé de l'entrée précédente)."""
    occ, prev = defaultdict(list), None
    for e in sf.entries:
        occ[e.lkey].append((e, prev))
        prev = e.lkey
    return occ


def pick(fr_occ, en_count, index, en_prev):
    """Choisit l'occurrence FR qui correspond à la index-ième occurrence VO."""
    if len(fr_occ) == en_count:
        return fr_occ[index][0]
    if en_count == 1:
        for e, prev in fr_occ:
            if prev == en_prev:
                return e
    return fr_occ[min(index, len(fr_occ) - 1)][0]


def rebuild(en_path, fr_paths, typo=False):
    en = strfile.read(en_path)
    sources = [occurrences(strfile.read(p)) for p in fr_paths]
    en_occ = occurrences(en)
    seen = defaultdict(int)
    items, missing = [], []
    for it in en.items:
        if not isinstance(it, strfile.Entry):
            items.append(it)
            continue
        k = it.lkey
        i = seen[k]
        seen[k] += 1
        en_prev = en_occ[k][i][1]
        fr = next((pick(s[k], len(en_occ[k]), i, en_prev) for s in sources if k in s), None)
        if fr is None:
            missing.append(it)
            items.append(it)
            continue
        values = [french_typography(v) if typo else v for v in fr.values]
        body, done = [], False
        for b in it.body:
            if b.strip() and not b.strip().startswith('//'):
                if not done:
                    body += values
                    done = True
            else:
                body.append(b)
        items.append(strfile.Entry(it.key, it.line, body, it.end))
    return items, missing


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    items, missing = rebuild(args[0], args[2:], typo='--typo' in sys.argv)
    strfile.write(args[1], items)
    print(f'{sum(isinstance(i, strfile.Entry) for i in items)} entrées écrites dans {args[1]}')
    print(f'{len(missing)} sans traduction (texte VO conservé) :')
    for e in missing:
        print(f'   {e.key} | {e.text[:80]}')
