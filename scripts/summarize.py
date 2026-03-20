import json, anthropic
from pathlib import Path
from datetime import datetime, timedelta

SCRIPT_DIR = Path(__file__).parent
SELECT_PROMPT = """Tu es un assistant de veille technologique pour un profil DevOps/Cloud Engineer.

Tu reçois la liste des articles tech de la semaine (indice, source, titre).
Sélectionne les 40 articles les plus pertinents et importants.

Règles :
- 40 articles
- Privilégie les infos à impact (nouvelles features, failles majeures, mouvements business, sorties de version)
- À pertinence égale, priorise dans cet ordre : Business > DevOps = Cloud > Tech > Security > AI/ML
- Privilégie la diversité thématique (cloud, devops, sécurité, IA, business, tech)
- Ignore le bruit (quizzes, tutos basiques, événements mineurs, articles sponsorisés)
- Pas de doublons (même sujet couvert par plusieurs sources = garder 1 seul)

Réponds UNIQUEMENT en JSON valide, une liste des indices sélectionnés :
[0, 5, 12, ...]

Articles :
{articles}"""

SUMMARIZE_PROMPT = """Tu es un assistant de veille technologique.

Pour CHAQUE article ci-dessous, écris un résumé factuel de 1-2 lignes en français ET en anglais.
Résume TOUS les articles, sans en ignorer aucun.
Pas d'interprétation, pas d'éditorial, uniquement les faits.
Attribue une catégorie parmi : Cloud, DevOps, Security, AI/ML, Business, Tech

Réponds UNIQUEMENT en JSON valide :
[
  {{
    "title": "titre original",
    "url": "url originale",
    "source": "nom de la source",
    "summary_fr": "résumé factuel en français",
    "summary_en": "factual summary in english",
    "category": "catégorie"
  }}
]

Articles :
{articles}"""

def extract_json(text):
    """Extrait le JSON d'une réponse Claude (gère les blocs ```json)."""
    text = text.strip()
    if text.startswith("```"):
        # Virer la première ligne (```json) et la dernière (```)
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)

def load_json(path):
    """Charge un fichier JSON.

    Args:
        path (Path): Chemin vers le fichier JSON

    Returns:
        dict: Contenu du fichier (week, year, articles, etc.)
    """
    with open(path, 'r') as f:
        return json.load(f)

def select_articles(client, articles):
    """Envoie les titres à Claude API pour sélectionner les 20 plus pertinents.

    Args:
        client (anthropic.Anthropic): Client API Anthropic
        articles (list): Liste complète des articles

    Returns:
        list: Indices des 20 articles sélectionnés
    """
    articles_text = ""
    for i, article in enumerate(articles):
        articles_text += f"{i}. [{article['source']}] {article['title']}\n"

    prompt = SELECT_PROMPT.format(articles=articles_text)

    response = client.messages.create(model="claude-haiku-4-5-20251001",
                                       max_tokens=4096,
                                       messages=[{"role": "user", "content": prompt}])

    result = response.content[0].text
    return extract_json(result)

def summarize_articles(client, selected):
    """Envoie les 20 articles sélectionnés à Claude API pour résumé bilingue et catégorisation.

    Args:
        client (anthropic.Anthropic): Client API Anthropic
        selected (list): Liste des 20 articles sélectionnés

    Returns:
        list: Articles enrichis (summary_fr, summary_en, category)
    """
    articles_text = ""
    for i, article in enumerate(selected):
        articles_text += f"""---
Titre : {article['title']}
URL : {article['url']}
Source : {article['source']}
Résumé brut : {article.get('summary_raw', '')}
---
"""

    prompt = SUMMARIZE_PROMPT.format(articles=articles_text)

    response = client.messages.create(model="claude-haiku-4-5-20251001",
                                      max_tokens=8192,
                                      messages=[{"role": "user", "content": prompt}])

    result = response.content[0].text
    return extract_json(result)

def save_json(enriched, week, year, date_start, date_end):
    """Sauvegarde les articles enrichis dans data/YYYY/week-XX-enriched.json.

    Args:
        enriched (list): Liste des articles enrichis
        week (int): Numéro de semaine ISO
        year (int): Année
        date_start (str): Date de début (YYYY-MM-DD)
        date_end (str): Date de fin (YYYY-MM-DD)
    """
    # Construire le chemin et créer le dossier
    output_dir = SCRIPT_DIR.parent / "data" / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"week-{week:02d}-enriched.json"

    # Structure complète
    data = {
        "week": week,
        "year": year,
        "date_start":  date_start,
        "date_end": date_end,
        "articles": enriched
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    now = datetime.now()
    year, week, _ = now.isocalendar()
    path = SCRIPT_DIR.parent / "data" / str(year) / f"week-{week:02d}.json"

    articles = load_json(path)
    print(f"Loaded {len(articles['articles'])} articles from week {articles['week']}")

    client = anthropic.Anthropic()
    indices = select_articles(client, articles['articles'])
    print(f"Selected {len(indices)} articles")

    selected = [articles['articles'][i] for i in indices]
    enriched = summarize_articles(client, selected)
    print(f"Summarized {len(enriched)} articles")

    # Post-processing : limiter par catégorie
    CATEGORY_LIMITS = {
        "Cloud": 6, "DevOps": 6, "Tech": 6, "Business": 6,
        "Security": 4, "AI/ML": 4,
    }
    category_count = {}
    filtered = []
    for article in enriched:
        cat = article['category']
        max_cat = CATEGORY_LIMITS.get(cat, 4)
        category_count[cat] = category_count.get(cat, 0) + 1
        if category_count[cat] <= max_cat:
            filtered.append(article)
    print(f"Filtered: {len(enriched)} -> {len(filtered)} articles")
    for cat, count in category_count.items():
        max_cat = CATEGORY_LIMITS.get(cat, 4)
        kept = min(count, max_cat)
        print(f"  {cat}: {count} -> {kept}")

    save_json(filtered, articles['week'], articles['year'], articles['date_start'], articles['date_end'])
    print(f"Saved to data/{articles['year']}/week-{articles['week']:02d}-enriched.json")