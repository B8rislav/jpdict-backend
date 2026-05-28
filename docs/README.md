# Backend Documentation

Supplementary documentation for the JpDict backend. Each doc is skimmable in under five minutes.

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Component overview, request lifecycle, and ASCII diagram |
| [STRUCTURE.md](STRUCTURE.md) | Directory-by-directory file listing with roles |
| [DATA_SOURCES.md](DATA_SOURCES.md) | Corpus provenance, licenses, and import scripts |
| [API.md](API.md) | Every public endpoint: method, path, auth, schemas, rate limit |
| [DATABASE.md](DATABASE.md) | All tables with columns, indexes, FK relations, and migration cross-links |
| [NLP.md](NLP.md) | Classifier routing, SudachiPy tokenizer, jieba/pypinyin pipeline, caveats |
| [SECURITY.md](SECURITY.md) | Auth, rate limiting, input validation, security headers, threat model |
| [RUNBOOK.md](RUNBOOK.md) | Operational recipes: rebuild DB, rotate keys, drain cache, tail logs |

Start with [ARCHITECTURE.md](ARCHITECTURE.md) for the big picture, then [RUNBOOK.md](RUNBOOK.md) to get the server running.
