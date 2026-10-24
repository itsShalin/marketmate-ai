"""Try the agent from the command line.
  python run_demo.py                       # uses .env settings
  python run_demo.py --request "Promote our new candles"
Tip: MOCK_LLM=true SAMPLE_MODE=true python run_demo.py   -> runs with no key and no backend."""
import argparse
import json

from marketing_agent.orchestrator import run_agent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--business", default="biz_001")
    ap.add_argument("--request", default="Write posts for this week's new arrivals")
    args = ap.parse_args()
    out = run_agent(args.business, args.request)
    print("\n=== FINAL OUTPUT ===")
    print(json.dumps(out.model_dump(), indent=2, ensure_ascii=False))
