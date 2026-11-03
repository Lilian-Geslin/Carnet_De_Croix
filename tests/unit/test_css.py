"""Feuilles de style : un bloc non fermé avalerait tout le reste du fichier (et casserait les couleurs de l'appli)."""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES = sorted(glob.glob(os.path.join(ROOT, 'src', 'static', 'css', '*.css')))


def test_there_are_stylesheets():
    assert FILES


def test_every_stylesheet_has_balanced_braces():
    for path in FILES:
        text = re.sub(r'/\*.*?\*/', '', open(path, encoding='utf-8').read(), flags=re.S)   # sans les commentaires
        assert text.count('{') == text.count('}'), f"accolades déséquilibrées dans {os.path.basename(path)}"


def test_base_css_declares_the_palette_and_fonts():
    text = open(os.path.join(ROOT, 'src', 'static', 'css', 'base.css'), encoding='utf-8').read()
    assert ':root' in text and '--bg:' in text and text.count('@font-face') == 6
