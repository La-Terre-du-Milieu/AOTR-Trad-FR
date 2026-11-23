"""Règles partagées : placeholders, raccourcis &, typographie française."""
import re

NBSP = '\xa0'
PLACEHOLDER = re.compile(r'%(?:\d*[a-zA-Z]|%)')
HOTKEY = re.compile(r'&(\w)')          # "& " seul est une esperluette, pas un raccourci
AZERTY = {'W': 'Z'}                    # convention de la FR : W de la VO -> Z

_SPACE_BEFORE = re.compile(r' +([?!:;])')                     # "mot ?" -> "mot\xa0?"
_GLUED_QE = re.compile(r'(?<=[0-9A-Za-zÀ-ÖØ-öø-ÿ%)»])([?!])')  # "mot?"  -> "mot\xa0?"
_GLUED_COLON = re.compile(r'(?<=[A-Za-zÀ-ÖØ-öø-ÿ%)»])([:;])(?= )')  # "Bonus: x" -> "Bonus\xa0: x"


MAX_CAPTION_LINES = 4     # sous-titres « lettre par lettre » (SHOW_MILITARY_CAPTION) : au-delà, le jeu plante


def wrap(text, width=100, max_lines=MAX_CAPTION_LINES):
    """Coupe aux espaces (\\n littéral des .str) les lignes de plus de `width` caractères, en lignes équilibrées :
    le moteur n'enroule pas les textes affichés à l'écran (dialogues de campagne), ils sortent de l'écran.

    Jamais plus de `max_lines` lignes : le moteur (hérité de Generals) n'a que 4 lignes pour un SHOW_MILITARY_CAPTION
    et plante à la 5e (crash du 23/11/2026, « L'Anneau part vers le Sud », mgfotr_gandalf129 de 480 caractères).
    Un texte trop long est alors recoupé en `max_lines` lignes plus larges, sans les \\n de la VO."""
    out = _wrap(text, width)
    if out.count('\\n') >= max_lines:
        flat = ' '.join(p.strip() for p in text.split('\\n') if p.strip())
        width = -(-len(flat) // max_lines)
        while (out := _wrap(flat, width)).count('\\n') >= max_lines:
            width += 2
    return out


def _wrap(text, width):
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
