"""
AIO Agents MCP — Demand-side procurement attribution server.

Operated by GreenCore Solutions Corp. (gsc-cpg.com).
Exposes the AIO procurement attribution dataset (2,235 retail grocery banners
across 28 EU + LatAm markets, attributed to ERP / procurement platform / cloud)
to AI agents via Model Context Protocol.

Brand           : gsc-cpg.com
MCP endpoint    : https://mcp.gsc-cpg.com
Registry ID     : io.github.gsc-em/aio-agents-mcp
Companion MCP   : io.github.gsc-em/a2a-mcp-cpg (supply-side catalog)

Transport: streamable-http (over Azure Container Apps).
"""
import os
from typing import Optional
import asyncpg
from fastmcp import FastMCP

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://aio_user:CHANGE_ME@pg-aio-agents-fr.postgres.database.azure.com:5432/aio_agents?sslmode=require",
)

mcp = FastMCP(
    name="aio-agents-mcp",
    instructions=(
        "Demand-side procurement attribution MCP for retail grocery, "
        "operated by GreenCore Solutions Corp. (gsc-cpg.com). "
        "Query the dataset of 2,235 retail grocery banners across 28 markets "
        "(EU 18 + LatAm 10), attributed to SAP / Oracle / D365 / Infor / Totvs ERPs, "
        "Ariba / Coupa / Ivalua / GEP / JAGGAER procurement platforms, and "
        "Azure / GCP / STACKIT / AWS / OCI clouds. Companion to "
        "io.github.gsc-em/a2a-mcp-cpg (supply-side catalog). Use this MCP to "
        "discover where a CPG product can land, which retailers run which "
        "procurement endpoint, and which markets are agentic-ready."
    ),
)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=4)
    return _pool


