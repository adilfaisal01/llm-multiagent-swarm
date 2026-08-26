---
name: finance
description: "Financial research — 5 parallel workers covering fundamentals, valuation, comparables, risks, and recent news, sourcing from SEC filings, market data, and web sources."
version: 1.0.0
category: research
tags: [finance, investing, markets, valuation, business]
trigger: "When the question concerns companies, markets, financials, valuation, investments, or business performance."
related_skills: [research, fact-check, data-analysis]
platforms: [linux, macos, windows]
triggers: [finance, stock, company, earnings, revenue, valuation, market, investment, fund, financial]
tools: [web_search, web_extract, http_request, sql_query, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: parallel
---

# Finance Research Swarm

## When to Use

Questions about companies, financial performance, valuation, markets, or investment products. Workers source from SEC filings, financial statements, market-data APIs (via `http_request`), and reputable business media.

## Workflow

1. **Vera** — fundamentals: revenue, earnings, balance sheet, cash flow.
2. **Cyrus** — valuation: multiples, ratios, how the market prices it.
3. **Romy** — comparables: similar companies and how they stack up.
4. **Ash** — risks: debt, litigation, market exposure, headwinds.
5. **Zara** — news: recent earnings, guidance, and market reactions.

All 5 run in parallel. Each worker prefers primary filings (SEC/EDGAR, company reports), may pull structured data via `http_request` to market-data APIs and `sql_query` on any provided dataset, and logs every finding + source URL with scratchpad_add. The orchestrator synthesizes the final answer with citations. Not investment advice.

## Team

| Agent | Model | Angle |
|-------|-------|-------|
| Vera | gpt-oss:120b-cloud | Fundamentals — financial statements and growth |
| Cyrus | nemotron-3-nano:30b-cloud | Valuation — multiples, ratios, market pricing |
| Romy | gemma4:31b-cloud | Comparables — peers and relative standing |
| Ash | deepseek-v4-flash:cloud | Risks — debt, exposure, headwinds |
| Zara | gpt-oss:120b-cloud | Recent — earnings, guidance, reactions |

## Running under swarm

```bash
python3 -m swarm --skill finance --goal "Analyze the financial health of [company]"
```

## Running under Hermes

Delegate 5 parallel research tasks (one per angle above) with web_search, web_extract, and http_request tools. Prefer SEC filings and primary financial statements. Collect and synthesize with citations. Disclaim that outputs are not investment advice.
