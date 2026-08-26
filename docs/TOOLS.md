# Tool Catalog

Every tool lives in `swarm/tools/` and extends `BaseTool`. Tools are
auto-discovered by the `ToolRegistry`; skills reference them **by name** in
`SKILL.md` frontmatter.

| Tool | Module | Description | Logs to scratchpad | Cache |
|------|--------|-------------|--------------------|-------|
| `web_search` | `web_search.py` | Search the web (DuckDuckGo/SearXNG/Google) | sources + findings | yes |
| `web_extract` | `web_extract.py` | Read content from a URL | sources + findings | yes |
| `scratchpad_add` | `scratchpad.py` | Log raw findings to the shared scratchpad | findings | no |
| `read_image` | `vision.py` | Read text/numbers from images via the vision model | no | no |
| `read_file` | `file_reader.py` | Read .txt/.csv/.json/.xml/.xlsx/.docx files | no | no |
| `python_exec` | `python_exec.py` | Execute Python code for calculations/processing | no | no |
| `wikipedia_search` | `wikipedia_search.py` | Search Wikipedia (MediaWiki API, no key) | sources + findings | yes |
| `arxiv_search` | `arxiv_search.py` | Search arXiv for academic papers (Atom API, no key) | sources + findings | yes |
| `github_search` | `github_search.py` | Search GitHub repos/issues/code (`GITHUB_TOKEN` optional) | sources + findings | yes |
| `wayback_machine` | `wayback_machine.py` | Find archived snapshots of a URL (Wayback Machine) | sources + findings | yes |
| `http_request` | `http_request.py` | Generic REST API client (GET/POST/PUT/DELETE) | findings | yes |
| `pdf_extract` | `pdf_extract.py` | Extract text from PDF files (requires `pdf` extra) | findings | no |
| `sql_query` | `sql_query.py` | Run read-only SELECT queries on a local SQLite DB | findings | no |
| `regex_extract` | `regex_extract.py` | Extract structured data from text with a regex | none | no |
| `text_diff` | `text_diff.py` | Unified diff between two text blobs | none | no |

## Optional-extras tools

These tools need an optional extra installed. The tool still loads and returns
a clear error string if the extra is missing — the swarm core stays stdlib-only.

| Tool | Extra | Install |
|------|-------|---------|
| `pdf_extract` | `pdf` | `pip install -e ".[pdf]"` |
