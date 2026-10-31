"""Lecture / écriture des fichiers .str de BFME (lotr.str, map.str).

Format : une clé, des lignes de valeur entre guillemets (éventuellement précédées
de commentaires //), puis END. Encodage Windows-1252, fins de ligne CRLF.
"""
from dataclasses import dataclass, field

ENCODING = 'cp1252'


@dataclass
class Entry:
    key: str
    line: int                                    # ligne de la clé (1-indexée)
    body: list = field(default_factory=list)     # lignes brutes entre la clé et END
    end: str = 'END'                             # ligne END brute (indentation conservée)

    @property
    def lkey(self):
        return self.key.lower()

    @property
    def values(self):
        """Lignes de valeur, sans les commentaires ni les lignes vides."""
        return [b for b in self.body if b.strip() and not b.strip().startswith('//')]

    @property
    def text(self):
        """Texte comparable : valeurs sans guillemets, jointes."""
        return '\n'.join(v.strip().strip('"') for v in self.values)


@dataclass
class StrFile:
    items: list            # str (ligne brute hors entrée) ou Entry
    problems: list         # (ligne, message)

    @property
    def entries(self):
        return [i for i in self.items if isinstance(i, Entry)]

    def index(self):
        """clé en minuscules -> première Entry (le jeu garde la première occurrence)."""
        idx = {}
        for e in self.entries:
            idx.setdefault(e.lkey, e)
        return idx

    def duplicates(self):
        seen, dups = set(), []
        for e in self.entries:
            if e.lkey in seen:
                dups.append(e)
            seen.add(e.lkey)
        return dups


def read(path):
    with open(path, encoding=ENCODING, newline='') as f:
        lines = f.read().splitlines()
    items, problems, cur = [], [], None
    for n, ln in enumerate(lines, 1):
        s = ln.strip()
        if cur is None:
            if not s or s.startswith('//'):
                items.append(ln)
            elif s.upper() == 'END':
                problems.append((n, 'END orphelin'))
                items.append(ln)
            elif s.startswith('"'):
                problems.append((n, f'texte hors entrée : {s[:60]}'))
                items.append(ln)
            else:
                cur = Entry(s, n)
        elif s.upper() == 'END':
            cur.end = ln
            if not cur.values:
                problems.append((cur.line, f'{cur.key} : aucune valeur'))
            elif len(cur.values) > 1:
                problems.append((cur.line, f'{cur.key} : {len(cur.values)} lignes de valeur'))
            for v in cur.values:
                if v.count('"') - v.count('\\"') > 2:
                    problems.append((cur.line, f'{cur.key} : guillemets en trop : {v.strip()[:60]}'))
            items.append(cur)
            cur = None
        else:
            cur.body.append(ln)
    if cur is not None:
        problems.append((cur.line, f'{cur.key} : END manquant'))
        items.append(cur)
    return StrFile(items, problems)


def write(path, items):
    out = []
    for i in items:
        if isinstance(i, Entry):
            out += [i.key, *i.body, i.end]
        else:
            out.append(i)
    with open(path, 'w', encoding=ENCODING, newline='') as f:
        f.write('\r\n'.join(out) + '\r\n')
