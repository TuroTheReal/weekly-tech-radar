# Weekly Tech Radar

<p align="center">
  <img src="https://img.shields.io/badge/Status-Active-brightgreen.svg"/>
  <img src="https://img.shields.io/badge/Updated-2026--03-blue.svg"/>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Claude_Haiku-Anthropic-6B4FBB?logo=anthropic&logoColor=white"/>
  <img src="https://img.shields.io/badge/GitHub_Actions-CI/CD-2088FF?logo=githubactions&logoColor=white"/>
</p>

<p align="center">
  <i>Automated weekly tech watch pipeline — collects, summarizes and publishes curated tech news to my portfolio</i>
</p>

---

## 📑 Table of Contents

- [📌 About](#-about)
- [🏗️ Architecture](#️-architecture)
- [📁 Project Structure](#-project-structure)
- [✅ Prerequisites](#-prerequisites)
- [🚀 Quick Start](#-quick-start)
- [⚙️ Configuration](#️-configuration)
- [📖 Usage](#-usage)
- [📝 Related Resources](#-related-resources)

---

## 📌 About

Automated pipeline that generates a weekly tech radar edition for my [portfolio](https://arthur-portfolio.com). Every Saturday, it collects articles from 27 RSS/Atom feeds, uses Claude Haiku to select and summarize the most relevant ones (FR + EN), generates bilingual HTML pages, and opens a PR on the portfolio repo.

### Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| AI | Claude Haiku 4.5 (Anthropic API) — selection, dedup, summarization |
| RSS Parsing | feedparser |
| HTML Generation | Jinja2-style string templating |
| CI/CD | GitHub Actions (cron + workflow_dispatch) |
| Target | [Portfolio](https://github.com/TuroTheReal/Portfolio) (Netlify) |

### Features

- **27 RSS/Atom sources** — Cloud, DevOps, AI, Security, Tech, Business (EN + FR)
- **AI-powered curation** — Claude selects top 40 articles, deduplicates, categorizes and summarizes in FR + EN
- **Full HTML generation** — Edition page, listing card, homepage preview, inter-edition navigation
- **Automated PR** — Pushes a branch and opens a PR on the portfolio repo with Netlify deploy preview
- **Idempotent** — Safe to re-run, skips already processed weeks

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   GitHub Actions (cron)                  │
│                  Every Saturday 8:00 UTC                 │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌──────────────────────┐     27 RSS/Atom feeds
│   1. collect.py      │◄──── AWS, K8s, Docker, CNCF,
│   Parse RSS feeds    │      GitHub, TechCrunch, etc.
│   Filter last 7 days │
└──────────┬───────────┘
           │ data/YYYY/week-XX.json
           ▼
┌──────────────────────┐     Anthropic API
│   2. summarize.py    │◄──── Claude Haiku 4.5
│   Select top 40      │      - Selection
│   Deduplicate        │      - Deduplication
│   Summarize FR + EN  │      - Bilingual summaries
│   Categorize         │      - Category assignment
└──────────┬───────────┘
           │ data/YYYY/week-XX-enriched.json
           ▼
┌──────────────────────┐     Portfolio repo
│   3. publish.py      │────► git clone → generate HTML
│   generate_html.py   │      → commit → push branch
│   Clone portfolio    │      → open PR
│   Generate HTML      │
│   Open PR            │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│   Netlify            │
│   Deploy preview     │
│   on PR              │
└──────────────────────┘
```

### Pipeline Flow

1. **Collect** — Parses 27 RSS/Atom feeds, filters articles from the last 7 days, saves raw data
2. **Summarize** — Claude Haiku selects top 40, deduplicates (~35), writes FR + EN summaries, assigns categories (cloud, devops, ia, business, tech, secu)
3. **Publish** — Clones portfolio repo, generates edition HTML (FR + EN), updates listing + homepage cards + inter-edition nav, commits, pushes branch, opens PR

---

## 📁 Project Structure

```
weekly-tech-radar/
├── scripts/
│   ├── collect.py             # RSS/Atom feed parser
│   ├── summarize.py           # Claude AI selection + summarization
│   ├── generate_html.py       # Bilingual HTML generation (edition, cards, nav)
│   ├── publish.py             # Git clone, commit, push, PR creation
│   └── sources.yaml           # 27 RSS/Atom feed definitions
├── data/                      # Generated data (git-ignored)
│   └── 2026/
│       ├── week-XX.json       # Raw collected articles
│       └── week-XX-enriched.json  # AI-enriched articles (summaries, categories)
├── .github/
│   └── workflows/
│       └── weekly.yml         # GitHub Actions workflow
├── .env.example               # Environment variables template
├── .gitignore
├── README.md
├── requirements.txt
└── roadmap.md                 # Planned features and improvements
```

---

## ✅ Prerequisites

### Required

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | >= 3.12 | |
| Anthropic API key | — | [console.anthropic.com](https://console.anthropic.com) |
| GitHub PAT | — | With `repo` scope on the portfolio repo |

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 🚀 Quick Start

### TL;DR

```bash
# Run full pipeline locally
python3 scripts/collect.py
python3 scripts/summarize.py
python3 scripts/publish.py --local /path/to/Portfolio
```

### Step by Step

```bash
# 1. Clone
git clone https://github.com/TuroTheReal/weekly-tech-radar.git
cd weekly-tech-radar

# 2. Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and PAT_PORTFOLIO in .env

# 3. Run
python3 scripts/collect.py        # Collect RSS feeds
python3 scripts/summarize.py      # AI selection + summarization
python3 scripts/publish.py        # Generate HTML + open PR
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude Haiku |
| `PAT_PORTFOLIO` | GitHub Personal Access Token (repo scope) for PR creation |

### GitHub Actions Secrets

Same variables must be configured in the repo's GitHub Actions secrets:
- `ANTHROPIC_API_KEY`
- `PAT_PORTFOLIO`

### RSS Sources

Edit `scripts/sources.yaml` to add/remove/modify feeds. Each source requires:

```yaml
- name: "Source Name"
  url: "https://example.com/feed.xml"
  lang: "en"
  description: "What this source covers"
  category: "cloud/devops/ai/security/business/general"
```

---

## 📖 Usage

### Automated (GitHub Actions)

The pipeline runs automatically every **Saturday at 8:00 UTC** via cron.

Manual trigger: **Actions** tab → **Weekly Tech Radar** → **Run workflow**

### Local Development

```bash
# Collect only (test RSS parsing)
python3 scripts/collect.py

# Summarize only (requires collected data + API key)
python3 scripts/summarize.py

# Publish to local portfolio repo (no PR, no push)
python3 scripts/publish.py --local /path/to/Portfolio
```

### Output

Each run generates:
- `data/YYYY/week-XX.json` — Raw articles
- `data/YYYY/week-XX-enriched.json` — Enriched articles (summaries FR + EN, categories)
- PR on [Portfolio](https://github.com/TuroTheReal/Portfolio) with:
  - `en/tech-radar/YYYY-week-XX.html` — Edition page EN
  - `fr/tech-radar/YYYY-week-XX.html` — Edition page FR
  - Updated listing pages (new card)
  - Updated homepage previews (latest 2 editions)
  - Updated inter-edition navigation links

---

## 📝 Related Resources

The weekly editions published by this pipeline are available on my portfolio:

- 🛰️ [Tech Radar](https://arthur-portfolio.com/en/tech-radar) — Weekly curated tech watch

---

**Last Updated**: 2026-03-28
**License**: MIT
