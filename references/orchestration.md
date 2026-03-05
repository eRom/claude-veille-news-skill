# Orchestration — Flows detailles

## Mode Veille

```
Utilisateur: "/what-about veille llm-ai-agents"
                    |
                    v
    +---------------------------+
    | 1. PARSE INTENT           |
    | - Mode: veille            |
    | - Domain: llm-ai-agents   |
    | - Params: defaults        |
    +---------------------------+
                    |
                    v
    +---------------------------+
    | 2. LOAD CONFIG            |
    | - domains.json -> domain  |
    | - sources.json -> sources |
    | - settings.json -> prefs  |
    +---------------------------+
                    |
                    v
    +---------------------------+
    | 3. COLLECT                |
    | Pour chaque source active |
    | du domaine:               |
    | $ python3 collectors/     |
    |   <source>.py '<params>'  |
    | -> JSON stdout            |
    +---------------------------+
                    |
                    v
    +---------------------------+
    | 4. DEDUP & SCORE          |
    | - Dedup par URL + titre   |
    | - Score composite:        |
    |   recence * 0.25          |
    |   pertinence * 0.35       |
    |   engagement * 0.25       |
    |   autorite * 0.15         |
    | - Tri par score desc      |
    +---------------------------+
                    |
                    v
    +---------------------------+
    | 5. NLM SYNTHESIS          |
    | Si notebooklm.enabled:    |
    | - Notebook: get or create |
    |   "{prefix}-{domain}"     |
    | - Inject top N articles   |
    |   comme sources URL/texte |
    | - notebook_query pour     |
    |   synthese                |
    +---------------------------+
                    |
                    v
    +---------------------------+
    | 6. FORMAT                 |
    | - Appliquer template      |
    |   report_markdown.md      |
    | - Injecter synthese NLM   |
    | - Sections par theme      |
    +---------------------------+
                    |
                    v
    +---------------------------+
    | 7. DELIVER                |
    | - Afficher rapport        |
    | - Sauvegarder fichier     |
    |   ~/Documents/WhatAbout/  |
    +---------------------------+
```

## Mode Research

```
Utilisateur: "/what-about research Comment implementer un RAG multimodal ?"
                    |
                    v
    +---------------------------+
    | 1. PARSE INTENT           |
    | - Mode: research          |
    | - Query: "Comment impl.." |
    +---------------------------+
                    |
                    v
    +---------------------------+
    | 2. DERIVE STRATEGY        |
    | - Keywords primaires:     |
    |   RAG, multimodal         |
    | - Keywords secondaires:   |
    |   vector DB, embeddings,  |
    |   production, deployment  |
    | - Sources pertinentes:    |
    |   arxiv, HN, github, RSS |
    +---------------------------+
                    |
                    v
    +---------------------------+
    | 3. COLLECT                |
    | Meme pattern que veille   |
    | mais avec keywords derives|
    | et time_range plus large  |
    | (30d par defaut)          |
    +---------------------------+
                    |
                    v
    +---------------------------+
    | 4. NLM DEEP RESEARCH      |
    | - Creer notebook temporaire|
    | - Injecter articles        |
    | - research_start avec      |
    |   la question originale    |
    | - Poll research_status     |
    | - research_import resultats|
    +---------------------------+
                    |
                    v
    +---------------------------+
    | 5. SYNTHESIZE             |
    | - Combiner:               |
    |   * Articles collectes    |
    |   * Resultats NLM         |
    | - Structurer en sections  |
    | - Identifier les trends   |
    +---------------------------+
                    |
                    v
    +---------------------------+
    | 6. DELIVER                |
    | - Rapport structure       |
    | - Conclusions + next steps|
    | - Liste de toutes les     |
    |   sources utilisees       |
    +---------------------------+
```

## Quand utiliser Agent Teams vs sequentiel

### Sequentiel (par defaut)
- Nombre de sources <= 3
- Mode quick
- Sources rapides (HN, RSS)

### Agent Teams (collecte parallele)
- Nombre de sources >= 4
- Mode deep
- Sources lentes (arXiv, scraping)
- Plusieurs domaines en une session

### Pattern Agent Teams
```
Team Lead: orchestre la collecte
  |-- Agent "collect-hn": hackernews.py
  |-- Agent "collect-rss": rss.py
  |-- Agent "collect-reddit": reddit.py
  |-- Agent "collect-arxiv": arxiv.py
  |
  v Merge resultats
  |
  v Dedup + Score
  |
  v NLM synthesis
  |
  v Format + Deliver
```

Chaque agent collecteur tourne dans un subprocessus isole,
retourne ses resultats via TaskUpdate, puis le lead merge.
