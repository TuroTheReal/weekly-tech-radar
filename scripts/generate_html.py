# ├── CATEGORY_MAP          — dict constant (mapping catégorie → css + labels)
# ├── load_enriched()       — charger le JSON enrichi
# ├── group_by_category()   — grouper articles par catégorie, dans le bon ordre
# ├── render_edition()      — générer le bloc HTML des articles (entre les marqueurs)
# ├── generate_edition()    — lire le HTML existant, remplacer le contenu, écrire EN + FR
# ├── update_index()        — ajouter la nouvelle card dans l'index EN + FR
# ├── update_prev_edition() — ajouter lien "next" sur l'édition précédente
# └── main                  — orchestrer tout

import json
from datetime import datetime
from pathlib import Path
import jinja2

SCRIPT_DIR = Path(__file__).parent
CTA = {"en": "Read article →", "fr": "Lire l'article →"}
CATEGORY_MAP = {
    "Cloud":    {"css": "cloud",      "en": "Cloud",    "fr": "Cloud"},
    "DevOps":   {"css": "devops",     "en": "DevOps",   "fr": "DevOps"},
    "Sécurité": {"css": "secu",       "en": "Security", "fr": "Sécurité"},
    "AI/ML":    {"css": "ia",         "en": "AI",       "fr": "IA"},
    "Business": {"css": "business",   "en": "Business", "fr": "Business"},
    "Tech":     {"css": "frameworks", "en": "Tech",     "fr": "Tech"},
}

def load_json(path):
    """Charge un fichier JSON.

    Args:
        path (Path): Chemin vers le fichier JSON

    Returns:
        dict: Contenu du fichier (week, year, articles, etc.)
    """
    with open(path, 'r') as f:
        return json.load(f)

def group_by_category(enriched):
    grouped = {}
    for article in enriched:
        if article['category'] not in grouped:
            grouped[article['category']] = []
        grouped[article['category']].append(article)
    return grouped

def render_edition(grouped, lang):
    filled = ""
    for category in grouped:
        category_info = CATEGORY_MAP[category]
        label = category_info[lang]
        css_class = category_info['css']
        link_text = CTA[lang]
        filled += f'\n<h2><span class="radar-tag radar-tag--{css_class}">{label}</span></h2>\n'
        for article in grouped[category]:
            summary = article['summary_en'] if lang == 'en' else article['summary_fr']
            url = article['url']
            title = article['title']
            filled += f'''
<div class="radar-edition-item">
    <h3>{title}</h3>
    <p>{summary}</p>
    <a href="{url}" target="_blank" rel="noopener noreferrer" class="radar-edition-source">{link_text}</a>
</div>
'''
    return filled

def generate_edition():
    pass

if __name__ == '__main__':
    now = datetime.now()
    year, week, _ = now.isocalendar()
    path = SCRIPT_DIR.parent / "data" / str(year) / f"week-{week:02d}-enriched.json"

    enriched = load_json(path)
    grouped = group_by_category(enriched)
    fr_edition = render_edition(grouped, 'fr')
    en_edition = render_edition(grouped, 'en')