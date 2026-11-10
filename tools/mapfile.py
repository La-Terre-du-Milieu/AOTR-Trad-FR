"""Lecture des cartes .map de BFME (compressées RefPack, en-tête « EAR\\0 » + taille).

On n'analyse pas le format des blocs : on extrait les chaînes préfixées par leur longueur (uint16), dans l'ordre
du fichier. Dans les scripts, une action « jouer un son » est précédée du nom du script, qui contient souvent
le texte de la réplique (« Audio - Sauron - No escape! No quarter! » puis « mgfotr_sauron046 »).
"""
import re


def refpack(data):
    """Décompresse un fichier RefPack (EAR\\0 + taille + flux 0x10FB)."""
    if data[:4] != b'EAR\0':
        return data
    d = data[8:]
    p = 2
    if d[0] & 0x80:
        size, p = int.from_bytes(d[p:p + 4], 'big'), p + 4
    else:
        size, p = int.from_bytes(d[p:p + 3], 'big'), p + 3
    out = bytearray()
    while p < len(d):
        b0 = d[p]
        if b0 < 0x80:
            b1 = d[p + 1]
            p += 2
            plain, n, off = b0 & 3, ((b0 & 0x1c) >> 2) + 3, ((b0 & 0x60) << 3) + b1 + 1
        elif b0 < 0xC0:
            b1, b2 = d[p + 1], d[p + 2]
            p += 3
            plain, n, off = (b1 >> 6) & 3, (b0 & 0x3f) + 4, ((b1 & 0x3f) << 8) + b2 + 1
        elif b0 < 0xE0:
            b1, b2, b3 = d[p + 1], d[p + 2], d[p + 3]
            p += 4
            plain, n, off = b0 & 3, ((b0 & 0x0c) << 6) + b3 + 5, ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1
        elif b0 < 0xFC:
            plain, n, off = ((b0 & 0x1f) << 2) + 4, 0, 0
            p += 1
        else:                                     # fin du flux
            p += 1
            out += d[p:p + (b0 & 3)]
            break
        out += d[p:p + plain]
        p += plain
        for _ in range(n):
            out.append(out[-off])
    if len(out) != size:
        raise ValueError(f'RefPack : {len(out)} octets au lieu de {size}')
    return bytes(out)


def strings(path):
    """Chaînes (uint16 longueur + texte) d'une carte, dans l'ordre."""
    with open(path, 'rb') as f:
        d = refpack(f.read())
    out = []
    for m in re.finditer(rb'[\x20-\x7e\xa0-\xff]{2,}', d):
        s, e = m.start(), m.end()
        if s >= 2 and int.from_bytes(d[s - 2:s], 'little') == e - s:
            out.append(m.group().decode('cp1252', errors='replace'))
    return out
