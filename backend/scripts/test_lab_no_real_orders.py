"""test_lab_no_real_orders.py

Section 0.1 & 9 Invariant:
0.1 PAPER ONLY. The lab never places a real order. It uses public market data only
and no exchange API keys. LAB_EXECUTION_MODE is the constant 'paper'.
test_lab_no_real_orders fails if lab code imports any private exchange client,
reads any *_API_KEY/*_SECRET env var, or can reach an order endpoint.
LIVE_TRADING_ENABLED and V2_LIVE_ENABLED stay false; the agent never edits them.
"""

import ast
import os
import sys
from pathlib import Path

# Add backend root to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.lab import LAB_EXECUTION_MODE
from app.config import settings
from app.v2.config import settings_v2


def scan_ast_for_violations(lab_dir: Path):
    forbidden_env_patterns = ["API_KEY", "SECRET", "PRIVATE_KEY", "BINANCE_API_KEY", "BINANCE_SECRET"]
    forbidden_imports = [
        "ccxt",
        "binance.client",
        "binance.spot",
        "binance.streams",
        "pybit",
        "bybit",
        "hyperliquid.exchange",
        "dydx3",
    ]
    forbidden_order_calls = [
        "create_order",
        "place_order",
        "post_order",
        "cancel_order",
        "new_order",
    ]

    violations = []

    for py_file in lab_dir.rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content, filename=str(py_file))
        except Exception as e:
            violations.append(f"Failed to parse {py_file}: {e}")
            continue

        # 1. Check string literals for env var reads like os.getenv("*_API_KEY")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check os.getenv, os.environ.get
                is_env = False
                if isinstance(node.func, ast.Attribute) and node.func.attr in ("getenv", "get"):
                    is_env = True
                if is_env and node.args and isinstance(node.args[0], ast.Constant):
                    val = str(node.args[0].value).upper()
                    for pat in forbidden_env_patterns:
                        if pat in val:
                            violations.append(f"Forbidden env read '{val}' in {py_file.name}:{node.lineno}")

                # Check forbidden method calls
                if isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_order_calls:
                    violations.append(f"Forbidden order call '{node.func.attr}' in {py_file.name}:{node.lineno}")

            # 2. Check imports
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for fi in forbidden_imports:
                        if alias.name.startswith(fi):
                            violations.append(f"Forbidden import '{alias.name}' in {py_file.name}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for fi in forbidden_imports:
                        if node.module.startswith(fi):
                            violations.append(f"Forbidden import from '{node.module}' in {py_file.name}:{node.lineno}")

    return violations


def main():
    print("================================================================================")
    print("GUARD 0.1 & 9: test_lab_no_real_orders (Zero Real Orders & Pure Paper Sandbox)")
    print("================================================================================")

    # 1. LAB_EXECUTION_MODE must be constant 'paper'
    assert LAB_EXECUTION_MODE == "paper", f"LAB_EXECUTION_MODE must be 'paper', got '{LAB_EXECUTION_MODE}'"
    print(f"[PASS] LAB_EXECUTION_MODE == 'paper'")

    # 2. LIVE_TRADING_ENABLED and V2_LIVE_ENABLED must stay False
    assert settings.live_trading_enabled is False, "settings.live_trading_enabled is not False!"
    assert settings_v2.v2_live_enabled is False, "settings_v2.v2_live_enabled is not False!"
    print(f"[PASS] settings.live_trading_enabled == False, settings_v2.v2_live_enabled == False")

    # 3. AST static scan of backend/app/lab/
    lab_dir = BACKEND_DIR / "app" / "lab"
    assert lab_dir.exists(), f"Lab directory not found at {lab_dir}"
    violations = scan_ast_for_violations(lab_dir)

    if violations:
        print("[FAIL] Violations found in backend/app/lab/:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    print(f"[PASS] AST scan of {lab_dir}: 0 private exchange imports, 0 secret env reads, 0 order endpoints.")
    print("================================================================================")
    print("ALL test_lab_no_real_orders CHECKS PASSED.")
    print("================================================================================")


if __name__ == "__main__":
    main()
