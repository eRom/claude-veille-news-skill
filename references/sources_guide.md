# Guide des Sources

## Hacker News

- **Collecteur** : `collectors/hackernews.py`
- **API** : Algolia HN Search — `https://hn.algolia.com/api/v1/search`
- **Auth** : Aucune
- **Rate limit** : 10 000 req/h (genereux)
- **Fiabilite** : Excellente
- **Donnees** : titre, URL, auteur, points, commentaires, date, tags
- **Filtres** : query text, tags (story/comment), numericFilters (points, date)
- **Notes** : Meilleure source pour le contenu tech communautaire. Les "Show HN" et "Ask HN" sont tagges.

### Exemple
```bash
python3 collectors/hackernews.py '{"keywords":["LLM","AI agent"],"time_range":"7d","max_results":10}'
```

---

## RSS/Atom

- **Collecteur** : `collectors/rss.py`
- **Lib** : feedparser + requests
- **Auth** : Aucune (feeds publics)
- **Rate limit** : Depend du serveur (respecter robots.txt)
- **Fiabilite** : Variable selon les feeds
- **Donnees** : titre, URL, auteur, date, resume, tags/categories
- **Config** : Liste de feeds dans `sources.json` ou en parametre
- **Notes** : Source la plus personnalisable. Porte depuis veille-ia.py.

### Feeds recommandes pour la tech/AI
| Feed | URL |
|------|-----|
| Simon Willison | `https://simonwillison.net/atom/entries/` |
| Lilian Weng | `https://lilianweng.github.io/index.xml` |
| HN RSS AI | `https://hnrss.org/newest?q=LLM+OR+Agent+OR+AI` |
| GitHub AI Blog | `https://github.blog/ai-and-ml/feed/` |

### Exemple
```bash
python3 collectors/rss.py '{"keywords":["LLM"],"time_range":"7d","max_results":5,"config":{"feeds":[{"url":"https://simonwillison.net/atom/entries/","name":"Simon Willison"}]}}'
```

---

## Reddit (a venir)

- **Collecteur** : `collectors/reddit.py`
- **API** : Reddit JSON (`/.json` suffix)
- **Auth** : Aucune pour le JSON public (User-Agent requis)
- **Rate limit** : 10 req/min sans auth
- **Subreddits cles** : r/MachineLearning, r/LocalLLaMA, r/artificial, r/ClaudeAI
- **Donnees** : titre, URL, auteur, score, commentaires, flair
- **Notes** : Le JSON endpoint ne necessite pas d'API key. Ajouter `.json` a l'URL du subreddit.

---

## GitHub Trending (a venir)

- **Collecteur** : `collectors/github_trending.py`
- **API** : GitHub REST API v3 + trending page
- **Auth** : Optionnelle (token pour rate limit plus eleve)
- **Rate limit** : 60 req/h (sans auth), 5000 req/h (avec token)
- **Donnees** : repo name, description, stars, forks, language, topics
- **Notes** : L'API ne propose pas de trending direct. Combiner search (sort=stars, created:>date) et scraping de github.com/trending.

---

## arXiv (a venir)

- **Collecteur** : `collectors/arxiv.py`
- **API** : arXiv API — `http://export.arxiv.org/api/query`
- **Auth** : Aucune
- **Rate limit** : 1 req/3s (strict)
- **Categories** : cs.AI, cs.CL, cs.LG, cs.CV
- **Donnees** : titre, auteurs, abstract, categories, PDF URL, date
- **Notes** : Source academique de reference. Abstracts tres detailles. Respecter scrupuleusement le rate limit.

---

## YouTube (a venir)

- **Collecteur** : `collectors/youtube.py`
- **Methode** : WebSearch proxy (pas d'API directe)
- **Pattern** : `site:youtube.com <keywords>`
- **Donnees** : titre, URL, channel, description
- **Notes** : Utilise WebSearch de Claude Code comme proxy. Pas de score ni de metriques sans API.

---

## X / Twitter (a venir)

- **Collecteur** : `collectors/twitter.py`
- **Methode** : WebSearch proxy
- **Pattern** : `site:x.com OR site:twitter.com <keywords>`
- **Donnees** : tweet content, URL, auteur
- **Notes** : API officielle payante et restrictive. WebSearch comme alternative gratuite mais limitee.

---

## Product Hunt (a venir)

- **Collecteur** : `collectors/producthunt.py`
- **Methode** : WebSearch proxy
- **Pattern** : `site:producthunt.com <keywords>`
- **Donnees** : product name, URL, tagline
- **Notes** : Pour decouvrir les nouveaux outils et produits tech.
