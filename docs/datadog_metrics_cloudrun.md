# Datadog Custom Metrics – Cloud Run Reference (Authoritative)

This document defines the **authoritative rules** for emitting custom metrics
from CleanMyData running on **Google Cloud Run**.

It intentionally excludes agent installation, UI usage, and dashboards.

---

## 1. Metric Types (Datadog Semantics)

Use the following metric types only:

- **count**
  - Monotonic increment
  - Used for request totals and error totals
  - Example: requests_total, requests_failed_total

- **gauge**
  - Point-in-time value
  - Used for dataset stats
  - Example: rows_processed, duplicates_removed

- **histogram**
  - Distribution of values
  - Used for latency and duration
  - Example: duration_ms

Do NOT use rates directly. Rates are derived in Datadog.

---

## 2. Metric Naming Rules

- Lowercase
- Dot-separated
- No spaces
- Stable names (do not encode variable values in the name)

Prefix all metrics with:

cleanmydata.*

Examples:
- cleanmydata.rows_processed
- cleanmydata.duplicates_removed
- cleanmydata.duration_ms
- cleanmydata.requests_total

---

## 3. Tagging Rules (Critical)

Tags must be **low-cardinality**.

### Required tags
- service: cleanmydata
- env: dev | staging | prod
- runtime: cloudrun

### Optional tags (ONLY if naturally available)
- dataset_kind instead of dataset_name to keep tags low-cardinality
- outliers_method (cap | remove | none)
- excel_used (true | false)
- status (success | failure)

Do NOT:
- Tag with request IDs
- Tag with user IDs
- Tag with full file paths
- Tag with free-form text

---

## 4. Cloud Run Constraints

- Cloud Run is **serverless**
- A local Datadog Agent **may not be present**
- Metrics emission MUST NOT assume an agent exists

### Environment-based behavior
- If `DD_AGENT_HOST` (+ optional `DD_DOGSTATSD_PORT`) is set:
  → DogStatsD is allowed
- Else if `DD_API_KEY` + `DD_SITE` are set:
  → Use Datadog Metrics HTTP API
- Else:
  → Metrics emission must be **no-op and non-failing**

Metrics failures must NEVER crash requests.

---

## 5. Failure Handling Rules

- Metrics emission errors must be swallowed
- Errors may be logged at DEBUG level only
- Cleaning requests must succeed or fail independently of Datadog availability

---

## 6. Testing Rules

- Tests must NOT call real Datadog endpoints
- Metrics clients must be mockable / replaceable
- Tests should assert:
  - metric name
  - metric type
  - value
  - tags

---

## 7. Non-Goals (Explicitly Out of Scope)

- Dashboards
- Monitors
- Agent installation
- Infrastructure provisioning
- Log ingestion
