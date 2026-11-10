"""Règles partagées : placeholders, raccourcis &, typographie française."""
import re

NBSP = '\xa0'
PLACEHOLDER = re.compile(r'%(?:\d*[a-zA-Z]|%)')
HOTKEY = re.compile(r'&(\w)')          # "& " seul est une esperluette, pas un raccourci
AZERTY = {'W': 'Z'}                    # convention de la FR : W de la VO -> Z

_SPACE_BEFORE = re.compile(r' +([?!:;])')                     # "mot ?" -> "mot\xa0?"
_GLUED_QE = re.compile(r'(?<=[0-9A-Za-zÀ-ÖØ-öø-ÿ%)»])([?!])')  # "mot?"  -> "mot\xa0?"
_GLUED_COLON = re.compile(r'(?<=[A-Za-zÀ-ÖØ-öø-ÿ%)»])([:;])(?= )')  # "Bonus: x" -> "Bonus\xa0: x"


def wrap(text, width=100):
    """Coupe aux espaces (\\n littéral des .str) les lignes de plus de `width` caractères, en lignes équilibrées :
    le moteur n'enroule pas les textes affichés à l'écran (dialogues de campagne), ils sortent de l'écran."""
    out = []
    for part in text.split('\\n'):
        part = part.strip()
        n = -(-len(part) // width)
        if n <= 1:
            out.append(part)
            continue
        target, lines, cur = len(part) / n, [], ''
        for word in part.split(' '):
            name = word[:1].isupper() and cur.rsplit(' ', 1)[-1][:1].isupper()     # « Carn Dûm » : ne pas couper
            if cur and (len(cur) + 1 + len(word) > width or
                        (len(cur) >= target and len(lines) < n - 1 and not name)):
                lines.append(cur)
                cur = word
            else:
                cur = f'{cur} {word}' if cur else word
        out += lines + [cur]
    return '\\n'.join(out)


def placeholders(text):
    return sorted(PLACEHOLDER.findall(text))


def hotkeys(text):
    return len(HOTKEY.findall(text))


def french_typography(value_line):
    """Espace insécable devant ? ! : ; dans une ligne de valeur. Les URL sont laissées telles quelles."""
    if '://' in value_line or 'www.' in value_line:
        return value_line
    v = _SPACE_BEFORE.sub(NBSP + r'\1', value_line)
    v = _GLUED_QE.sub(NBSP + r'\1', v)
    return _GLUED_COLON.sub(NBSP + r'\1', v)
