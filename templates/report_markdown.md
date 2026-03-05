# {{title}}

> Veille du **{{date}}** | Domaine : **{{domain_name}}** | Sources : {{source_count}} | Articles : {{article_count}}

---

## Synthese

{{synthesis}}

---

## Top Articles

{{#articles}}
### [{{title}}]({{url}})
- **Source** : {{source_name}} | **Date** : {{published}} | **Score** : {{score}}
- **Le topo** : {{summary}}
- **Pourquoi c'est important** : {{relevance_note}}
{{#tags}}`{{.}}` {{/tags}}

---
{{/articles}}

## Tendances identifiees

{{#trends}}
- **{{name}}** : {{description}}
{{/trends}}

## Sources consultees

| Source | Articles | Periode |
|--------|----------|---------|
{{#sources_summary}}
| {{name}} | {{count}} | {{time_range}} |
{{/sources_summary}}

---

*Rapport genere par What About le {{generated_at}}*
