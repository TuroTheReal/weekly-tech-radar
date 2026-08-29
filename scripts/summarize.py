import json, anthropic
from pathlib import Path
from datetime import datetime, timedelta

SCRIPT_DIR = Path(__file__).parent
SELECT_PROMPT = """You are a tech watch assistant for a DevOps/Cloud Engineer profile.

You receive a list of tech articles from the past week (index, source, title).
Select the 40 most relevant and impactful articles.

Selection criteria:
- Prioritize high-impact news: new cloud/devops features, critical vulnerabilities (CVSS 8+), major acquisitions, version releases, pricing changes
- When relevance is equal, prioritize in this order: Business > DevOps = Cloud > Tech > Security > AI/ML
- Maximize thematic diversity across all domains
- Ignore noise: quizzes, basic tutorials, event announcements, sponsored content, opinion pieces, listicles

Respond with ONLY valid JSON — a list of 40 selected indices:
[0, 5, 12, ...]

Articles:
{articles}"""

DEDUP_PROMPT = """You receive a list of tech articles (index, source, title).
Some articles may cover the SAME EVENT or SAME ANNOUNCEMENT from different sources.

Your task: identify duplicates and keep ONLY ONE article per topic (the most informative one).

Rules:
- Same event/announcement/fact = DUPLICATES, regardless of angle or source
- An opinion piece about an event AND a factual report about that same event = DUPLICATES
- Two articles mentioning the same company about DIFFERENT events = NOT duplicates

Examples:
- DUPLICATES (same event):
  3. [Ars Technica] OpenAI acquires Python toolmaker Astral
  8. [The Register] OpenAI buys Astral, maker of uv and ruff
  12. [Simon Willison] Thoughts on OpenAI acquiring Astral
  → Same event (Astral acquisition). Keep only 1.

- NOT DUPLICATES (different events):
  3. [TechCrunch] OpenAI acquires Astral for Python tooling
  7. [The Register] OpenAI signs $2B Pentagon AI contract
  → Two different events about OpenAI. Keep both.

Respond with ONLY valid JSON — the list of indices to KEEP (one per topic):
[0, 2, 3, 5, ...]

Articles:
{articles}"""

SUMMARIZE_PROMPT = """You are a tech watch assistant for a DevOps/Cloud Engineer.

For EACH article below, produce, in BOTH French and English, a rewritten TITLE (headline) and a factual SUMMARY, plus exactly one category. Process ALL articles, no exception.
French and English must be EQUIVALENT: same facts, same angle, same length. The site ships both languages side by side.

TITLE rules (title = English headline, title_fr = French headline):
- Rewrite a real headline from the facts. Do NOT translate or mechanically shorten the source title.
- A headline, not a sentence: short (max ~8 words / ~65 characters), no subordinate clause, no explanatory colon, no trailing qualifier, no final period.
- A verb is allowed, but keep it tight: subject, verb, object.
- Lead with the actor or the thing: company, product, version, CVE.
- Terminology (applies to titles AND summaries): keep a term in English when it has no genuine, commonly used French equivalent (cloud, workload, patch, log, container, pipeline, serverless, GA, endpoint, proper nouns and product/feature names). "cloud" stays "cloud", never "informatique en nuage". Translate a word ONLY when French practitioners actually use a French equivalent (compliance frameworks -> cadres de conformite, audit logs -> logs d'audit). When unsure, keep the English term rather than force an awkward translation. But never chain several untranslated English descriptive words as a noun pile in a French sentence.
  BAD  (fr): "Le template GitLab compliance frameworks pour SOC 2" / "20 ans d'informatique en nuage"
  GOOD (fr): "GitLab : modeles de cadres de conformite pour SOC 2" / "20 ans de cloud"
- No marketing tone, no clickbait, no em dash.

SUMMARY rules (summary_fr / summary_en):
- One sentence, one concrete fact. Lead with what changed: version, figure, name, CVE, price.
- Extract facts from the raw summary. If it gives no concrete fact, state only what happened. NEVER invent an impact or a benefit.
- Mirror the source's level of certainty. If the source frames it as a report, rumor, or "reportedly", keep that hedging (en: "reportedly", "a report says"; fr: conditionnel like "racheterait" or "selon un rapport"). Never turn an unconfirmed report into a stated fact, and never add doubt the source does not express.
- Native, plain language in both. Not translationese, not corporate.
- No em dash anywhere: use comma, colon or period.
- BANNED constructions (they make it read as AI-written):
  - gerund/impact tails: "..., reducing/enabling/allowing/streamlining X" / "..., réduisant/permettant/facilitant X"
  - empty intensifiers: "at scale", "significantly", "seamless", "robust", "powerful", "innovative", "next-gen" / "à grande échelle", "de manière significative", "révolutionnaire", "robuste", "puissant"
  - vague impact: "improves efficiency", "reduces overhead", "streamlines workflows" / "améliore l'efficacité", "réduit la surcharge"
  - meta: "this article", "aims to", "worth noting" / "cet article", "vise à", "il est à noter"

Examples (apply this exact style):
- Source title: "Automating root cause analysis at scale: Multi-signal correlation for cloud native incident response"
  title: "Atlassian correlates signals to find root cause"
  title_fr: "Atlassian corrèle ses signaux pour trouver la cause racine"
  summary_en: "Atlassian details a multi-signal correlation method to find the root cause of incidents across its microservices."
  summary_fr: "Atlassian détaille sa méthode de corrélation multi-signaux pour trouver la cause racine des incidents sur ses microservices."
- Source title: "Kubernetes v1.37: Pod Certificates and Cluster Trust Bundles"
  title: "Kubernetes v1.37 moves Pod Certificates to GA"
  title_fr: "Kubernetes v1.37 fait passer les Pod Certificates en GA"
  summary_en: "Kubernetes 1.37 moves Pod Certificates and Cluster Trust Bundles to GA: X.509 workload identity with auto-rotation, a replacement for service account JWTs."
  summary_fr: "Kubernetes 1.37 fait passer Pod Certificates et Cluster Trust Bundles en GA : identité de workload en X.509 à rotation auto, en remplacement des JWT de service account."
- Source title: "Scale before the spike: Predictive autoscaling for GPU workloads on Kubernetes"
  title: "A predictive autoscaler provisions GPUs before the peak"
  title_fr: "Un autoscaler prédictif provisionne les GPU avant le pic"
  summary_en: "A predictive autoscaler provisions Kubernetes GPU nodes ahead of the traffic peak instead of reacting after it."
  summary_fr: "Un autoscaler prédictif provisionne les nodes GPU Kubernetes avant le pic de trafic, au lieu de réagir après coup."

Categories (assign exactly one): Cloud, DevOps, Security, AI/ML, Business, Tech
- Cloud: cloud services (AWS, Azure, GCP), infrastructure, pricing, data centers
- DevOps: CI/CD, containers, orchestration, IaC, monitoring, observability
- Security: CVEs, vulnerabilities, malware, patches, compliance
- AI/ML: models, ML frameworks, LLMs, AI tools
- Business: acquisitions, fundraising, corporate strategy, regulation
- Tech: languages, frameworks, OS, dev tools, releases

Respond with ONLY valid JSON:
[
  {{
    "title": "English headline",
    "title_fr": "titre français",
    "url": "original url",
    "source": "source name",
    "summary_fr": "résumé factuel en français",
    "summary_en": "factual English summary",
    "category": "category"
  }}
]

Articles:
{articles}"""

