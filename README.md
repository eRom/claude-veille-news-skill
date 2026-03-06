# What About

Skill Claude Code pour la veille technologique multi-sources.

Agregation parallele de plusieurs sources (Perplexity Sonar Pro, Hacker News, RSS), scoring intelligent, deduplication, et synthese structuree — le tout pilote depuis Claude Code avec `/what-about`.

[Présentation vidéo](https://video.romain-ecarnot.com/opensource/WhatAboutVideo.mp4)

![Architecture](architecture.png)

## Utilisation rapide

```bash
# Recherche sur un sujet
/what-about LLM Agents

# Avec une fenetre temporelle
/what-about OpenAI ChatGPT 5.4 --time=30d

# Avec NotebookLM
/what-about Claude Code MCP --nlm
```

## Comment ca marche

```
/what-about "LLM agents"
       |
       v
   SKILL.md  -------->  Analyse l'intent (mode, type, keywords)
       |
       v
   whatabout.py  ----->  Charge .env + lance 8 collecteurs en PARALLELE
       |                          |
       |     +--------------------+--------------------+
       |     |          |         |         |          |
       |     v          v         v         v          v
       |  Perplexity  Hacker   RSS      Reddit      arXiv
       |  Sonar Pro   News     Feeds    JSON API    Atom/XML
       |     |          |         |         |          |
       |     |     +----+---------+---------+----+     |
       |     |     |         |          |        |     |
       |     v     v         v          v        v     v
       |  GitHub Trending  YouTube   Product Hunt
       |  Search API       API/RSS   GraphQL/RSS
       |     |               |          |
       |     +---------------+----------+
       |                     |
       v                     v
   PIPELINE (sequentiel)
       |
       |   1. Normalize  -->  JSON brut -> ScoredArticle
       |   2. Score      -->  relevance + recency + engagement + authority
       |   3. Dedupe     -->  Jaccard similarity (seuil: 0.85)
       |   4. Cross-link -->  Detection cross-source (seuil: 0.4)
       |   5. Render     -->  compact
       |
       v
   Claude synthetise + WebSearch complement
       |
       v
   Rapport sauvegarde (.what-about/reports/YYYY-MM-DD-sujet.md)
       |
       v (si --nlm)
   NotebookLM : notebook + sources + prompt Deep Research
```

### Collecteurs

| Source | Methode | Description |
|--------|---------|-------------|
| **Perplexity Sonar Pro** | API | Recherche web augmentee avec citations sourcees |
| **Hacker News** | Algolia API | Posts de la communaute tech |
| **RSS Feeds** | feedparser | Blogs curates (Simon Willison, Lilian Weng, GitHub AI...) |
| **Reddit** | API JSON publique | Subreddits tech (MachineLearning, LocalLLaMA, ClaudeAI...) |
| **arXiv** | API Atom/XML | Papers academiques (cs.AI, cs.CL, cs.LG) |
| **GitHub Trending** | API Search | Repos populaires par etoiles recentes (python, typescript, rust) |
| **YouTube** | API v3 / RSS fallback | Videos tech (Two Minute Papers, AI Explained...) |
| **Product Hunt** | GraphQL API / RSS fallback | Nouveaux produits tech (AI, dev tools, open-source) |

Les collecteurs sont executes en **parallele** via `ThreadPoolExecutor`. Chaque collecteur est un module Python independant qui herite de `BaseCollector`.

### Pipeline de scoring

Les articles sont scores sur 100 points avec 4 criteres ponderes :

| Critere | Poids | Description |
|---------|-------|-------------|
| Relevance | 0.35 | Correspondance avec les keywords |
| Recency | 0.25 | Fraicheur de l'article |
| Engagement | 0.25 | Points, commentaires |
| Authority | 0.15 | Reputation de la source |

### Options

| Option | Valeurs | Defaut | Description |
|--------|---------|--------|-------------|
| `--time` | `24h`, `7d`, `30d` | `7d` | Fenetre temporelle de collecte |
| `--domain` | ID depuis `domains.json` | auto | Force un domaine pre-configure |
| `--sources` | `hn,rss,reddit,...` | toutes | Filtrer les sources |
| `--max` | `N` | 100 | Limite articles total |
| `--nlm` | flag | off | Active NotebookLM |
| `--debug` | flag | off | Logs verbose |

Si le sujet correspond a un domaine connu (`config/domains.json`), les keywords pre-configures sont utilises automatiquement. Sinon, les keywords sont extraits du sujet.

### Commandes utilitaires

| Commande | Description |
|----------|-------------|
| `/what-about config show` | Afficher les settings |
| `/what-about config sources` | Lister les sources actives |
| `/what-about config domains` | Lister les domaines pre-configures |
| `/what-about status` | Etat des sources actives/inactives |
| `/what-about history` | Lister les rapports sauvegardes |

## Structure du projet

```
what-about/
  SKILL.md                  # Instructions Claude Code
  install.sh                # Script d'installation
  architecture.png          # Diagramme d'architecture

  scripts/
    whatabout.py            # Orchestrateur principal
    lib/
      normalize.py          # JSON brut -> ScoredArticle
      score.py              # Scoring multi-criteres
      dedupe.py             # Dedup Jaccard + cross-source linking
      render.py             # Output compact/json/md
      dates.py              # Helpers dates + recency

  collectors/
    base.py                 # Classe abstraite BaseCollector
    __init__.py             # Discovery dynamique des collecteurs
    hackernews.py           # Collecteur Hacker News
    rss.py                  # Collecteur RSS/Atom
    perplexity.py           # Collecteur Perplexity Sonar Pro
    reddit.py               # Collecteur Reddit (API JSON publique)
    arxiv.py                # Collecteur arXiv (API Atom/XML)
    github_trending.py      # Collecteur GitHub Trending (API Search)
    youtube.py              # Collecteur YouTube (API v3 + RSS fallback)
    producthunt.py          # Collecteur Product Hunt (GraphQL + RSS fallback)

  config/
    sources.json            # Configuration des sources (enabled/disabled)
    domains.json            # Domaines de veille pre-configures
    settings.json           # Parametres globaux (scoring, limites, NLM)

  references/
    notebooklm_integration.md  # Workflow NotebookLM (optionnel, --nlm)
```

## Installation

```bash
# Cloner et installer la skill
git clone <repo-url>
cd claude-veille-news-skill

# Configurer les cles API
cp .env.example .env
# Editer .env avec tes cles (voir section ci-dessous)

# Installer
./install.sh
```

### Prerequis

- Python 3.10+
- `pip install requests feedparser`

### Cles API

Copier `.env.example` en `.env` et remplir les valeurs :

| Variable | Service | Requis | Lien |
|----------|---------|--------|------|
| `PERPLEXITY_API_KEY` | Perplexity Sonar Pro | Oui | [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api) |
| `YOUTUBE_API_KEY` | YouTube Data API v3 | Non (fallback RSS) | [console.cloud.google.com](https://console.cloud.google.com/apis/credentials) |
| `GITHUB_TOKEN` | GitHub API | Non (rate limit +) | [github.com/settings/tokens](https://github.com/settings/tokens) |
| `PRODUCTHUNT_TOKEN` | Product Hunt GraphQL | Non (fallback RSS) | [api.producthunt.com](https://api.producthunt.com/v2/oauth/applications) |

Sans cles optionnelles, les collecteurs YouTube et Product Hunt basculent automatiquement en mode RSS (moins de donnees mais fonctionnel). GitHub fonctionne sans token mais avec un rate limit reduit (10 req/min au lieu de 30).

### Configuration

Les domaines de veille se configurent dans `config/domains.json` :

```json
{
  "id": "llm-ai-agents",
  "name": "LLM & AI Agents",
  "keywords": {
    "primary": ["LLM", "AI agent", "RAG", "Claude", "GPT"],
    "secondary": ["prompt engineering", "MCP", "tool use"],
    "exclude": ["crypto", "NFT"]
  }
}
```

Les sources se gerent dans `config/sources.json` (activer/desactiver, rate limits, feeds RSS...).

## Rapport de sortie

Chaque recherche genere un fichier markdown dans `.what-about/reports/` :

```
.what-about/reports/2026-03-06-openai-chatgpt-5-4.md
```

Le rapport contient la synthese structuree + toutes les URLs collectees par source.

## NotebookLM (optionnel, --nlm)

Avec le flag `--nlm`, la skill cree un notebook Google NotebookLM :
- Notebook nomme `YYYY-MM-DD — {sujet}`
- Top 50 URLs par score (hors Reddit/HN) ajoutees comme sources
- Prompt Deep Research genere et ajoute comme source texte
- L'utilisateur lance le Deep Research manuellement dans NLM

## Licence

MIT
