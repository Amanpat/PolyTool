# RIS_06 — Infrastructure
**System:** PolyTool Research Intelligence System  
**Covers:** Scheduling, CLI commands, n8n workflows, Grafana panels, monitoring, health checks

---

## Purpose

The infrastructure layer handles scheduling (when pipelines run), monitoring (are they
working), alerting (when something breaks), and the CLI interface (how humans interact
with the system). After Phase R4, the RIS should run autonomously with ~30 minutes/week
of operator attention.

---

## Scheduling

### v1: APScheduler

For the first 2-3 weeks of development, use APScheduler (already in the Python stack).
Simple, no external dependencies, easy to debug.

```python
# packages/research/scheduling/scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

def start_research_scheduler():
    """Start the RIS background scheduler."""
    scheduler = BackgroundScheduler()
    
    # Academic pipeline — every 12 hours
    scheduler.add_job(
        run_academic_ingestion,
        CronTrigger(hour="6,18"),
        id="academic_ingest",
        name="ArXiv + SSRN ingestion",
    )
    
    # Reddit r/polymarket — every 6 hours
    scheduler.add_job(
        run_reddit_polymarket,
        CronTrigger(hour="0,6,12,18"),
        id="reddit_polymarket",
        name="r/polymarket ingestion",
    )
    
    # Reddit other subreddits — daily at 03:00
    scheduler.add_job(
        run_reddit_others,
        CronTrigger(hour=3),
        id="reddit_others",
        name="Other subreddits ingestion",
    )
    
    # Twitter/X — every 6 hours
    scheduler.add_job(
        run_twitter_ingestion,
        CronTrigger(hour="1,7,13,19"),
        id="twitter_ingest",
        name="Twitter/X ingestion",
    )
    
    # Blog/RSS — every 4 hours
    scheduler.add_job(
        run_blog_ingestion,
        CronTrigger(hour="2,6,10,14,18,22"),
        id="blog_ingest",
        name="Blog/RSS ingestion",
    )
    
    # YouTube — weekly on Monday at 04:00
    scheduler.add_job(
        run_youtube_ingestion,
        CronTrigger(day_of_week="mon", hour=4),
        id="youtube_ingest",
        name="YouTube transcript ingestion",
    )
    
    # GitHub — weekly on Wednesday at 04:00
    scheduler.add_job(
        run_github_ingestion,
        CronTrigger(day_of_week="wed", hour=4),
        id="github_ingest",
        name="GitHub README ingestion",
    )
    
    # Freshness tier refresh — weekly on Sunday at 02:00
    scheduler.add_job(
        refresh_freshness_tiers,
        CronTrigger(day_of_week="sun", hour=2),
        id="freshness_refresh",
        name="Freshness tier recalculation",
    )
    
    # Weekly digest — Sunday at 08:00
    scheduler.add_job(
        generate_weekly_digest,
        CronTrigger(day_of_week="sun", hour=8),
        id="weekly_digest",
        name="Weekly research digest",
    )
    
    # Rejection audit — weekly on Saturday at 03:00
    scheduler.add_job(
        run_rejection_audit,
        CronTrigger(day_of_week="sat", hour=3),
        id="rejection_audit",
        name="Weekly rejection audit",
    )
    
    scheduler.start()
    return scheduler
```

### v2: n8n Migration

Once pipeline shapes are stable (~2-3 weeks after v1 launch), migrate to n8n for visual
workflow management, cloud LLM API routing, and monitoring.

**n8n setup:** `docker compose` — add n8n to the existing Docker stack:

```yaml
# docker-compose.yml (add to existing services)
n8n:
  image: n8nio/n8n:latest
  ports:
    - "5678:5678"
  environment:
    - N8N_BASIC_AUTH_ACTIVE=true
    - N8N_BASIC_AUTH_USER=admin
    - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
  volumes:
    - n8n_data:/home/node/.n8n
```

**n8n workflow definitions:**

| Workflow | Trigger | Steps |
|----------|---------|-------|
| Academic Ingest | Cron every 12h | HTTP → ArXiv API → Python exec (evaluate) → Chroma write |
| Reddit Ingest | Cron every 6h | HTTP → Reddit API → Python exec (normalize + evaluate) → Chroma write |
| Twitter Ingest | Cron every 6h | HTTP → Twitter scraper → Python exec → Chroma write |
| Blog/RSS Ingest | Cron every 4h | RSS Read → Python exec (extract + evaluate) → Chroma write |
| YouTube Ingest | Cron weekly | HTTP → yt-dlp exec → Python exec (clean + evaluate) → Chroma write |
| GitHub Ingest | Cron weekly | HTTP → GitHub API → Python exec → Chroma write |
| Weekly Digest | Cron Sunday 08:00 | Python exec (query + synthesize) → Save report → Discord webhook |
| Rejection Audit | Cron Saturday 03:00 | Python exec (sample + re-evaluate) → Discord if issues |
| Health Check | Cron every 30 min | Check pipeline status → Discord red alert if down |
| Manual URL | Webhook | Receive URL → Python exec (fetch + evaluate) → Chroma write |

**n8n advantage for cloud models:** n8n has built-in HTTP Request nodes with retry logic,
header management, and error handling. Routing to Gemini Flash vs DeepSeek V3 vs Ollama
becomes a visual decision tree instead of Python if/else chains.

---

## CLI Command Reference

### Ingestion Commands

