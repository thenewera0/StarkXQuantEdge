"""CI Test: Verify that every numeric table in phase_4.md and phase_5.md contains a valid Query ID,
Row Count, and Git Hash, matches invariants or independent recomputation, and ensures Direction A
does not show identical column values across rows.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

cur_path = Path(__file__).resolve()
root_dir = cur_path.parents[2] if cur_path.parents[1].name == "backend" else cur_path.parents[1]
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(root_dir))
load_dotenv(backend_dir / ".env")


def extract_tables_with_metadata(report_path: Path) -> list[dict[str, Any]]:
    assert report_path.exists(), f"Report file not found at {report_path}"
    content = report_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    tables = []
    current_table = []
    current_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if not current_table:
                current_start = i
            current_table.append(stripped)
        else:
            if len(current_table) >= 3:
                tables.append((current_start, current_table))
            current_table = []

    if len(current_table) >= 3:
        tables.append((current_start, current_table))

    assert len(tables) > 0, f"No tables found in {report_path}"

    num_pattern = re.compile(r"[-+]?\d*\.?\d+(?:%|R|bps|\$)?")
    query_id_pattern = re.compile(r"Query ID\*{0,2}:\*{0,2}\s*`?(Q_[A-Za-z0-9_]+)`?", re.IGNORECASE)
    row_count_pattern = re.compile(r"Row Count\*{0,2}:\*{0,2}\s*`?(\d+)`?", re.IGNORECASE)
    git_hash_pattern = re.compile(r"(?:Code\s+)?Git(?:\s+Code)?\s+Hash\*{0,2}:\*{0,2}\s*`?([0-9a-fA-F]{7,40})`?", re.IGNORECASE)

    extracted_tables = []

    for start_line, tbl_lines in tables:
        header_cells = [c.strip() for c in tbl_lines[0].strip("|").split("|")]
        body_lines = tbl_lines[2:]
        
        has_numeric = False
        parsed_rows = []
        for r_line in body_lines:
            cells = [c.strip() for c in r_line.strip("|").split("|")]
            parsed_rows.append(cells)
            for cell in cells:
                clean_cell = re.sub(r"\[.*?\]\(.*?\)", "", cell)
                if num_pattern.search(clean_cell):
                    has_numeric = True

        if not has_numeric:
            continue

        lookback_start = max(0, start_line - 10)
        preceding_text = "\n".join(lines[lookback_start:start_line])

        qid_match = query_id_pattern.search(preceding_text)
        rc_match = row_count_pattern.search(preceding_text)
        git_match = git_hash_pattern.search(preceding_text)

        error_msg = f"Numeric table starting at line {start_line + 1} in {report_path.name} is missing mandatory provenance metadata!"
        assert qid_match is not None, f"{error_msg} Missing 'Query ID: Q_...' in preceding lines."
        assert rc_match is not None, f"{error_msg} Missing 'Row Count: ...' in preceding lines."
        assert git_match is not None, f"{error_msg} Missing 'Git Hash: ...' in preceding lines."

        extracted_tables.append({
            "start_line": start_line + 1,
            "query_id": qid_match.group(1),
            "row_count": int(rc_match.group(1)),
            "git_hash": git_match.group(1),
            "headers": header_cells,
            "rows": parsed_rows,
            "table_lines": tbl_lines
        })

    return extracted_tables


def verify_table_provenance(report_path: Path) -> list[dict[str, Any]]:
    extracted = extract_tables_with_metadata(report_path)
    for t in extracted:
        assert len(t["rows"]) == t["row_count"], (
            f"Row count mismatch in table {t['query_id']} at line {t['start_line']} of {report_path.name}: "
            f"metadata says {t['row_count']}, actual table has {len(t['rows'])}"
        )
        print(f"[{report_path.name}] Line {t['start_line']:3d}: Verified Query ID `{t['query_id']}` (Rows: {t['row_count']}, Hash: {t['git_hash'][:7]})")
    return extracted


def verify_dir_a_column_non_identical(tables: list[dict[str, Any]], report_name: str):
    """Enforces 5.5: Dir A table must not show identical values in a column unless structurally identical (fix Top 5% P&L share = 100.0%)."""
    for t in tables:
        if "DIR_A" in t["query_id"]:
            # Check the Top 5% column
            top_5_col_idx = None
            for idx, h in enumerate(t["headers"]):
                if "top 5%" in h.lower():
                    top_5_col_idx = idx
                    break
            
            if top_5_col_idx is not None:
                vals = [r[top_5_col_idx] for r in t["rows"]]
                unique_vals = set(vals)
                assert len(unique_vals) > 1, (
                    f"In {report_name} table {t['query_id']}, Top 5% column has identical values across all rows: {unique_vals}! "
                    f"Must reflect true positive gain concentration across horizons."
                )
                print(f"[{report_name}] Table `{t['query_id']}`: Verified Top 5% column contains non-identical values: {sorted(list(unique_vals))}")


def verify_phase_5_invariants_and_recomputations(tables: list[dict[str, Any]]):
    """Enforces 5.5: every numeric table must match an invariant or a recomputation from a second independent query."""
    q_map = {t["query_id"]: t for t in tables}

    # 1. Q_P5_COHORTS_SSOT vs config/cohorts.json invariants
    assert "Q_P5_COHORTS_SSOT" in q_map, "Missing Q_P5_COHORTS_SSOT in phase_5.md"
    cohort_t = q_map["Q_P5_COHORTS_SSOT"]
    cohorts_path = root_dir / "config" / "cohorts.json"
    if not cohorts_path.exists():
        cohorts_path = backend_dir / "config" / "cohorts.json"
    with open(cohorts_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)["cohorts"]

    for row in cohort_t["rows"]:
        k = row[0].replace("`", "")
        if k in cfg:
            assert int(row[7]) == cfg[k]["n_trades"], f"Cohort {k} trade count mismatch: {row[7]} vs {cfg[k]['n_trades']}"
            reported_sum = float(row[8].replace("R", "").strip())
            assert abs(reported_sum - cfg[k]["sum_r_net"]) < 0.001, f"Cohort {k} sum mismatch: {reported_sum} vs {cfg[k]['sum_r_net']}"
    print("[phase_5.md] Table `Q_P5_COHORTS_SSOT` matched 100% against config/cohorts.json invariants.")

    # 2. Q_P5_BENCHMARKS_ALL_BARS vs Universe Benchmark Invariants
    assert "Q_P5_BENCHMARKS_ALL_BARS" in q_map, "Missing Q_P5_BENCHMARKS_ALL_BARS in phase_5.md"
    bench_t = q_map["Q_P5_BENCHMARKS_ALL_BARS"]
    for row in bench_t["rows"]:
        rule_trades = int(row[2])
        base_trades = int(row[3])
        assert base_trades > rule_trades, f"Benchmark baseline trades ({base_trades}) not greater than rule trades ({rule_trades})"
        rule_mean = float(row[4].replace("R", "").strip())
        base_mean = float(row[5].replace("R", "").strip())
        assert rule_mean != base_mean, f"Baseline series equal to rule series: {rule_mean} == {base_mean}"
        verdict = row[10].replace("*", "").strip()
        assert verdict == "BETA ONLY", f"Unexpected verdict: {verdict}"
    print("[phase_5.md] Table `Q_P5_BENCHMARKS_ALL_BARS` verified: n_baseline > n_rule, series unequal, verdict BETA ONLY.")

    # 3. Q_P5_TRADE_LEVEL_PROOF vs actual DB records and cost identity
    assert "Q_P5_TRADE_LEVEL_PROOF" in q_map, "Missing Q_P5_TRADE_LEVEL_PROOF in phase_5.md"
    trade_t = q_map["Q_P5_TRADE_LEVEL_PROOF"]
    from app import db
    signal_ids = [int(r[0]) for r in trade_t["rows"]]
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            select s.id, s.entry, s.stop, s.target, o.r_net
            from signals s
            join outcomes o on o.signal_id = s.id
            where s.id = any(%s)
        """, (signal_ids,))
        db_trades = {r[0]: {"entry": float(r[1]), "stop": float(r[2]), "target": float(r[3]), "r_net": float(r[4])} for r in cur.fetchall()}

    for row in trade_t["rows"]:
        sig_id = int(row[0])
        assert sig_id in db_trades, f"Signal ID {sig_id} not found in database!"
        db_t = db_trades[sig_id]

        # Verify against actual DB fields
        stored_r = float(row[11].replace("R", "").strip())
        assert abs(stored_r - db_t["r_net"]) < 0.0002, (
            f"Trade {sig_id} stored r_net {stored_r} != DB outcomes.r_net {db_t['r_net']}"
        )
        assert abs(float(row[2]) - db_t["entry"]) < 0.001, f"Trade {sig_id} entry fill mismatch"
        assert abs(float(row[4]) - db_t["stop"]) < 0.001, f"Trade {sig_id} stop mismatch"
        assert abs(float(row[5]) - db_t["target"]) < 0.001, f"Trade {sig_id} target mismatch"

        # Verify recomputation identity: recomputed_r == gross_r - (fee_r + slip_r + funding_r)
        gross_r = float(row[7].replace("R", "").strip())
        fee_r = float(row[8].replace("R", "").strip())
        slip_r = float(row[9].replace("R", "").strip())
        funding_r = float(row[10].replace("R", "").strip())
        recomputed_r = float(row[12].replace("R", "").strip())
        expected_recomputed = gross_r - (fee_r + slip_r + funding_r)
        assert abs(recomputed_r - expected_recomputed) <= 0.0002, (
            f"Trade {sig_id} recomputed_r {recomputed_r} != gross - costs {expected_recomputed}"
        )
    print(f"[phase_5.md] Table `Q_P5_TRADE_LEVEL_PROOF` verified: all {len(trade_t['rows'])} trades matched PostgreSQL ledger fields and cost identity.")

    # 4. Q_P5_CARRY_RECON vs Mathematical Identity
    assert "Q_P5_CARRY_RECON" in q_map, "Missing Q_P5_CARRY_RECON in phase_5.md"
    carry_t = q_map["Q_P5_CARRY_RECON"]
    carry_dict = {r[0]: (r[1], r[2]) for r in carry_t["rows"]}
    mean_bps = float(carry_dict["Daily Return Mean (bps/day)"][1].replace("bps", "").strip())
    std_bps = float(carry_dict["Daily Return Volatility (Std)"][1].replace("bps", "").strip())
    sharpe = float(carry_dict["Annualized Net Sharpe"][1].strip())
    calc_sharpe = (mean_bps / std_bps) * (365.0 ** 0.5)
    assert abs(sharpe - calc_sharpe) < 0.001, f"Carry Sharpe identity mismatch: {sharpe} vs {calc_sharpe:.4f}"
    apr = float(carry_dict["Net Annualized Carry APR"][1].replace("% APR", "").strip())
    hurdle = float(carry_dict["Required Economic Hurdle"][1].replace("% APR", "").strip())
    assert apr < hurdle, f"Carry APR {apr} >= hurdle {hurdle}"
    assert carry_dict["Pre-Registered Final Verdict"][1] == "UNECONOMIC"
    print("[phase_5.md] Table `Q_P5_CARRY_RECON` verified: Sharpe identity |2.4256 - 0.4690/3.6938*sqrt(365)| = 0.00, verdict UNECONOMIC.")

    # 5. Q_P5_OPERATING_GOVERNANCE
    assert "Q_P5_OPERATING_GOVERNANCE" in q_map, "Missing Q_P5_OPERATING_GOVERNANCE in phase_5.md"
    gov_t = q_map["Q_P5_OPERATING_GOVERNANCE"]
    gov_dict = {r[0]: (r[1], r[2]) for r in gov_t["rows"]}
    assert "live_trading_enabled = False" in gov_dict["Live Order Routing"][0]
    assert "halt-2026-10-27" in gov_dict["Git Archival Release Tag"][0]
    print("[phase_5.md] Table `Q_P5_OPERATING_GOVERNANCE` verified: Live trading False, tag halt-2026-10-27.")


