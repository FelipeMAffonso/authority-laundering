"""Cost tracker — ported from spec-resistance. Thread-safe per-provider budget."""

import json
import threading
from datetime import datetime
from pathlib import Path


class BudgetExceededError(Exception):
    pass


class CostTracker:
    def __init__(self, budget_per_provider: float = 100.00,
                 max_calls_per_provider: int = 1_000_000,
                 log_dir: Path = None):
        self.budget_per_provider = budget_per_provider
        self.max_calls_per_provider = max_calls_per_provider
        self.log_dir = log_dir or Path(__file__).resolve().parent.parent / "data" / "costs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._costs: dict[str, float] = {}
        self._calls: dict[str, int] = {}
        self._tokens: dict[str, dict] = {}
        self._history: list[dict] = []

    def record_call(self, provider, model_id, input_tokens, output_tokens,
                    cost_usd, experiment="", trial_id=""):
        with self._lock:
            if provider not in self._costs:
                self._costs[provider] = 0.0
                self._calls[provider] = 0
                self._tokens[provider] = {"input": 0, "output": 0}
            if cost_usd is not None:
                self._costs[provider] += cost_usd
            self._calls[provider] += 1
            self._tokens[provider]["input"] += input_tokens
            self._tokens[provider]["output"] += output_tokens
            self._history.append({
                "timestamp": datetime.now().isoformat(),
                "provider": provider, "model_id": model_id,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "cumulative_cost": self._costs[provider],
                "call_number": self._calls[provider],
                "experiment": experiment, "trial_id": trial_id,
            })

    def check_budget(self, provider: str) -> bool:
        with self._lock:
            cost = self._costs.get(provider, 0.0)
            calls = self._calls.get(provider, 0)
        if cost > self.budget_per_provider:
            raise BudgetExceededError(f"{provider}: ${cost:.4f} spent")
        if calls >= self.max_calls_per_provider:
            raise BudgetExceededError(f"{provider}: {calls} calls")
        return True

    def get_summary(self) -> dict:
        providers = set(self._costs.keys()) | set(self._calls.keys())
        return {p: {
            "total_cost_usd": round(self._costs.get(p, 0.0), 6),
            "total_calls": self._calls.get(p, 0),
            "input_tokens": self._tokens.get(p, {}).get("input", 0),
            "output_tokens": self._tokens.get(p, {}).get("output", 0),
        } for p in sorted(providers)}

    def print_summary(self):
        s = self.get_summary()
        total_cost = sum(v["total_cost_usd"] for v in s.values())
        total_calls = sum(v["total_calls"] for v in s.values())
        print("\n" + "=" * 60)
        print("COST SUMMARY")
        print("=" * 60)
        for p, d in s.items():
            print(f"  {p:12s}  ${d['total_cost_usd']:.4f}  ({d['total_calls']} calls)")
        print(f"  {'TOTAL':12s}  ${total_cost:.4f}  ({total_calls} calls)")
        print("=" * 60)

    def save_log(self, filename: str = None):
        if filename is None:
            filename = f"cost_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = self.log_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "summary": self.get_summary(),
                "history": self._history,
            }, f, indent=2)
        return path
