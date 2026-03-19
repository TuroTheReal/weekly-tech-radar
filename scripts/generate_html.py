# ├── CATEGORY_MAP          — dict constant (mapping catégorie → css + labels)
# ├── load_enriched()       — charger le JSON enrichi
# ├── group_by_category()   — grouper articles par catégorie, dans le bon ordre
# ├── render_edition()      — générer le bloc HTML des articles (entre les marqueurs)
# ├── generate_edition()    — lire le HTML existant, remplacer le contenu, écrire EN + FR
# ├── update_index()        — ajouter la nouvelle card dans l'index EN + FR
# ├── update_prev_edition() — ajouter lien "next" sur l'édition précédente
# └── main                  — orchestrer tout

import json, sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TECH_RADAR_DIR = "tech-radar"
TEMPLATE_NAME = "edition-template.html"
INDEX_NAME = "index.html"
CTA = {"en": "Read article →", "fr": "Lire l'article →"}
CATEGORY_MAP = {
    "Cloud":    {"css": "cloud",      "en": "Cloud",    "fr": "Cloud"},
    "DevOps":   {"css": "devops",     "en": "DevOps",   "fr": "DevOps"},
    "Sécurité": {"css": "secu",       "en": "Security", "fr": "Sécurité"},
    "AI/ML":    {"css": "ia",         "en": "AI",       "fr": "IA"},
    "Business": {"css": "business",   "en": "Business", "fr": "Business"},
    "Tech":     {"css": "frameworks", "en": "Tech",     "fr": "Tech"},
}
MONTHS = {
    "en": ["", "January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
    "fr": ["", "janvier", "février", "mars", "avril", "mai", "juin",
           "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
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

def render_card(enriched, grouped, lang):
    week = enriched['week']
    year = enriched['year']
    week_label = f"Week {week}" if lang == 'en' else f"Semaine {week}"
    date_iso = enriched['date_end']
    date = datetime.strptime(date_iso, "%Y-%m-%d")
    date_display = f"{MONTHS['en'][date.month]} {date.day}, {date.year}" if lang == 'en' else f"{date.day} {MONTHS['fr'][date.month]} {date.year}"
    article_count = len(enriched['articles'])


    filled = ""
    filled += f'''
<a href="/{lang}/{TECH_RADAR_DIR}/{year}-week-{week:02d}.html" class="radar-card">
    <div class="radar-card-header">
        <span class="radar-card-week">{week_label}</span>
        <time class="radar-card-date">{date_display}</time>
    </div>
    <ul class="radar-card-list">
'''

    for category in grouped:
        category_info = CATEGORY_MAP[category]
        label = category_info[lang]
        css_class = category_info['css']
        title = grouped[category][0]['title']
        filled += f'''
        <li class="radar-card-item">
            <span class="radar-tag radar-tag--{css_class}">{label}</span>
            <span class="radar-card-text">{title}</span>
        </li>
'''
    filled += f'''
    </ul>
    <span class="radar-card-count">{article_count} articles</span>
</a>
'''
    return filled

def generate_edition(enriched, grouped, portfolio_dir):
    article_count = len(enriched['articles'])
    week = enriched['week']
    year = enriched['year']
    date_iso = enriched['date_end']
    filename = f"{year}-week-{week:02d}.html"
    date = datetime.strptime(date_iso, "%Y-%m-%d")

    if week > 1:
        prev_week = week - 1
        prev_year = year
    else:
        prev_year = year - 1
        # Trouver la dernière semaine de l'année précédente
        prev_week = datetime(prev_year, 12, 28).isocalendar()[1]

    prev_filename = f"{prev_year}-week-{prev_week:02d}.html"
    prev_exists = (portfolio_dir / "en" / TECH_RADAR_DIR / prev_filename).exists()

    for lang in ['en', 'fr']:
        if prev_exists:
            prev_label = f"Week {prev_week}" if lang == 'en' else f"Semaine {prev_week}"
            nav_label = "&larr; Previous edition" if lang == 'en' else "&larr; Édition précédente"
            radar_nav = f'''
<a href="/{lang}/{TECH_RADAR_DIR}/{prev_filename}" class="article-nav-link article-nav-prev">
    <span class="article-nav-label">{nav_label}</span>
    <span class="article-nav-title">{prev_label}</span>
</a>'''
        else:
            radar_nav = ""

        template_path = portfolio_dir / lang / TECH_RADAR_DIR / TEMPLATE_NAME
        # EN: "March 16, 2026"
        # FR: "16 mars 2026"
        date_display = f"{MONTHS['en'][date.month]} {date.day}, {date.year}" if lang == 'en' else f"{date.day} {MONTHS['fr'][date.month]} {date.year}"

        highlights = []
        for category in grouped:
            highlights.append(grouped[category][0]['title'])
        suffix = " and more." if lang == 'en' else " et plus."
        meta_description = ", ".join(highlights[:4]) + suffix

        with open(template_path, 'r') as f:
            html = f.read()

        content = render_edition(grouped, lang)

        html = html.replace("{{WEEK}}", str(week))
        html = html.replace("{{FILENAME}}", filename)
        html = html.replace("{{DATE_ISO}}", date_iso)
        html = html.replace("{{DATE_DISPLAY}}", date_display)
        html = html.replace("{{ARTICLE_COUNT}}", str(article_count))
        html = html.replace("{{META_DESCRIPTION}}", meta_description)
        html = html.replace("{{RADAR_CONTENT}}", content)
        html = html.replace("{{RADAR_NAV}}", radar_nav)

        # Écrire le fichier
        output_path = portfolio_dir / lang / TECH_RADAR_DIR / filename
        with open(output_path, 'w') as f:
            f.write(html)

def update_index(enriched, grouped, portfolio_dir):
    for lang in ['en', 'fr']:
        index_path = portfolio_dir / lang / TECH_RADAR_DIR / INDEX_NAME
        with open(index_path, 'r') as f:
            html = f.read()

        before, rest = html.split("<!-- RADAR_CARDS -->", 1)
        existing_cards, after = rest.split("<!-- /RADAR_CARDS -->", 1)

        new_card = render_card(enriched, grouped, lang)
        all_cards = new_card + existing_cards
        # Compter les cards
        count = all_cards.count('class="radar-card"')
        if count > 12:
            last = all_cards.rfind('<a href=')
            all_cards = all_cards[:last]

        all_cards = all_cards.replace(' radar-card--hidden', '')

        # Split sur chaque card
        cards_split = all_cards.split('class="radar-card"')
        # cards_split[0] = whitespace avant la 1ère card
        # cards_split[1] = contenu après le class de la card 1
        # cards_split[2] = contenu après le class de la card 2
        # etc.

        # Reconstruire avec --hidden sur les cards 5+
        rebuilt = cards_split[0]
        for i in range(1, len(cards_split)):
            if i > 4:
                rebuilt += 'class="radar-card radar-card--hidden"' + cards_split[i]
            else:
                rebuilt += 'class="radar-card"' + cards_split[i]

        all_cards = rebuilt
        new_html = before + "<!-- RADAR_CARDS -->\n" + all_cards + "\n<!-- /RADAR_CARDS -->" + after
        with open(index_path, 'w') as f:
            f.write(new_html)

def update_home(enriched, grouped, portfolio_dir):
    for lang in ['en', 'fr']:
        index_path = portfolio_dir / lang / INDEX_NAME
        with open(index_path, 'r') as f:
            html = f.read()

        before, rest = html.split("<!-- RADAR_HOME -->", 1)
        existing_cards, after = rest.split("<!-- /RADAR_HOME -->", 1)

        new_card = render_card(enriched, grouped, lang)

        first_end = existing_cards.find('</a>')
        if first_end != -1:
            first_card = existing_cards[:first_end + len('</a>')]
        else:
            first_card = existing_cards

        new_html = before + "<!-- RADAR_HOME -->\n" + new_card + first_card + "\n<!-- /RADAR_HOME -->" + after
        with open(index_path, 'w') as f:
            f.write(new_html)

def update_nav(enriched, portfolio_dir):
    week = enriched['week']
    year = enriched['year']
    filename = f"{year}-week-{week:02d}.html"

    if week > 1:
        prev_week = week - 1
        prev_year = year
    else:
        prev_year = year - 1
        # Trouver la dernière semaine de l'année précédente
        prev_week = datetime(prev_year, 12, 28).isocalendar()[1]

    prev_filename = f"{prev_year}-week-{prev_week:02d}.html"
    prev_exists = (portfolio_dir / "en" / TECH_RADAR_DIR / prev_filename).exists()

    if not prev_exists:
        return  # première édition, rien à modifier

    for lang in ['en', 'fr']:
        prev_path = portfolio_dir / lang / TECH_RADAR_DIR / prev_filename
        with open(prev_path, 'r') as f:
            html = f.read()

        # Split sur les marqueurs
        before, rest = html.split("<!-- RADAR_NAV -->", 1)
        existing_nav, after = rest.split("<!-- /RADAR_NAV -->", 1)

        # Construire le lien NEXT (pas prev !)
        next_label = f"Week {week}" if lang == 'en' else f"Semaine {week}"
        nav_label = "Next edition &rarr;" if lang == 'en' else "Édition suivante &rarr;"
        next_link = f'''
<a href="/{lang}/{TECH_RADAR_DIR}/{filename}" class="article-nav-link article-nav-next">
    <span class="article-nav-label">{nav_label}</span>
    <span class="article-nav-title">{next_label}</span>
</a>'''

        # Ajouter next à côté du prev existant
        new_nav = existing_nav + next_link

        new_html = before + "<!-- RADAR_NAV -->" + new_nav + "\n<!-- /RADAR_NAV -->" + after
        with open(prev_path, 'w') as f:
            f.write(new_html)


if __name__ == '__main__':
    portfolio_dir = Path(sys.argv[1])
    now = datetime.now()
    year, week, _ = now.isocalendar()
    path = SCRIPT_DIR.parent / "data" / str(year) / f"week-{week:02d}-enriched.json"

    enriched = load_json(path)
    grouped = group_by_category(enriched['articles'])
    generate_edition(enriched, grouped, portfolio_dir)
    update_index(enriched, grouped, portfolio_dir)
    update_home(enriched, grouped, portfolio_dir)
    update_nav(enriched, portfolio_dir)