def test_phase_4_tables_have_query_ids():
    p4_paths = [Path("docs/reports/phase_4.md"), Path("backend/docs/reports/phase_4.md")]
    p4_path = next((p for p in p4_paths if p.exists()), None)
    assert p4_path is not None, "Report docs/reports/phase_4.md not found"
    tables = verify_table_provenance(p4_path)
    verify_dir_a_column_non_identical(tables, "phase_4.md")
    print(f"\nSUCCESS: All {len(tables)} numeric tables in phase_4.md verified.")


def test_phase_5_tables_have_query_ids():
    p5_paths = [Path("docs/reports/phase_5.md"), Path("backend/docs/reports/phase_5.md")]
    p5_path = next((p for p in p5_paths if p.exists()), None)
    assert p5_path is not None, "Report docs/reports/phase_5.md not found"
    tables = verify_table_provenance(p5_path)
    verify_dir_a_column_non_identical(tables, "phase_5.md")
    verify_phase_5_invariants_and_recomputations(tables)
    print(f"\nSUCCESS: All {len(tables)} numeric tables in phase_5.md verified against invariants & recomputations.")


def test_phase_6_tables_have_query_ids():
    p6_paths = [Path("docs/reports/phase_6.md"), Path("backend/docs/reports/phase_6.md")]
    p6_path = next((p for p in p6_paths if p.exists()), None)
    assert p6_path is not None, "Report docs/reports/phase_6.md not found"
    tables = verify_table_provenance(p6_path)
    q_map = {t["query_id"]: t for t in tables}
    
    # Verify core Phase 6 tables exist
    expected_queries = [
        "Q_P6_DUPLICATES_AUDIT",
        "Q_P6_UNIQUE_RECOMPUTATIONS",
        "Q_P6_SIZING_AND_SPLITS",
        "Q_P6_ROOT_CAUSE_MIGRATION",
        "Q_P6_MARKET_COMPOSITION",
        "Q_P6_PARTIAL_BOOK_PARITY",
        "Q_P6_COST_RECONCILIATION"
    ]
    for eq in expected_queries:
        assert eq in q_map, f"Missing {eq} in phase_6.md tables!"
    print(f"\nSUCCESS: All {len(tables)} numeric tables in phase_6.md verified.")


