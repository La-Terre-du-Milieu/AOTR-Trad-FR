"""Règles partagées : placeholders, raccourcis &, typographie française."""
import re

NBSP = '\xa0'
PLACEHOLDER = re.compile(r'%(?:\d*[a-zA-Z]|%)')
HOTKEY = re.compile(r'&(\w)')          # "& " seul est une esperluette, pas un raccourci
AZERTY = {'W': 'Z'}                    # convention de la FR : W de la VO -> Z

_SPACE_BEFORE = re.compile(r' +([?!:;])')                     # "mot ?" -> "mot\xa0?"
_GLUED_QE = re.compile(r'(?<=[0-9A-Za-zÀ-ÖØ-öø-ÿ%)»])([?!])')  # "mot?"  -> "mot\xa0?"
_GLUED_COLON = re.compile(r'(?<=[A-Za-zÀ-ÖØ-öø-ÿ%)»])([:;])(?= )')  # "Bonus: x" -> "Bonus\xa0: x"


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
