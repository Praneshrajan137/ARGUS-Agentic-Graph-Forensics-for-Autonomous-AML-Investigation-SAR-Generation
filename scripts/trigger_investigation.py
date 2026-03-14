"""
E2E Investigation Trigger -- Send real AML investigations to Tracer Agent.

Stdlib-only (runs on any Python 3.10+). No external dependencies.

Usage:
    python scripts/trigger_investigation.py
    python scripts/trigger_investigation.py --tracer-url http://localhost:8080
    python scripts/trigger_investigation.py --forge-url http://localhost:8000
"""
import argparse
import io
import json
import sys
import time
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PURPLE_URL = "http://localhost:8080"
GREEN_URL = "http://localhost:8000"
HEALTH_TIMEOUT = 120
INVESTIGATION_TIMEOUT = 180

GROUND_TRUTH_PATH = Path(__file__).parent.parent / "outputs" / "ground_truth.json"

INVESTIGATIONS = [
    {
        "case_id": "E2E-STRUCTURING-001",
        "subject_id": "0",
        "hop_depth": 3,
        "jurisdiction": "fincen",
        "description": "Structuring: 20 criminal sources -> mule node 0 ($9K-$9.8K band)",
    },
    {
        "case_id": "E2E-LAYERING-001",
        "subject_id": "10",
        "hop_depth": 5,
        "jurisdiction": "fincen",
        "description": "Layering: 6-hop chain from node 10, $100K decays to $82.5K",
    },
]


