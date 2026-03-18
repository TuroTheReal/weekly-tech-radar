# Weekly Tech Radar — Feuille de route

## Phase 0 — Setup du repo

- [ ] Initialiser le repo Git + structure de dossiers (`scripts/`, `data/`, `.github/workflows/`)
- [ ] Créer `requirements.txt` — `feedparser`, `anthropic`, `pyyaml`, `jinja2`
- [ ] Créer `.gitignore` — `.env`, `__pycache__/`, `.venv/`
- [ ] Créer `.env.example` — `ANTHROPIC_API_KEY=`, `GITHUB_PAT=` (documentation des secrets nécessaires)

---

## Phase 1 — Collecte RSS (`scripts/collect.py`)

Premier script à coder car tout le reste en dépend.

### 1.1 — Définir les sources

- [ ] Créer `scripts/sources.yaml` — sélection finale des flux RSS
  - URL du flux
  - Nom de la source
  - Langue (fr/en)
  - Catégorie par défaut (optionnel, Claude recatégorisera)
  - Commencer avec 10-15 sources solides, ajouter plus tard si besoin
  - Voir `rss_feeds.yaml` à la racine pour la liste complète de 45 sources candidates

### 1.2 — Coder le collecteur

- [ ] Coder `scripts/collect.py` :
  - Charger `sources.yaml`
  - Pour chaque flux : parser via `feedparser`, filtrer les articles des 7 derniers jours
  - Déduplication (par URL)
  - Calcul automatique du numéro de semaine ISO
  - Sortie : `data/2026/week-XX.json` avec structure :
    ```json
    {
      "week": 12,
      "year": 2026,
      "date_start": "2026-03-16",
      "date_end": "2026-03-22",
      "articles": [
        {
          "title": "...",
          "url": "...",
          "source": "AWS Blog",
          "published": "2026-03-17",
          "language": "en",
          "summary_raw": "..."
        }
      ]
    }
    ```

### 1.3 — Test manuel

- [ ] Lancer le script, vérifier que le JSON est propre
- [ ] Ajuster les sources si certaines ne retournent rien ou sont trop bruyantes

---

## Phase 2 — Résumé via Claude API (`scripts/summarize.py`)

### 2.1 — Coder le summarizer

- [ ] Coder `scripts/summarize.py` :
  - Charger le JSON brut de la semaine
  - Construire le prompt pour Claude (Haiku 4.5) :
    - Input : titre + summary_raw + source de chaque article
    - Output attendu : résumé 1-2 lignes en FR **et** EN + catégorie assignée
  - Stratégie d'appel : **batch** (envoyer plusieurs articles par requête pour réduire coût)
  - Catégories possibles définies dans le prompt :
    - Cloud/DevOps
    - AI/ML
    - Sécurité
    - Frameworks/Langages
    - Business/Politique
    - Open Source
    - (dynamiques selon contenu)
  - Écrire le résultat enrichi :
    ```json
    {
      "summary_fr": "...",
      "summary_en": "...",
      "category": "Cloud/DevOps"
    }
    ```
  - Gestion d'erreurs : retry basique, log si un article échoue (ne pas bloquer le pipeline)

### 2.2 — Itérer sur le prompt

- [ ] Tester la qualité des résumés
- [ ] Ajuster le prompt (c'est l'étape la plus itérative)
- [ ] Vérifier la cohérence des catégories assignées

---

## Phase 3 — Génération HTML (`scripts/generate_html.py`)

### Pré-requis

Le template `template-radar.html` doit exister côté Portfolio. Arthur le design lui-même. Il faut au minimum définir les **placeholders/classes CSS** que le script va remplir.

### 3.1 — Définir le contrat template

- [ ] Variables à injecter :
  - `{{week_number}}`, `{{year}}`, `{{date_range}}`
  - Boucle sur les catégories → chaque catégorie contient une liste d'articles
  - Chaque article : `{{title}}`, `{{summary}}`, `{{url}}`, `{{source}}`

### 3.2 — Template de dev

- [ ] Créer un template HTML minimal temporaire (juste pour tester le script — le vrai design viendra dans Portfolio)

### 3.3 — Coder le générateur

- [ ] Coder `scripts/generate_html.py` :
  - Charger le JSON enrichi
  - Grouper les articles par catégorie
  - Trier les catégories (ordre fixe ou par nombre d'articles)
  - Charger le template (Jinja2)
  - Générer 2 fichiers HTML : un FR, un EN
  - Nommage : `2026-week-12.html`

### 3.4 — Test manuel

- [ ] Ouvrir les HTML générés dans un navigateur, vérifier le rendu

---

## Phase 4 — Script de push PR (`scripts/publish.py`)

- [ ] Coder `scripts/publish.py` :
  - Clone (ou sparse checkout) du repo Portfolio
  - Créer branche `radar/2026-week-XX`
  - Copier les HTML générés dans `en/tech-radar/` et `fr/tech-radar/`
  - Commit + push la branche
  - Ouvrir une PR via GitHub API ou `gh` CLI
  - Titre PR : `Tech Radar — Week XX (2026)`
  - Body PR : liste des articles inclus
- [ ] Tester manuellement — vérifier que la PR est créée correctement

---

## Phase 5 — GitHub Actions (`.github/workflows/weekly.yml`)

- [ ] Coder le workflow :
  ```yaml
  on:
    schedule:
      - cron: '0 8 * * 0'  # dimanche 8h UTC
    workflow_dispatch:        # déclenchement manuel pour les tests
  ```
  Steps :
  1. Checkout `weekly-tech-radar`
  2. Setup Python + install deps
  3. Run `collect.py`
  4. Run `summarize.py`
  5. Run `generate_html.py`
  6. Run `publish.py`
  7. Commit le JSON dans `weekly-tech-radar` (archivage des données)
  - Secrets nécessaires : `ANTHROPIC_API_KEY`, `PORTFOLIO_PAT`
- [ ] Tester le workflow via `workflow_dispatch`

---

## Phase 6 — Rétention & nettoyage

- [ ] Ajouter la logique de rétention (dans `publish.py` ou `scripts/cleanup.py`) :
  - Supprimer les fichiers HTML de plus de 12 semaines dans la PR
  - Mettre à jour `index.html` si nécessaire

---

## Phase 7 — Finalisation

- [ ] README.md du repo `weekly-tech-radar`
- [ ] Design côté Portfolio — `template-radar.html` + `index.html` (travail Arthur)
- [ ] Première semaine live — ajuster sources/prompt selon résultats

---

## Ordre de priorité

| Ordre | Quoi | Dépend de |
|-------|------|-----------|
| 1 | Setup repo (phase 0) | — |
| 2 | `sources.yaml` | — |
| 3 | `collect.py` | sources.yaml |
| 4 | `summarize.py` | collect.py |
| 5 | Contrat template | — (en parallèle) |
| 6 | `generate_html.py` | summarize.py + template |
| 7 | `publish.py` | generate_html.py |
| 8 | `weekly.yml` | tous les scripts |
| 9 | Rétention/cleanup | publish.py |
| 10 | README + design Portfolio | tout le reste |

---

## Phase 2 (future)

- Email newsletter (Resend API ou Buttondown)
- Preview "actu rapide" sur homepage Portfolio (3-5 top news)
