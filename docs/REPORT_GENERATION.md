# Report Generation & Numeric Integrity Architecture

**Revision:** 1.0  
**Enforcement Level:** Mandatory Institutional Standard  
**Operating Principle:** *Numbers Are Computed, Never Typed.*

---

## 1. Why Numbers Are Never Hand-Typed

During Phases 0.5 through 3.0 of the quantitative rehabilitation program, forensic audits uncovered multiple severe discrepancies directly caused by manual transcription and hardcoding:
1. **Regime Cohort Transposition:** $16.60$ R was shifted between Choppy and Trending in `config/cohorts.json` due to manual markdown transcription, falsely creating the appearance of regime cohort drift.
2. **Double-Deduction of Costs:** In Phase 0.6, the author manually subtracted cost fractions from ledger outcomes that were *already* net of costs, reporting $+0.1702$ R instead of $+0.2627$ R for Core 4h Longs.
3. **Ghost Parity & Cross-Market Fee Inflation:** In Phase 3, manual table entry left Ranging cohort delta at exactly $0.0000$ R by copy-pasting, while Core Shorts had $-0.4719$ R manually injected from an inappropriate crypto fee model on forex trades.

**Institutional Policy:**  
No metric, sample size, return, Sharpe ratio, p-value, or dollar value in any publication under `docs/reports/` may be authored by human keystroke. Every number must originate from an executable, deterministic query or backtest script with traceable data provenance.

---

## 2. Report Generation Architecture (`scripts/generate_report.py`)

The canonical report generator [`scripts/generate_report.py`](file:///c:/Users/Admin/Trading%20Bot%20app/scripts/generate_report.py) binds the raw database and parquet data directly to the markdown reporting layer.

```
+-------------------------------------------------------------+
|                  Underlying Data Layer                      |
|  - Supabase PostgreSQL (signals, outcomes, audit_logs)       |
|  - Immutable Parquet Caches (backend/data_cache/*_4h.parquet)|
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                  Named Query Registry                       |
|  - Q_P4_RECON_CORE_LONG     - Q_P4_DIR_A_SPEC               |
|  - Q_P4_COST_SANITY         - Q_P4_DIR_A_RESULTS            |
|  - Q_P4_BENCHMARKS          - Q_P4_MASTER_DECISION          |
|  - Q_P4_CARRY_RECON         - Q_P3_DIFF_AUDIT               |
|  - Q_P4_MOMENTUM_2D                                         |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                Automated Table Renderer                     |
|  - Evaluates query / computation engine                     |
|  - Extracts row count (N) and Git Commit Hash               |
|  - Injects mandatory provenance metadata caption            |
|  - Formats markdown tables with GitHub Flavored Markdown    |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                 Published Report Artifacts                  |
|  - docs/reports/phase_4.md                                  |
|  - backend/docs/reports/phase_4.md                          |
+-------------------------------------------------------------+
```

---

## 3. How to Add a New Table to a Report

To add or modify any table in a published quantitative report, follow these four mandatory steps:

### Step 1: Define a Named Query in `scripts/generate_report.py`
Register a dedicated data-fetching or computation function with a unique `Query ID` prefixed with `Q_`:

```python
def query_my_new_metric() -> dict[str, Any]:
    query_id = "Q_P4_MY_NEW_METRIC"
    # Execute SQL query or vectorized DataFrame backtest
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT cohort, count(*), avg(r_net) FROM outcomes GROUP BY cohort")
        rows = cur.fetchall()
    
    return {
        "query_id": query_id,
        "row_count": len(rows),
        "columns": ["Cohort", "Trades (n)", "Mean Net R"],
        "data": rows
    }
```

### Step 2: Render Table with Provenance Metadata
Every table must be rendered using the standardized table formatter that embeds the provenance header:

```python
def render_markdown_table(result: dict[str, Any], git_hash: str) -> str:
    md = []
    # Mandatory Provenance Header
    md.append(f"> **Query ID:** `{result['query_id']}` | **Row Count:** `{result['row_count']}` | **Git Hash:** `{git_hash}`\n")
    # Table Header & Body
    md.append("| " + " | ".join(result["columns"]) + " |")
    md.append("| " + " | ".join([":---"] * len(result["columns"])) + " |")
    for row in result["data"]:
        md.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(md)
```

### Step 3: Run the Report Generator
Execute the generator from the repository root:
```bash
python scripts/generate_report.py --phase 4
```

### Step 4: Verify via Automated CI Check
Run the CI table integrity test:
```bash
pytest backend/scripts/test_report_tables.py
```
The test scans all markdown files in `docs/reports/` and fails the build if:
1. Any markdown table contains numeric data without an associated `Query ID`.
2. Any `Query ID` is unregistered or orphaned.
3. The table row count does not match the query output.

---

## 4. Verification CI Test (`test_report_tables.py`)

The automated regression test enforces numeric integrity:
- **Rule 1:** No numeric markdown table without a preceding `> **Query ID:**` block.
- **Rule 2:** Every git commit hash embedded in the table matches `git rev-parse HEAD`.
- **Rule 3:** The generator must reproduce all published tables identically ($\Delta = 0$).