def http_get(url: str, timeout: float = 10.0) -> dict | None:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def http_post_json(url: str, body: dict, timeout: float = 180.0) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def wait_for_health(name: str, url: str, timeout: int = HEALTH_TIMEOUT) -> bool:
    health_url = f"{url}/health"
    print(f"  Waiting for {name} at {health_url} ...", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = http_get(health_url, timeout=5.0)
        if result and result.get("status") in ("healthy", "ok"):
            print(f" UP ({result})")
            return True
        print(".", end="", flush=True)
        time.sleep(3)
    print(f" TIMEOUT after {timeout}s")
    return False


def load_ground_truth() -> dict:
    if not GROUND_TRUTH_PATH.exists():
        print(f"  [WARN] Ground truth file not found: {GROUND_TRUTH_PATH}")
        return {}
    with open(GROUND_TRUTH_PATH) as f:
        return json.load(f)


def compute_recall(detected: list[str], ground_truth_nodes: list) -> tuple[float, int, int]:
    gt_set = {str(n) for n in ground_truth_nodes}
    det_set = set(detected)
    if not gt_set:
        return 1.0, 0, 0
    hits = len(gt_set & det_set)
    return hits / len(gt_set), hits, len(gt_set)


def print_separator(char: str = "=", width: int = 72) -> None:
    print(char * width)


def print_result(result: dict, investigation: dict, gt_crimes: list) -> None:
    print_separator()
    print(f"  INVESTIGATION: {investigation['description']}")
    print(f"  Case ID:       {result.get('case_id', 'N/A')}")
    print(f"  Status:        {result.get('status', 'N/A')}")
    print(f"  Typology:      {result.get('typology_detected', 'N/A')}")
    print(f"  Confidence:    {result.get('confidence_score', 0.0):.2f}")
    print(f"  Entities:      {len(result.get('involved_entities', []))} detected")
    print_separator("-")

    narrative = result.get("sar_narrative", "")
    if narrative:
        print("  SAR NARRATIVE:")
        print()
        for line in textwrap.wrap(narrative, width=70):
            print(f"    {line}")
        print()
    else:
        print("  SAR NARRATIVE: (none generated)")
        print()

    entities = result.get("involved_entities", [])
    if entities:
        print(f"  INVOLVED ENTITIES ({len(entities)}):")
        for i in range(0, len(entities), 10):
            chunk = entities[i : i + 10]
            print(f"    {', '.join(str(e) for e in chunk)}")
        print()

    if result.get("error_message"):
        print(f"  ERROR: {result['error_message']}")
        print()

    for crime in gt_crimes:
        crime_type = crime.get("crime_type", "")
        gt_nodes = crime.get("nodes_involved", [])
        recall, hits, total = compute_recall(entities, gt_nodes)
        print(f"  RECALL vs {crime_type.upper()} ground truth: {recall:.1%} ({hits}/{total} nodes)")

    print_separator()
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Trigger E2E AML investigations")
    parser.add_argument("--tracer-url", default=PURPLE_URL, help="Tracer Agent URL")
    parser.add_argument("--forge-url", default=GREEN_URL, help="Forge Agent URL")
    parser.add_argument("--timeout", type=int, default=HEALTH_TIMEOUT, help="Health check timeout (s)")
    args = parser.parse_args()

    print()
    print_separator("=")
    print("  E2E AML INVESTIGATION TRIGGER")
    print(f"  Forge Agent: {args.forge_url}")
    print(f"  Tracer Agent: {args.tracer_url}")
    print_separator("=")
    print()

    print("[1/4] Checking agent health...")
    green_ok = wait_for_health("Forge Agent", args.forge_url, timeout=args.timeout)
    purple_ok = wait_for_health("Tracer Agent", args.tracer_url, timeout=args.timeout)

    if not green_ok or not purple_ok:
        print("\nFATAL: One or both agents are not healthy. Aborting.")
        print("  Tip: docker-compose -f docker-compose.yml -f docker-compose.e2e.yml logs")
        sys.exit(1)

    print()
    print("[2/4] Loading ground truth...")
    gt = load_ground_truth()
    gt_crimes = gt.get("crimes", [])
    print(f"  Found {len(gt_crimes)} crime(s) in ground truth (difficulty={gt.get('difficulty', '?')})")
    for crime in gt_crimes:
        n = len(crime.get("nodes_involved", []))
        print(f"    - {crime['crime_type']}: {n} nodes involved")
    print()

    print(f"[3/4] Running {len(INVESTIGATIONS)} investigation(s)...")
    print()

    results = []
    for i, inv in enumerate(INVESTIGATIONS, 1):
        print(f"  >>> Investigation {i}/{len(INVESTIGATIONS)}: {inv['description']}")
        payload = {
            "case_id": inv["case_id"],
            "subject_id": inv["subject_id"],
            "hop_depth": inv["hop_depth"],
            "jurisdiction": inv["jurisdiction"],
        }
        print(f"      POST {args.tracer_url}/a2a")
        print(f"      Payload: {json.dumps(payload)}")

        start = time.time()
        try:
            result = http_post_json(
                f"{args.tracer_url}/a2a", payload, timeout=INVESTIGATION_TIMEOUT
            )
            elapsed = time.time() - start
            print(f"      Completed in {elapsed:.1f}s")
            results.append((result, inv))
        except urllib.error.HTTPError as e:
            elapsed = time.time() - start
            body = e.read().decode() if e.fp else ""
            print(f"      FAILED ({e.code}): {body[:200]} [{elapsed:.1f}s]")
            results.append(({"status": "error", "error_message": f"HTTP {e.code}: {body[:200]}"}, inv))
        except Exception as e:
            elapsed = time.time() - start
            print(f"      FAILED: {e} [{elapsed:.1f}s]")
            results.append(({"status": "error", "error_message": str(e)}, inv))
        print()

    print("[4/4] RESULTS")
    print()

    for result, inv in results:
        crime_type_match = inv["case_id"].split("-")[1].lower()
        matching_gt = [c for c in gt_crimes if c["crime_type"] == crime_type_match]
        print_result(result, inv, matching_gt or gt_crimes)

    all_detected = set()
    for result, _ in results:
        all_detected.update(result.get("involved_entities", []))

    all_gt = set()
    for crime in gt_crimes:
        all_gt.update(str(n) for n in crime.get("nodes_involved", []))

    if all_gt:
        hits = len(all_gt & all_detected)
        total_recall = hits / len(all_gt) if all_gt else 0
        print_separator("=")
        print(f"  AGGREGATE ENTITY RECALL: {total_recall:.1%} ({hits}/{len(all_gt)} criminal nodes)")
        print(f"  Total entities detected: {len(all_detected)}")
        print_separator("=")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
