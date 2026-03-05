# Integration NotebookLM

## Vue d'ensemble

NotebookLM sert de couche d'analyse et de synthese. Les articles collectes sont injectes
comme sources dans un notebook, puis NLM produit des syntheses, rapports ou podcasts.

## 1. Authentification

### Verification
```bash
nlm status
```
Ou via MCP : `server_info`

### Login si necessaire
```bash
nlm login
```
Suit le flow OAuth Google. Les tokens sont sauvegardes localement.

### Changement de compte
```bash
nlm login switch <profile>
```

## 2. Gestion des notebooks

### Convention de nommage
Format : `{prefix}-{domain_id}-{date}`
Exemple : `WA-llm-ai-agents-2026-03-05`

### Creation
```bash
nlm notebook create "WA-llm-ai-agents-2026-03-05"
```
Ou MCP : `notebook_create`

### Reutilisation
Avant de creer, verifier si un notebook recent existe :
```bash
nlm notebook list
```
Si un notebook du meme domaine date de moins de `auto_cleanup_days`, le reutiliser.

### Cleanup
Supprimer les notebooks anciens (> `auto_cleanup_days` jours) :
```bash
nlm notebook delete <notebook_id>
```

## 3. Ingestion des sources

### Par URL (prefere)
Pour chaque article avec une URL valide :
```bash
nlm source add --url "https://example.com/article" --notebook <id>
```
MCP : `source_add(source_type="url", url="...")`

### Par texte (fallback)
Si l'URL n'est pas accessible ou si on a un contenu agrege :
```bash
nlm source add --text "Contenu de l'article..." --title "Titre" --notebook <id>
```
MCP : `source_add(source_type="text", text="...")`

### Rate limiting
- Respecter les limites : max 50 sources par notebook
- Espacer les ajouts de 500ms minimum
- En cas d'erreur 429, attendre 5s et retenter

## 4. Deep Research

### Lancement
```bash
nlm research start --notebook <id> --query "Comment implementer un RAG multimodal en production ?"
```
MCP : `research_start`

### Suivi
```bash
nlm research status --notebook <id>
```
MCP : `research_status`

Poll toutes les 10s jusqu'a completion (timeout: 5 min).

### Import des resultats — OBLIGATOIRE
```bash
nlm research import --notebook <id>
```
MCP : `research_import`

**IMPORTANT** : cet appel est OBLIGATOIRE apres la completion de la deep research.
Sans lui, les sources decouvertes restent en attente et ne sont PAS integrees au notebook.
Le `notebook_query` qui suit ne beneficiera pas des resultats de la deep research si cette
etape est sautee. Toujours appeler `research_import` AVANT `notebook_query`.

## 5. Generation de rapports

### Query simple (synthese)
```bash
nlm query --notebook <id> "Synthetise les articles en un rapport structure avec les tendances cles"
```
MCP : `notebook_query`

### Podcast audio
```bash
nlm studio create --type audio --notebook <id>
nlm studio status --notebook <id>  # Poll
nlm download --type audio --notebook <id> --output rapport.wav
```

## 6. Workflow complet (mode veille)

```
1. Auth check
   |
2. notebook_list -> chercher notebook existant pour le domaine
   |
   +-- Existe et recent ? -> reutiliser
   +-- Sinon -> notebook_create
   |
3. Pour chaque article (top N par score) :
   source_add(url=article.url)
   sleep(500ms)
   |
4. notebook_query("Synthetise ces articles tech...")
   |
5. Recuperer la reponse -> integrer au rapport
   |
6. (Optionnel) studio_create(type=audio) -> podcast
```

## 7. Workflow complet (mode research)

```
1. Auth check
   |
2. notebook_create (temporaire)
   |
3. Injecter articles collectes comme sources
   |
4. research_start(query=question_utilisateur)
   |
5. Poll research_status toutes les 10s
   |
6. research_import
   |
7. notebook_query("Reponds a: {question} en te basant sur toutes les sources")
   |
8. Recuperer synthese -> rapport
   |
9. (Optionnel) Cleanup notebook temporaire
```

## Erreurs courantes

| Erreur | Cause | Solution |
|--------|-------|----------|
| `401 Unauthorized` | Tokens expires | `nlm login` |
| `429 Too Many Requests` | Rate limit | Attendre et retenter |
| `Source limit reached` | > 50 sources | Prioriser les articles |
| `Research timeout` | > 5 min | Reduire le scope de la query |
