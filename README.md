# AIO Agents MCP

**Demand-side procurement attribution for retail grocery · 2,235 banners · 28 markets · ERP × Cloud × Procurement attribution.**

Operated by [GreenCore Solutions Corp.](https://gsc-cpg.com)

---

## What this is

A live MCP server exposing GreenCore's demand-side procurement attribution dataset to AI agents.

AI agents — Claude, GPT, Gemini, Grok, Mistral — connect to `mcp.gsc-cpg.com` and query *where* a CPG product can land: which retail grocery banners run which ERP system, on which cloud, with which procurement platform, in which market.

**Companion to [`io.github.gsc-em/a2a-mcp-cpg`](https://github.com/gsc-em/a2a-mcp-cpg)** — supply-side catalog (rails, GTINs, signals). Together: GSC's full agentic CPG procurement surface.

**MCP endpoint:** `https://mcp.gsc-cpg.com`

**Registry:** `io.github.gsc-em/aio-agents-mcp`

---

## Tools

| Tool | Purpose |
| --- | --- |
| `find_banners` | Find banners matching country / ERP / cloud / procurement / confidence filters. |
| `get_market_summary` | Get attribution totals + ERP / cloud / procurement breakdowns for a single market. |
| `get_strike_targets` | Return ranked list of highest-confidence agentic-ready banners. |
| `get_agentic_readiness` | Get readiness scorecard by region (% of banners with attribution). |
| `count_attribution_coverage` | Global dataset stats — totals, distinct ERPs / clouds / platforms. |

---

## Dataset

| Dimension | Coverage |
| --- | --- |
| Total banners | 2,235 |
| Markets | 28 (18 EU + 10 LatAm) |
| Banners with full attribution | 1,218 (54%) |
| Confirmed | 276 |
| Probable | 210 |
| Inferred | 319 |
| Contested | 26 |
| Distinct ERP systems | 209 (SAP S/4HANA, Oracle Fusion, D365, Infor, Totvs, etc.) |
| Distinct clouds | 105 (Azure, GCP, STACKIT, AWS, OCI, HEC, on-prem, hybrid) |
| Distinct procurement platforms | 94 (Ariba, Coupa, Ivalua, GEP, JAGGAER, Zycus, Native, etc.) |

Attribution is 6-LLM cross-validated (ChatGPT, Gemini, Copilot, Perplexity, Mistral, Grok) where possible. Confidence tiers reflect cross-LLM agreement: `CONFIRMED` (5-of-6 or 6-of-6), `PROBABLE` (partial agreement), `INFERRED` (corporate-parent inheritance), `CONTESTED` (sources disagree), `UNKNOWN` (no reliable attribution).

---

## Markets covered

**EU:** Germany · France · United Kingdom · Ireland · Italy · Spain · Portugal · Netherlands · Belgium · Luxembourg · Austria · Switzerland · Norway · Sweden · Denmark · Finland · Poland · Czech Republic

**LatAm:** Brazil · Mexico · Colombia · Chile · Argentina · Peru · Ecuador · Costa Rica + Central America · Dominican Republic · Puerto Rico + Caribbean

---

## Ghost Headers

Every response carries the GreenCore Ghost Header set:

```
X-GSC-Protocol: ACM-68000
X-GSC-Version: 1.0.0
X-GSC-Router: mcp.gsc-cpg.com
X-GSC-Role: mcp-server
X-GSC-Operator: GreenCore Solutions Corp.
X-GSC-Registry: io.github.gsc-em/aio-agents-mcp
X-MCP-Server: https://mcp.gsc-cpg.com
X-MCP-Registry: io.github.gsc-em/aio-agents-mcp
X-Agent-Access: Claude,Mistral,Gemini,Grok,OpenAI
```

---

## Architecture

```
github.com/gsc-em/aio-agents-mcp     ← this repo
       │
       ▼
Azure Container Apps (France Central)
  ├─ ca-aio-agents-mcp               (FastMCP server, this code)
  └─ pg-aio-agents-fr                (Postgres Flexible Server, dataset)
       │
       ▼
mcp.gsc-cpg.com                       ← public MCP endpoint
```

**Subscription:** AIO Agents (`gsc-em.com` tenant)
**Resource group:** `rg-aio-agents-fr`
**Region:** France Central

---

## Companion server

GreenCore operates two production MCP servers in the official MCP Registry:

| Repository | Endpoint | Function |
| --- | --- | --- |
| `io.github.gsc-em/a2a-mcp-cpg` | `mcp.gsc-em.com` | Supply side — rails, GTINs, ACM-68000 signals |
| `io.github.gsc-em/aio-agents-mcp` | `mcp.gsc-cpg.com` | Demand side — banner attribution, strike targets |

Together they form the complete agentic CPG procurement surface: *what we sell* + *where it lands*.

---

## License

MIT — see [LICENSE](./LICENSE).

---

## Links

| Name | URL |
| --- | --- |
| GreenCore Solutions Corp. | [gsc-cpg.com](https://gsc-cpg.com) |
| Repository | [github.com/gsc-em/aio-agents-mcp](https://github.com/gsc-em/aio-agents-mcp) |
| MCP Registry | `io.github.gsc-em/aio-agents-mcp` |
| Companion MCP | [a2a-mcp-cpg](https://github.com/gsc-em/a2a-mcp-cpg) |

<!-- mcp-server-name: io.github.gsc-em/aio-agents-mcp -->
