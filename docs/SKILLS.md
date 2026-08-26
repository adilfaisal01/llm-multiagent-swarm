# Skill Catalog

Every skill lives in `swarm/skills/<name>/SKILL.md`. The YAML frontmatter
declares the skill's tools (resolved against the tool registry), triggers,
recommended model, optional team, and mode. Full-pack skills also ship a
`team.json` with named workers/models/angles.

| Skill | Tools | Mode | Team | When assigned |
|-------|-------|------|------|---------------|
| `default` | web_search, web_extract, scratchpad_add | parallel | no | Fallback when no more specific skill fits |
| `research` | web_search, web_extract, scratchpad_add | parallel | yes (5) | Open-ended multi-perspective research |
| `search` | web_search, web_extract | parallel | no | Simple fact lookups (no scratchpad) |
| `vision` | read_image, web_search, web_extract, scratchpad_add | parallel | no | Questions with image attachments |
| `code` | python_exec, web_search, web_extract, scratchpad_add | parallel | no | Questions needing computation |
| `files` | read_file, read_image, web_search, web_extract, scratchpad_add | parallel | no | Questions with attached data files |
| `reverse-engineering` | python_exec, web_search, web_extract, read_file, read_image, scratchpad_add | parallel | yes (5) | Obfuscated payload analysis |
| `fact-check` | web_search, web_extract, scratchpad_add | parallel | yes (5) | Verifying claims / debunking |
| `code-debug` | python_exec, read_file, web_search, web_extract, scratchpad_add | parallel | no | Debugging code, tracing errors |
| `multi-hop` | web_search, web_extract, scratchpad_add | pipeline | no | Chaining facts across sources |
| `comparison` | web_search, web_extract, scratchpad_add | parallel | no | Comparing products/tools/options |
| `academic` | wikipedia_search, arxiv_search, web_search, web_extract, pdf_extract, scratchpad_add | parallel | yes (5) | Academic literature / papers / methodology |
| `legal` | web_search, web_extract, wayback_machine, scratchpad_add | parallel | yes (5) | Laws, statutes, court cases, legal questions |
| `medical` | wikipedia_search, arxiv_search, web_search, web_extract, scratchpad_add | parallel | yes (5) | Health, treatments, drugs, medical evidence |
| `finance` | web_search, web_extract, http_request, sql_query, scratchpad_add | parallel | yes (5) | Companies, markets, financials, valuation |
| `data-analysis` | read_file, sql_query, python_exec, regex_extract, scratchpad_add | pipeline | yes (5) | Analyzing a data file / statistics / trends |
| `summarize` | read_file, pdf_extract, web_extract, python_exec, scratchpad_add | parallel | yes (5) | Summarizing a document, PDF, or URL |
| `translate` | web_search, web_extract, scratchpad_add | parallel | yes (5) | Translating or checking a translation |
| `historical` | wayback_machine, web_search, web_extract, wikipedia_search, scratchpad_add | parallel | yes (5) | History, timelines, change over time |
| `code-review-swarm` | read_file, python_exec, web_search, scratchpad_add | parallel | yes (5) | Reviewing / critiquing code |
