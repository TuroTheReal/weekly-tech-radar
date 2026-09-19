import json, re, string, anthropic
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
- At most 3 articles PER SOURCE, whatever its volume. A source that published 50 articles this week
  does not get 50 slots, and a single vendor blog must not fill a quarter of the edition on its own.
- Ignore noise: quizzes, basic tutorials, event announcements, sponsored content, opinion pieces, listicles

Respond with ONLY valid JSON, a list of 40 selected indices:
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
- A roundup or weekly digest covering announcement X AND a dedicated article about X = DUPLICATES, keep the dedicated one
- A multi-vendor headline whose actual content is vendor A's launch AND a dedicated article on that same launch = DUPLICATES

Examples:
- DUPLICATES (same event):
  3. [Ars Technica] OpenAI acquires Python toolmaker Astral
  8. [The Register] OpenAI buys Astral, maker of uv and ruff
  12. [Simon Willison] Thoughts on OpenAI acquiring Astral
  → Same event (Astral acquisition). Keep only 1.

- DUPLICATES (multi-vendor headline vs dedicated article):
  4. [The Register] Google, Anthropic, OpenAI unveil cyber AI models
  9. [Google Blog] Google launches Gemini 3.8 Flash and its Cyber variant
  → Both are the Gemini 3.8 Flash Cyber launch. Keep only 1.

- NOT DUPLICATES (different events):
  3. [TechCrunch] OpenAI acquires Astral for Python tooling
  7. [The Register] OpenAI signs $2B Pentagon AI contract
  → Two different events about OpenAI. Keep both.

Respond with ONLY valid JSON, the list of indices to KEEP (one per topic):
[0, 2, 3, 5, ...]

Articles:
{articles}"""

SUMMARIZE_PROMPT = """You are a tech watch assistant for a DevOps/Cloud Engineer.

For EACH article below, produce, in BOTH French and English, a rewritten TITLE (headline) and a factual SUMMARY, plus exactly one category. Process ALL articles, no exception.
French and English must be EQUIVALENT: same facts, same angle. The site ships both languages side by side.
French runs about 15% longer than English for identical content. That is expected: respect the per-language limit below, never pad or truncate one language to match the other's character count.

TITLE rules (title = English headline, title_fr = French headline):
- Rewrite a real headline from the facts. Do NOT translate or mechanically shorten the source title.
- A headline, not a sentence: no subordinate clause, no explanatory colon, no trailing qualifier, no final period.
- HARD LIMIT, count characters: title (English) 65 max, title_fr (French) 75 max. Over the limit is a failure, rewrite it shorter.
- Subject, verb, object, with a CONJUGATED verb. Never a noun pile, and never a trailing status in parentheses: put Alpha/Beta/GA in the summary.
  BAD  (fr): "Kubernetes v1.37 Preemption du planificateur pour redimensionnement de Pod sur place (Alpha)"
  GOOD (fr): "Kubernetes v1.37 preempte les Pods pour les redimensionner"
- Lead with the actor or the thing: company, product, version, CVE. The reader scans the first word of
  each headline, so it has to carry information. In French, NEVER open a headline with Le, La, Les or L'.
  BAD  (fr): "Les limites de debit de GitLab.com s'alignent sur les niveaux d'abonnement"
  GOOD (fr): "GitLab.com aligne ses limites de debit sur les abonnements"
