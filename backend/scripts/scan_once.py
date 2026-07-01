"""Run one autonomous scan and print emitted signals."""

from __future__ import annotations

from app import scanner


def main() -> None:
    r = scanner.scan_once()
    print(f"scanned={r['scanned']} emitted={r['emitted']} errors={r['errors']} min_conf={r['min_confidence']}")
    for s in r["signals"]:
        print(f"  {s['symbol']:9} {s['interval']:>3} {s['label']:<11} conf={s['confidence']:>4} "
              f"regime={s['regime']:<9} entry={s['entry']} stop={s['stop']} target={s['target']} (id={s['id']})")


if __name__ == "__main__":
    main()