STOP_WORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "for", "on",
              "with", "is", "are", "its", "by", "from", "how", "what", "why",
              "new", "now", "can", "that", "this", "it", "as", "at", "be"}

def title_keywords(title):
    """Extrait les mots significatifs d'un titre (sans stop words)."""
    words = set(title.lower().replace("—", " ").replace("-", " ").split())
    return words - STOP_WORDS

def extract_json(text):
    """Extrait le JSON d'une réponse Claude (gère blocs ```json et texte parasite)."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    # Trouver le JSON : premier [ ou { jusqu'au dernier ] ou }
    candidates = [text.find(c) for c in '[{' if text.find(c) != -1]
    if not candidates:
        raise ValueError(f"Pas de JSON trouvé dans la réponse : {text[:200]}")
    start = min(candidates)
    if text[start] == '[':
        end = text.rfind(']') + 1
    else:
        end = text.rfind('}') + 1
    return json.loads(text[start:end])

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
    """Envoie les titres à Claude API pour sélectionner les 40 plus pertinents.

    Args:
        client (anthropic.Anthropic): Client API Anthropic
        articles (list): Liste complète des articles (~300+)

    Returns:
        list: Indices des 40 articles sélectionnés
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

def dedup_articles(client, selected):
    """Envoie les articles sélectionnés à Claude API pour déduplication par sujet.

    Args:
        client (anthropic.Anthropic): Client API Anthropic
        selected (list): Liste des articles pré-sélectionnés (~40)

    Returns:
        list: Indices des articles à garder (1 par sujet)
    """
    articles_text = ""
    for i, article in enumerate(selected):
        articles_text += f"{i}. [{article['source']}] {article['title']}\n"

    prompt = DEDUP_PROMPT.format(articles=articles_text)

    response = client.messages.create(model="claude-haiku-4-5-20251001",
                                       max_tokens=4096,
                                       messages=[{"role": "user", "content": prompt}])

    result = response.content[0].text
    return extract_json(result)

def summarize_articles(client, selected):
    """Envoie les articles dédupliqués à Claude API pour résumé bilingue et catégorisation.

    Args:
        client (anthropic.Anthropic): Client API Anthropic
        selected (list): Liste des articles dédupliqués (~25-35)

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

    for attempt in range(3):
        response = client.messages.create(model="claude-haiku-4-5-20251001",
                                          max_tokens=16384,
                                          messages=[{"role": "user", "content": prompt}])
        result = response.content[0].text
        try:
            return extract_json(result)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Tentative {attempt + 1}/3 échouée : {e}")
            if attempt == 2:
                raise

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

    keep_indices = dedup_articles(client, selected)
    deduped = [selected[i] for i in keep_indices]
    print(f"Deduped: {len(selected)} -> {len(deduped)} articles")

    enriched = summarize_articles(client, deduped)
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

    # Dedup Python par mots-clés significatifs (filet de sécurité)
    final = []
    seen_keywords = []
    for article in filtered:
        kw = title_keywords(article['title'])
        is_dup = False
        for prev_kw in seen_keywords:
            common = kw & prev_kw
            # Si 3+ mots significatifs en commun → doublon
            if len(common) >= 3:
                is_dup = True
                break
        if not is_dup:
            final.append(article)
            seen_keywords.append(kw)
        else:
            print(f"  Python dedup: dropped '{article['title'][:60]}...'")

    print(f"Final: {len(filtered)} -> {len(final)} articles")

    save_json(final, articles['week'], articles['year'], articles['date_start'], articles['date_end'])
    print(f"Saved to data/{articles['year']}/week-{articles['week']:02d}-enriched.json")