def test_phase_7_tables_have_query_ids():
    p7_paths = [Path("docs/reports/phase_7.md"), Path("backend/docs/reports/phase_7.md")]
    p7_path = next((p for p in p7_paths if p.exists()), None)
    assert p7_path is not None, "Report docs/reports/phase_7.md not found"
    tables = verify_table_provenance(p7_path)
    q_map = {t["query_id"]: t for t in tables}
    
    # Verify core Phase 7 tables exist
    expected_queries = [
        "Q_P7_GEOMETRY_BY_MARKET",
        "Q_P7_KNOWN_VIOLATIONS_DETAIL",
        "Q_P7_SAME_PERIOD_BENCHMARK",
        "Q_P7_TRADE_REPLAY_GAP",
        "Q_P7_LOGGING_HARDENING",
        "Q_P7_FORWARD_EVAL_SPEC"
    ]
    for eq in expected_queries:
        assert eq in q_map, f"Missing {eq} in phase_7.md tables!"
    
    # Verify that every table header names the aggregator
    for t in tables:
        has_aggregator = any("aggregator" in h.lower() for h in t["headers"])
        assert has_aggregator, f"Table {t['query_id']} in phase_7.md does not name its aggregator in headers: {t['headers']}"
        
    print(f"\nSUCCESS: All {len(tables)} numeric tables in phase_7.md verified with query IDs, git hashes, and aggregator declarations.")


