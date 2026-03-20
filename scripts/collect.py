import yaml, feedparser, json
from datetime import datetime, timedelta
from time import mktime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def load_sources():
    """Charge les sources RSS depuis sources.yaml.

    Returns:
        list: Liste des sources (name, url, lang, category, description)
    """
    with open(SCRIPT_DIR / "sources.yaml", 'r') as f:
        data = yaml.safe_load(f)
    return data["sources"]

def fetch_feed(source):
    """Parse un feed RSS/Atom et retourne le résultat feedparser.

    Args:
        source (dict): Infos de la source (name, url, lang, etc.)

    Returns:
        FeedParserDict: Objet feedparser avec .entries (liste des articles)
    """
    return feedparser.parse(source['url'])

def filter_recent(articles):
    """Filtre les articles publiés dans les 7 derniers jours.

    Args:
        articles (list): Liste d'entries feedparser

    Returns:
        list: Articles de moins de 7 jours
    """
    recent_articles = []
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    for article in articles:
        date_raw = article.get("published_parsed") or article.get("updated_parsed")
        if not date_raw:
            continue
        date = datetime.fromtimestamp(mktime(date_raw))
        if date < week_ago:
            continue
        recent_articles.append(article)
    return recent_articles

def save_json(articles):
    """Sauvegarde les articles dans data/YYYY/week-XX.json.

    Args:
        articles (list): Liste des articles formatés
    """
    now = datetime.now()
    year, week, _ = now.isocalendar()
    week_ago = now - timedelta(days=7)

    # Construire le chemin et créer le dossier
    output_dir = SCRIPT_DIR.parent / "data" / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"week-{week:02d}.json"

    # Structure complète
    data = {
        "week": week,
        "year": year,
        "date_start": week_ago.strftime("%Y-%m-%d"),
        "date_end": now.strftime("%Y-%m-%d"),
        "articles": articles
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    sources = load_sources()
    weekly_articles = []

    for source in sources:
        feed = fetch_feed(source)
        recent = filter_recent(feed.entries)
        print(f"  {source['name']}: {len(recent)} articles")
        for article in recent:
            weekly_articles.append({
                "title": article.title,
                "url": article.link,
                "source": source['name'],
                "language": source['lang'],
                "category": source['category'],
                "published": datetime.fromtimestamp(mktime(article.get("published_parsed") or article.get("updated_parsed"))).strftime("%Y-%m-%d"),
                "summary_raw": article.get("summary", "")
            })
            
    # Déduplication par URL
    seen_urls = set()
    unique_articles = []
    for article in weekly_articles:
        if article['url'] not in seen_urls:
            seen_urls.add(article['url'])
            unique_articles.append(article)
    print(f"Collected {len(weekly_articles)} articles from {len(sources)} sources")
    print(f"Dedup: {len(weekly_articles)} -> {len(unique_articles)} articles")
    save_json(unique_articles)