- Terminology (applies to titles AND summaries): keep a term in English when it has no genuine, commonly used French equivalent (cloud, workload, patch, log, container, pipeline, serverless, GA, endpoint, proper nouns and product/feature names). "cloud" stays "cloud", never "informatique en nuage". Translate a word ONLY when French practitioners actually use a French equivalent (compliance frameworks -> cadres de conformite, audit logs -> logs d'audit). When unsure, keep the English term rather than force an awkward translation. But never chain several untranslated English descriptive words as a noun pile in a French sentence.
  BAD  (fr): "Le template GitLab compliance frameworks pour SOC 2" / "20 ans d'informatique en nuage"
  GOOD (fr): "GitLab : modeles de cadres de conformite pour SOC 2" / "20 ans de cloud"
- FIXED translations, never improvise on these (observed mistranslations):
    sandbox escape -> evasion de sandbox        NEVER "fuite" (a leak and an escape are two different vulnerabilities)
    container breakout -> evasion de conteneur  NEVER "fuite de conteneur"
    on-call page -> alerte d'astreinte          NEVER "page"
    AI -> IA                                    always, in French prose and titles alike
- No marketing tone, no clickbait, no em dash. Never reuse the vendor's own slogan as the headline,
  say what the product actually does. Their campaign words are not facts.
  BAD  (fr): "GitLab securise l'usine logicielle a la vitesse machine"
  GOOD (fr): "GitLab detaille un modele de defense en trois couches pour le code agentique"

SUMMARY rules (summary_fr / summary_en):
- One sentence, one concrete fact. Lead with what changed: version, figure, name, CVE, price.
- Length: summary_en 240 characters max, summary_fr 290 max. Density is fine, listing is not: if you need
  a semicolon or a third comma-separated item to fit everything in, you are listing instead of summarizing.
  Keep the single most consequential fact and drop the rest.
  BAD  (fr): "GitLab 19.4 ajoute les budgets de crédits par utilisateur, la visibilité des dépenses et les
             exportations d'utilisation détaillées; les administrateurs définissent les plafonds fixes avec
             les dérogations par utilisateur pour contrôler les dépenses IA."
  GOOD (fr): "GitLab 19.4 permet de plafonner les crédits IA par utilisateur, avec dérogations ponctuelles
             et export détaillé de la consommation."
- Extract facts from the raw summary. If it gives no concrete fact, state what the article establishes, in the subject's own terms. NEVER invent an impact or a benefit.
- Mirror the source's level of certainty. If the source frames it as a report, rumor, or "reportedly", keep that hedging (en: "reportedly", "a report says"; fr: conditionnel like "racheterait" or "selon un rapport"). Never turn an unconfirmed report into a stated fact, and never add doubt the source does not express.
- Native, plain language in both. Not translationese, not corporate.
- No em dash anywhere: use comma, colon or period.
- BANNED constructions (they make it read as AI-written):
  - gerund/impact tails: "..., reducing/enabling/allowing/streamlining X" / "..., réduisant/permettant/facilitant X"
  - empty intensifiers: "at scale", "significantly", "seamless", "robust", "powerful", "innovative", "next-gen" / "à grande échelle", "de manière significative", "révolutionnaire", "robuste", "puissant"
  - vague impact: "improves efficiency", "reduces overhead", "streamlines workflows" / "améliore l'efficacité", "réduit la surcharge"
  - meta: "this article", "aims to", "worth noting" / "cet article", "vise à", "il est à noter"
  - source as subject: "CNCF article on X", "CNCF guidance on X", "GitLab addresses X" / "Article CNCF sur X", "Directives CNCF sur X"
    Say what changed or what the method is, never that an organisation published something about it.
    BAD : "CNCF guidance on integrating external identity providers with on-prem clusters using public client OAuth flows."
    GOOD: "On-prem Kubernetes clusters can delegate auth to an external identity provider via public client OAuth flows, avoiding a shared client secret."

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

# Budgets de longueur, par langue. Mesure sur les editions publiees : le francais
# fait ~19% de plus que l'anglais a contenu egal, un budget unique pousserait le
# modele a tronquer le FR. Les budgets de resume sont cales sur le p90 du publie :
# un garde-fou qui crie sur un tiers des resumes ne serait plus lu.
LENGTH_LIMITS = {"title": 65, "title_fr": 75, "summary_en": 240, "summary_fr": 290}

# Nb max d'articles portant sur le meme acteur (1er mot significatif du titre).
VENDOR_LIMIT = 3

# Quotas par catégorie, pour garder une édition variée
CATEGORY_LIMITS = {
    "Cloud": 6, "DevOps": 6, "Tech": 6, "Business": 6,
    "Security": 4, "AI/ML": 4,
}

def title_keywords(title):
    """Extrait les mots significatifs d'un titre (sans stop words ni ponctuation).

    Les tokens de version (v1.37, 3.8) sont ignores : sur une semaine de release,
    ils sont communs a des articles qui traitent de features differentes et
    feraient passer pour doublons des sujets distincts.

    Args:
        title (str): Titre de l'article

    Returns:
        set: Mots significatifs en minuscules
    """
    raw = title.lower().replace("—", " ").replace("-", " ").split()
    words = {w.strip(string.punctuation) for w in raw}
    words -= STOP_WORDS | {""}
    return {w for w in words if not re.match(r"^v?\d", w)}

def title_actor(title):
    """Renvoie l'acteur d'un titre : premier mot significatif, et sa version s'il y en a une.

    Le prompt impose "Lead with the actor or the thing", donc le premier mot porte
    le vendor ou le produit. La version est incluse dans la clé pour viser la vraie
    nuisance, une série d'articles sur la même release ("kubernetes v1.37"), sans
    plafonner les autres sujets du même produit ("kubernetes" tout court).

    Args:
        title (str): Titre de l'article

    Returns:
        str: Clé acteur en minuscules, "" si le titre est vide
    """
    words = [w.strip(string.punctuation) for w in title.lower().replace("—", " ").replace("-", " ").split()]
    words = [w for w in words if w]
    actor = next((w for w in words if w not in STOP_WORDS), "")
    version = next((w for w in words if re.match(r"^v?\d+\.\d", w)), "")
    return f"{actor} {version}".strip()

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


def post_process(enriched):
    """Filtre les articles enrichis : quotas de catégorie, doublons, plafond par acteur.

    Args:
        enriched (list): Articles enrichis renvoyés par summarize_articles()

    Returns:
        list: Articles retenus, dans l'ordre d'origine
    """
    # 1. Quotas par catégorie
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
        print(f"  {cat}: {count} -> {min(count, CATEGORY_LIMITS.get(cat, 4))}")

    # 2. Dedup par mots-clés significatifs (filet de sécurité derrière le LLM).
    # Seuil volontairement conservateur : mesuré sur 542 titres publiés, un seuil
    # à 2 produit 42 faux positifs ("supply chain", "open source" suffisent à
    # déclencher). Un doublon publié se voit en relisant la PR, un article jeté à
    # tort ne se voit pas. La vraie dédup est celle du DEDUP_PROMPT.
    deduped = []
    seen = []
    for article in filtered:
        kw = title_keywords(article['title'])
        dup_of = next(((title, sorted(kw & prev)) for prev, title in seen if len(kw & prev) >= 3), None)
        if dup_of is None:
            deduped.append(article)
            seen.append((kw, article['title']))
        else:
            # On logue la paire : un faux positif doit être jugeable d'un coup d'oeil
            print(f"  Dedup: dropped '{article['title'][:60]}'")
            print(f"    doublon de '{dup_of[0][:60]}' sur {dup_of[1]}")
    print(f"Deduped: {len(filtered)} -> {len(deduped)} articles")

    # 3. Plafond par acteur : CATEGORY_LIMITS borne les catégories, pas les vendors.
    # Sans ça, une semaine de release Kubernetes remplit la catégorie DevOps à elle seule.
    actor_count = {}
    final = []
    for article in deduped:
        actor = title_actor(article['title'])
        actor_count[actor] = actor_count.get(actor, 0) + 1
        if actor_count[actor] <= VENDOR_LIMIT:
            final.append(article)
        else:
            print(f"  Vendor cap ({actor}, max {VENDOR_LIMIT}): dropped '{article['title'][:60]}'")
    print(f"Final: {len(deduped)} -> {len(final)} articles")
    return final

def check_lengths(articles):
    """Signale les champs hors budget. Ne tronque pas : ça casserait le sens.

    Le prompt demande des longueurs, il ne les garantit pas. Le but est de voir
    les dépassements dans les logs de l'Action, pas en relisant la PR à l'oeil.

    Args:
        articles (list): Articles à vérifier

    Returns:
        list: Messages de dépassement, vide si tout tient
    """
    over = []
    for article in articles:
        for field, cap in LENGTH_LIMITS.items():
            value = article.get(field, "")
            if len(value) > cap:
                over.append(f"{field} {len(value)}/{cap} : {value}")
    return over


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

    final = post_process(enriched)

    over_budget = check_lengths(final)
    if over_budget:
        print(f"⚠ {len(over_budget)} champ(s) hors budget, à relire dans la PR :")
        for line in over_budget:
            print(f"    {line}")
    else:
        print("Longueurs : tout est dans les budgets")

    save_json(final, articles['week'], articles['year'], articles['date_start'], articles['date_end'])
    print(f"Saved to data/{articles['year']}/week-{articles['week']:02d}-enriched.json")