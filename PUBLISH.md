# PUBLISH.md — Deployment runbook

End-to-end deployment of `aio-agents-mcp` from empty repo to live MCP at `https://mcp.gsc-cpg.com`.

---

## Phase 1 — Register MCP Registry namespace (10 min)

Claims `io.github.gsc-em/aio-agents-mcp` immediately. Can be done before Azure deployment.

### 1.1 Push repo to GitHub

```bash
cd /path/to/aio-agents-mcp
git init
git add .
git commit -m "Initial scaffold: AIO Agents MCP v0.1.0"
git branch -M main
git remote add origin https://github.com/gsc-em/aio-agents-mcp.git
git push -u origin main
```

### 1.2 Install mcp-publisher

macOS / Linux:
```bash
curl -L https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr '[:upper:]' '[:lower:]')_$(uname -m).tar.gz | tar xz
sudo mv mcp-publisher /usr/local/bin/
```

Windows (PowerShell):
```powershell
$arch = if ([System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -eq "Arm64") { "arm64" } else { "amd64" }
Invoke-WebRequest -Uri "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_windows_$arch.tar.gz" -OutFile "mcp-publisher.tar.gz"
tar xf mcp-publisher.tar.gz
```

### 1.3 Authenticate with GitHub

```bash
mcp-publisher login github
```

Follow the device-code flow. Sign in as a member of the `gsc-em` GitHub org.

### 1.4 Publish

```bash
cd /path/to/aio-agents-mcp
mcp-publisher publish server.json
```

Confirms with `✓ Successfully published io.github.gsc-em/aio-agents-mcp version 0.1.0`.

Verify at: https://registry.modelcontextprotocol.io/v0/servers?search=aio-agents-mcp

---

## Phase 2 — Provision Azure infrastructure (30 min)

All resources land in the **AIO Agents** subscription (`gsc-em.com` tenant), region **France Central**.

### 2.1 Resource group

```bash
az login
az account set --subscription "AIO Agents"

az group create \
  --name rg-aio-agents-fr \
  --location francecentral \
  --tags operator="GreenCore Solutions Corp." mcp="io.github.gsc-em/aio-agents-mcp"
```

### 2.2 Postgres Flexible Server

```bash
az postgres flexible-server create \
  --resource-group rg-aio-agents-fr \
  --name pg-aio-agents-fr \
  --location francecentral \
  --tier Burstable \
  --sku-name Standard_B1ms \
  --storage-size 32 \
  --version 16 \
  --admin-user aio_admin \
  --admin-password '<STRONG-PASSWORD>' \
  --public-access 0.0.0.0
```

Then create the application user + database via Azure Cloud Shell (psql):

```sql
CREATE DATABASE aio_agents;
\c aio_agents
CREATE USER aio_user WITH PASSWORD '<APP-PASSWORD>';
GRANT CONNECT ON DATABASE aio_agents TO aio_user;
GRANT USAGE ON SCHEMA public TO aio_user;
```

### 2.3 Load schema + data

From your local machine, with psql installed:

```bash
PGHOST=pg-aio-agents-fr.postgres.database.azure.com \
PGUSER=aio_admin \
PGDATABASE=aio_agents \
PGPASSWORD='<ADMIN-PASSWORD>' \
PGSSLMODE=require \
psql -f sql/schema.sql

PGHOST=pg-aio-agents-fr.postgres.database.azure.com \
PGUSER=aio_admin \
PGDATABASE=aio_agents \
PGPASSWORD='<ADMIN-PASSWORD>' \
PGSSLMODE=require \
psql -f sql/load.sql

# Then grant select to app user
psql -c "GRANT SELECT ON ALL TABLES IN SCHEMA aio TO aio_user;"
psql -c "GRANT SELECT ON aio.v_strike_targets, aio.v_agentic_readiness TO aio_user;"
```

### 2.4 Container Registry (or use existing)

If using existing ACR `waypointregistry10060`:

```bash
az acr login --name waypointregistry10060
docker build -t waypointregistry10060.azurecr.io/aio-agents-mcp:0.1.0 .
docker push waypointregistry10060.azurecr.io/aio-agents-mcp:0.1.0
```

### 2.5 Container Apps environment

If `aio-agents-env-fr` doesn't already exist:

```bash
az containerapp env create \
  --resource-group rg-aio-agents-fr \
  --name aio-agents-env-fr \
  --location francecentral
```

### 2.6 Deploy Container App

```bash
az containerapp create \
  --resource-group rg-aio-agents-fr \
  --name ca-aio-agents-mcp \
  --environment aio-agents-env-fr \
  --image waypointregistry10060.azurecr.io/aio-agents-mcp:0.1.0 \
  --registry-server waypointregistry10060.azurecr.io \
  --target-port 8000 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 2 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --secrets database-url='postgresql://aio_user:<APP-PASSWORD>@pg-aio-agents-fr.postgres.database.azure.com:5432/aio_agents?sslmode=require' \
  --env-vars DATABASE_URL=secretref:database-url
```

### 2.7 Custom domain

```bash
# Get the Container App FQDN
az containerapp show --resource-group rg-aio-agents-fr --name ca-aio-agents-mcp --query properties.configuration.ingress.fqdn -o tsv
# e.g. ca-aio-agents-mcp.purpleflower-12345.francecentral.azurecontainerapps.io
```

In Cloudflare (`gsc-cpg.com` zone):
1. Add **CNAME** record: `mcp` → `<container-app-fqdn>` — DNS only (grey cloud)
2. Add **TXT** record (Azure validation, get value from `az containerapp hostname add --validation-method=cname-delegation`)

```bash
az containerapp hostname add \
  --resource-group rg-aio-agents-fr \
  --name ca-aio-agents-mcp \
  --hostname mcp.gsc-cpg.com

az containerapp hostname bind \
  --resource-group rg-aio-agents-fr \
  --name ca-aio-agents-mcp \
  --hostname mcp.gsc-cpg.com \
  --environment aio-agents-env-fr \
  --validation-method CNAME
```

Once validated, Cloudflare cloud can be flipped to orange (proxied) for DDoS / TLS edge.

---

## Phase 3 — Verify (5 min)

```bash
# Health check (FastMCP exposes /mcp endpoint)
curl -i https://mcp.gsc-cpg.com/mcp

# Test from Claude Desktop:
# Settings → Developer → Edit Config → add:
#   "aio-agents-mcp": {
#     "url": "https://mcp.gsc-cpg.com/mcp",
#     "transport": "streamable-http"
#   }

# Test from Cursor / VS Code MCP:
# Add server URL: https://mcp.gsc-cpg.com/mcp
```

---

## Phase 4 — Bump version + republish (when production-ready)

After tools are live and verified:

1. Edit `server.json` → `"version": "1.0.0"`
2. Commit + push
3. Tag: `git tag v1.0.0 && git push --tags`
4. Republish: `mcp-publisher publish server.json`

The registry now lists v1.0.0 as the canonical version.

---

## Cost estimate (monthly, idle traffic)

| Resource | Cost |
| --- | --- |
| Postgres Flexible Server (B1ms, 32GB) | ~$15 |
| Container App (scale-to-zero, ~10K req/mo) | ~$3–8 |
| ACR (shared with existing fleet) | $0 marginal |
| Cloudflare DNS | $0 |
| **Total** | **~$20–25 / mo** |

Scales linearly with traffic. Heavy production load (1M+ req/mo) puts it at ~$50–80/mo.
