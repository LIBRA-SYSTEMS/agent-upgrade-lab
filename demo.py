"""Short, reproducible terminal demonstration using the installed CLI."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
exe = Path(sys.executable).parent / "agent-upgrade"
examples = Path(__file__).resolve().parent / "examples"
for name, version, expected in [("refund", "changed", 1), ("refund", "pinned", 0), ("support", "changed", 1)]:
    target = a.output / f"{name}-{version}.json"
    proc = subprocess.run([str(exe), str(examples / (name + ".py")), "--candidate", version, "--output", str(target)], capture_output=True, text=True, timeout=65)
    if proc.returncode != expected:
        print(proc.stdout, proc.stderr)
        raise SystemExit("Unexpected demo result")
    result = json.loads(target.read_text())
    print(f"{name} / {version}: {result['verdict']} (CLI exit {proc.returncode})")
    print("  baseline:", json.dumps(result["baseline"]["observation"], ensure_ascii=False))
    print("  candidate:", json.dumps(result["candidate"]["observation"], ensure_ascii=False))
print("Expected differences reproduced; no real business action performed.")