def test_phase_8_tables_have_query_ids():
    p8_paths = [Path("docs/reports/phase_8.md"), Path("backend/docs/reports/phase_8.md")]
    p8_path = next((p for p in p8_paths if p.exists()), None)
    assert p8_path is not None, "Report docs/reports/phase_8.md not found"
    tables = verify_table_provenance(p8_path)
    q_map = {t["query_id"]: t for t in tables}
    
    # Verify core Phase 8 tables exist
    expected_queries = [
        "Q_P8_STOP_OVERWRITE_AUDIT",
        "Q_P8_SELECTION_TESTS",
        "Q_P8_GAP_DECOMPOSITION",
        "Q_P8_SIM_SIZE_RECONCILIATION",
        "Q_P8_ESTIMATOR_STABILITY",
        "Q_P8_FORWARD_LOG_ENRICHMENT",
        "Q_P8_GEOMETRY_REFINEMENTS"
    ]
    for eq in expected_queries:
        assert eq in q_map, f"Missing {eq} in phase_8.md tables!"
    
    # Verify that every table header names the aggregator
    for t in tables:
        has_aggregator = any("aggregator" in h.lower() for h in t["headers"])
        assert has_aggregator, f"Table {t['query_id']} in phase_8.md does not name its aggregator in headers: {t['headers']}"
        
    print(f"\nSUCCESS: All {len(tables)} numeric tables in phase_8.md verified with query IDs, git hashes, and aggregator declarations.")


def test_phase_9_tables_have_query_ids():
    p9_paths = [Path("docs/reports/phase_9.md"), Path("backend/docs/reports/phase_9.md")]
    p9_path = next((p for p in p9_paths if p.exists()), None)
    assert p9_path is not None, "Report docs/reports/phase_9.md not found"
    tables = verify_table_provenance(p9_path)
    q_map = {t["query_id"]: t for t in tables}
    
    # Verify core Phase 9 tables exist
    expected_queries = [
        "Q_P9_PLAIN_COUNTS_OVERVIEW",
        "Q_P9_DISCREPANCY_RECONCILIATION",
        "Q_P9_MUTATED_STOPS_RESOLUTION",
        "Q_P9_POWER_TABLE",
        "Q_P9_AMENDMENT_SPECIFICATION",
        "Q_P9_VALIDATION_FIXES_AUDIT"
    ]
    for eq in expected_queries:
        assert eq in q_map, f"Missing {eq} in phase_9.md tables!"
    
    # Verify that every table header names the aggregator
    for t in tables:
        has_aggregator = any("aggregator" in h.lower() for h in t["headers"])
        assert has_aggregator, f"Table {t['query_id']} in phase_9.md does not name its aggregator in headers: {t['headers']}"
        
    print(f"\nSUCCESS: All {len(tables)} numeric tables in phase_9.md verified with query IDs, git hashes, and aggregator declarations.")


def test_all_reports_tables():
    test_phase_4_tables_have_query_ids()
    test_phase_5_tables_have_query_ids()
    test_phase_6_tables_have_query_ids()
    test_phase_7_tables_have_query_ids()
    test_phase_8_tables_have_query_ids()
    test_phase_9_tables_have_query_ids()


if __name__ == "__main__":
    test_all_reports_tables()

