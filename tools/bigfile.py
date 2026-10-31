"""Lecture des archives .big de BFME (BIGF / BIG4).

En-tête : magic (4), taille (4, LE), nombre de fichiers (4, BE), début des données (4, BE),
puis pour chaque fichier : offset (4, BE), taille (4, BE), nom terminé par \\0.

Usage : python tools/bigfile.py <archive.big> [dossier_de_sortie]
"""
import os
import struct
import sys


class BigFile:
    def __init__(self, path):
        self.path = path
        self.files = {}    # chemin interne normalisé (minuscules, /) -> (offset, taille, nom d'origine)
        with open(path, 'rb') as f:
            self.magic = f.read(4)
            f.read(4)
            count, _ = struct.unpack('>II', f.read(8))
            for _ in range(count):
                off, size = struct.unpack('>II', f.read(8))
                name = bytearray()
                while (c := f.read(1)) != b'\0':
                    name += c
                name = name.decode('latin1')
                self.files[name.replace('\\', '/').lower()] = (off, size, name)

    def by_basename(self):
        return {os.path.basename(k): k for k in self.files}

    def read(self, name, limit=None):
        off, size, _ = self.files[name]
        with open(self.path, 'rb') as f:
            f.seek(off)
            return f.read(size if limit is None else min(size, limit))

    def extract(self, name, dest):
        os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
        with open(dest, 'wb') as f:
            f.write(self.read(name))


if __name__ == '__main__':
    big = BigFile(sys.argv[1])
    for name, (_, size, orig) in big.files.items():
        print(f'{size:>10}  {orig}')
        if len(sys.argv) > 2:
            big.extract(name, os.path.join(sys.argv[2], *orig.split('\\')))