```bash
# Run all ingestion pipelines
polytool research ingest-all

# Academic
polytool research ingest-academic [--topic TOPIC] [--max-papers N] [--days N]
polytool research ingest-arxiv ARXIV_ID          # specific paper by ID
polytool research ingest-book FILE [--title T] [--author A]
polytool research ingest-url URL                  # manual URL submission

# Social
polytool research ingest-social                   # all social sources
polytool research ingest-reddit [--subreddits S] [--days N]
polytool research ingest-twitter [--days N]
polytool research ingest-youtube [--query Q] [--max-videos N]
polytool research ingest-blogs                    # RSS feeds
polytool research ingest-github [--query Q] [--max-repos N]
```

### Query and Synthesis Commands

```bash
# Direct knowledge base query
polytool research query QUESTION [--partition P] [--freshness F] [--after DATE]

# Research brief generation
polytool research report --topic TOPIC [--output FILE]

# Pre-development check (most important command)
polytool research precheck --idea "description of what you want to build"

# Weekly digest (usually auto-generated, can be run manually)
polytool research digest [--days N]
```

### Catalog and Review Commands

```bash
# List ingested documents
polytool research catalog [--source-type TYPE] [--min-score N] [--freshness F]

# Show ingestion statistics
polytool research stats [--days N]

# Review borderline documents for calibration
polytool research review-borderline [--score-range MIN-MAX]

# Review rejected documents
polytool research review-rejected [--days N]

# Promote a wrongly rejected document
polytool research promote-rejected --doc-id DOC_ID

# Export rejected log
polytool research export-rejected [--days N] [--output FILE]
```

### Maintenance Commands

```bash
# Update evaluation prompt with calibration example
polytool research update-eval-prompt --add-example accept DOC_ID
polytool research update-eval-prompt --add-example reject DOC_ID

# Refresh freshness tiers (usually scheduled, can run manually)
polytool research refresh-freshness

# Seed foundational documents (Phase R0 — run once)
polytool research seed-foundations

# Re-embed all documents (after embedding model change)
polytool research reembed [--batch-size N]

# Show scheduler status
polytool research scheduler-status
```

---

## Grafana Dashboard

### Panel: research_intelligence

Add to existing Grafana instance (already reads from ClickHouse). Create a new dashboard
called "Research Intelligence" with these panels:

| Panel | Type | Data Source | Description |
|-------|------|------------|-------------|
| Documents ingested (24h/7d/30d) | Bar chart | ClickHouse | Count by source_type, grouped by time |
| Accept/reject ratio | Pie chart | ClickHouse | Should be 50-70% accept |
| Score distribution | Histogram | ClickHouse | Distribution of eval_score across all documents |
| Source distribution | Treemap | ClickHouse | Documents by source_type |
| Recent high-scoring docs | Table | ClickHouse | Top 10 documents this week by eval_score |
| Knowledge base size | Stat | ClickHouse | Total documents by partition |
| Eval model usage | Bar chart | ClickHouse | Gemini vs DeepSeek vs Ollama calls |
| Pipeline status | Status | ClickHouse | Last run time per pipeline, green/red |
| Rejection audit results | Table | ClickHouse | Last audit: how many rejections DeepSeek disagreed with |

**ClickHouse table for ingestion tracking:**

```sql
CREATE TABLE research_ingestion_log (
    event_time    DateTime DEFAULT now(),
    doc_id        String,
    source_type   String,
    title         String,
    eval_score    Int32,
    gate_decision Enum('ACCEPT', 'REVIEW', 'REJECT', 'DUPLICATE'),
    eval_model    String,
    eval_latency_ms Int32,
    pipeline_run_id String
) ENGINE = MergeTree()
ORDER BY event_time;
```

---

## Health Checks and Alerts

| Check | Frequency | Alert Level | Action |
|-------|-----------|-------------|--------|
| Pipeline failed (any) | Per run | RED (Discord) | Check API keys, rate limits, network |
| Accept rate <30% for 48h | Daily | YELLOW (Discord) | Review eval prompt calibration |
| Accept rate >90% for 48h | Daily | YELLOW (Discord) | Threshold may be too low |
| No new documents in 48h | Every 12h | YELLOW (Discord) | Check all source connectivity |
| Gemini API unavailable | Per eval | YELLOW (log) | Auto-fallback to DeepSeek/Ollama |
| DeepSeek API unavailable | Per eval | YELLOW (log) | Auto-fallback to Ollama |
| All LLM APIs down | Per eval | RED (Discord) | Queue documents, alert operator |
| Chroma write failure | Per write | RED (Discord) | Check disk space, Chroma health |
| Rejection audit >30% disagreement | Weekly | YELLOW (Discord) | Evaluator drift — recalibrate |

**Discord webhook integration:**

```python
import requests

def send_discord_alert(webhook_url: str, level: str, message: str):
    """Send a research pipeline alert to Discord."""
    colors = {"RED": 0xFF0000, "YELLOW": 0xFFAA00, "GREEN": 0x00FF00}
    payload = {
        "embeds": [{
            "title": f"RIS Alert: {level}",
            "description": message,
            "color": colors.get(level, 0x808080),
        }]
    }
    requests.post(webhook_url, json=payload)
```

---

## Automation Philosophy

The goal after Phase R4: the RIS runs without daily attention. The operator's weekly
commitment is:

1. **Read the weekly digest** (5 minutes) — what was ingested, notable findings
2. **Review YELLOW zone queue** (10 minutes) — accept/reject borderline documents
3. **Check Grafana dashboard** (5 minutes) — pipeline health, accept rates
4. **Update eval prompt if needed** (10 minutes) — add calibration examples

Total: ~30 minutes per week. Everything else runs on cron/n8n automatically.

---

*End of RIS_06 — Infrastructure*