# ---------------------------------------------------------------------------
# Tool 1 — find banners by attribution criteria
# ---------------------------------------------------------------------------
@mcp.tool()
async def find_banners(
    country: Optional[str] = None,
    erp: Optional[str] = None,
    cloud: Optional[str] = None,
    procurement: Optional[str] = None,
    confidence: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """
    Find retail grocery banners matching procurement attribution criteria.

    Args:
        country: ISO country code ('DE', 'FR', 'BR', 'CL') or full name ('Germany').
        erp: ERP system fragment ('SAP', 'Oracle', 'D365', 'Totvs').
        cloud: Cloud platform ('Azure', 'GCP', 'STACKIT', 'AWS', 'OCI').
        procurement: Procurement platform ('Ariba', 'Coupa', 'Ivalua', 'GEP').
        confidence: Confidence tier ('CONFIRMED', 'PROBABLE', 'INFERRED', 'CONTESTED').
        limit: Max rows to return (default 50, max 500).

    Returns:
        Dict with 'count', 'limit', 'banners' (list of attributed banner records).
    """
    limit = min(max(limit, 1), 500)
    pool = await get_pool()
    where, params = [], []

    if country:
        if len(country) == 2:
            where.append(f"country_iso = ${len(params)+1}")
            params.append(country.upper())
        else:
            where.append(f"country_name ILIKE ${len(params)+1}")
            params.append(f"%{country}%")
    if erp:
        where.append(f"erp ILIKE ${len(params)+1}")
        params.append(f"%{erp}%")
    if cloud:
        where.append(f"cloud ILIKE ${len(params)+1}")
        params.append(f"%{cloud}%")
    if procurement:
        where.append(f"procurement ILIKE ${len(params)+1}")
        params.append(f"%{procurement}%")
    if confidence:
        where.append(f"confidence = ${len(params)+1}")
        params.append(confidence.upper())

    where_sql = " AND ".join(where) if where else "TRUE"
    sql = f"""
        SELECT banner, country_iso, country_name, region, erp, cloud, procurement, confidence
        FROM aio.banners
        WHERE {where_sql}
        ORDER BY
          CASE confidence
            WHEN 'CONFIRMED' THEN 1 WHEN 'PROBABLE' THEN 2
            WHEN 'INFERRED' THEN 3 WHEN 'CONTESTED' THEN 4
            ELSE 5 END,
          country_iso, banner
        LIMIT ${len(params)+1}
    """
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return {
        "count": len(rows),
        "limit": limit,
        "banners": [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Tool 2 — single market summary
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_market_summary(country: str) -> dict:
    """
    Get attribution summary for a single market.

    Args:
        country: ISO country code ('DE') or full name ('Germany').

    Returns:
        Market totals + top breakdowns by ERP, cloud, procurement.
    """
    pool = await get_pool()
    iso = country.upper() if len(country) == 2 else None
    name_pattern = None if iso else f"%{country}%"

    async with pool.acquire() as conn:
        if iso:
            market = await conn.fetchrow(
                "SELECT * FROM aio.markets WHERE country_iso = $1", iso
            )
        else:
            market = await conn.fetchrow(
                "SELECT * FROM aio.markets WHERE country_name ILIKE $1", name_pattern
            )
        if not market:
            return {"error": f"market not found: {country}"}

        country_iso = market["country_iso"]
        erp_breakdown = await conn.fetch(
            """SELECT erp, COUNT(*) AS n FROM aio.banners
               WHERE country_iso = $1 AND erp IS NOT NULL
               GROUP BY erp ORDER BY n DESC LIMIT 10""",
            country_iso,
        )
        cloud_breakdown = await conn.fetch(
            """SELECT cloud, COUNT(*) AS n FROM aio.banners
               WHERE country_iso = $1 AND cloud IS NOT NULL
               GROUP BY cloud ORDER BY n DESC LIMIT 10""",
            country_iso,
        )
        proc_breakdown = await conn.fetch(
            """SELECT procurement, COUNT(*) AS n FROM aio.banners
               WHERE country_iso = $1 AND procurement IS NOT NULL
               GROUP BY procurement ORDER BY n DESC LIMIT 10""",
            country_iso,
        )

    return {
        "market": dict(market),
        "erp_breakdown": [dict(r) for r in erp_breakdown],
        "cloud_breakdown": [dict(r) for r in cloud_breakdown],
        "procurement_breakdown": [dict(r) for r in proc_breakdown],
    }


# ---------------------------------------------------------------------------
# Tool 3 — strike targets (highest-confidence agentic-ready banners)
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_strike_targets(
    top_n: int = 30,
    region: Optional[str] = None,
) -> dict:
    """
    Return highest-confidence banners ready for agentic procurement targeting.

    Strike score weights confidence: CONFIRMED=100, PROBABLE=70, INFERRED=50,
    CONTESTED=30. Only banners with full ERP + cloud + procurement attribution
    are included.

    Args:
        top_n: Number of targets to return (default 30, max 200).
        region: Optional region filter ('Western EU + UK + IE', 'DACH', 'LatAm', etc.).

    Returns:
        Ranked list of strike targets with attribution + score.
    """
    top_n = min(max(top_n, 1), 200)
    pool = await get_pool()
    params = [top_n]
    where = ""
    if region:
        where = "WHERE region ILIKE $2"
        params.append(f"%{region}%")

    sql = f"""
        SELECT banner, country_iso, country_name, region, erp, cloud, procurement,
               confidence, strike_score
        FROM aio.v_strike_targets
        {where}
        ORDER BY strike_score DESC, country_iso, banner
        LIMIT $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return {
        "count": len(rows),
        "top_n": top_n,
        "region_filter": region,
        "targets": [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Tool 4 — agentic readiness by region
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_agentic_readiness(region: Optional[str] = None) -> dict:
    """
    Get agentic-readiness scorecard by region.

    Readiness = % of banners in the region with at least an inferred
    ERP/cloud/procurement attribution.

    Args:
        region: Optional region name to filter ('LatAm', 'DACH', 'Nordics', etc.).

    Returns:
        List of regions with attribution percentages.
    """
    pool = await get_pool()
    if region:
        sql = """SELECT * FROM aio.v_agentic_readiness
                 WHERE region ILIKE $1 ORDER BY attribution_pct DESC NULLS LAST"""
        params = [f"%{region}%"]
    else:
        sql = "SELECT * FROM aio.v_agentic_readiness ORDER BY attribution_pct DESC NULLS LAST"
        params = []

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return {
        "count": len(rows),
        "regions": [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Tool 5 — global attribution coverage
# ---------------------------------------------------------------------------
@mcp.tool()
async def count_attribution_coverage() -> dict:
    """
    Get global attribution coverage stats across the entire dataset.

    Returns:
        Total banners, breakdowns by confidence tier, distinct ERPs/clouds/
        procurement platforms, market count.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM aio.banners")
        by_conf = await conn.fetch(
            """SELECT confidence, COUNT(*) AS n FROM aio.banners
               GROUP BY confidence ORDER BY n DESC"""
        )
        with_erp = await conn.fetchval(
            "SELECT COUNT(*) FROM aio.banners WHERE erp IS NOT NULL"
        )
        with_cloud = await conn.fetchval(
            "SELECT COUNT(*) FROM aio.banners WHERE cloud IS NOT NULL"
        )
        with_proc = await conn.fetchval(
            "SELECT COUNT(*) FROM aio.banners WHERE procurement IS NOT NULL"
        )
        markets = await conn.fetchval(
            "SELECT COUNT(DISTINCT country_iso) FROM aio.banners"
        )
        distinct_erps = await conn.fetchval(
            "SELECT COUNT(DISTINCT erp) FROM aio.banners WHERE erp IS NOT NULL"
        )
        distinct_clouds = await conn.fetchval(
            "SELECT COUNT(DISTINCT cloud) FROM aio.banners WHERE cloud IS NOT NULL"
        )
        distinct_proc = await conn.fetchval(
            "SELECT COUNT(DISTINCT procurement) FROM aio.banners WHERE procurement IS NOT NULL"
        )

    return {
        "total_banners": total,
        "markets_covered": markets,
        "by_confidence": [dict(r) for r in by_conf],
        "banners_with_erp": with_erp,
        "banners_with_cloud": with_cloud,
        "banners_with_procurement": with_proc,
        "distinct_erp_systems": distinct_erps,
        "distinct_clouds": distinct_clouds,
        "distinct_procurement_platforms": distinct_proc,
        "operator": "GreenCore Solutions Corp.",
        "endpoint": "https://mcp.gsc-cpg.com",
        "registry_id": "io.github.gsc-em/aio-agents-mcp",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
