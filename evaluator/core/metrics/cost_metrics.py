# evaluator/metrics/cost_metrics.py
from typing import Dict, Any, Optional, List
import logging

from evaluator.core.metrics.base_metrics import BaseMetric
from evaluator.core.events import AgentEvent


# Model pricing in USD per 1 million tokens (as of January 2025)
MODEL_PRICING = {
    # Anthropic Claude models
    "claude-3-7-sonnet-20250219": {
        "input": 3.00,  # $3.00 per 1M input tokens
        "output": 15.00,  # $15.00 per 1M output tokens
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
    },
    "claude-3-5-sonnet-20240620": {
        "input": 3.00,
        "output": 15.00,
    },
    "claude-3-opus-20240229": {
        "input": 15.00,
        "output": 75.00,
    },
    "claude-3-sonnet-20240229": {
        "input": 3.00,
        "output": 15.00,
    },
    "claude-3-haiku-20240307": {
        "input": 0.25,
        "output": 1.25,
    },
    # OpenAI models
    "gpt-4-turbo": {
        "input": 10.00,
        "output": 30.00,
    },
    "gpt-4": {
        "input": 30.00,
        "output": 60.00,
    },
    "gpt-4o": {
        "input": 2.50,
        "output": 10.00,
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
    },
    "gpt-3.5-turbo": {
        "input": 0.50,
        "output": 1.50,
    },
    # Default fallback for unknown models
    "_default": {
        "input": 0.00,
        "output": 0.00,
    },
}


class CostPerTurnMetric(BaseMetric):
    """
    Tracks token costs for each LLM call based on model pricing.
    Calculates cost per turn and total cost.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.turn_costs: List[Dict[str, Any]] = []  # Store cost data for each turn
        self.total_cost_usd: float = 0.0
        self.current_model: Optional[str] = None

    def get_name(self) -> str:
        return "cost_metrics"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)

        if event_type == AgentEvent.LLM_QUERY_START:
            # Track the model being used
            self.current_model = data.get('model_name')

        elif event_type == AgentEvent.LLM_QUERY_END and data.get('status') == 'success':
            # Calculate cost for this turn
            prompt_tokens = data.get('prompt_tokens', 0)
            completion_tokens = data.get('completion_tokens', 0)

            if prompt_tokens is None or completion_tokens is None:
                self.logger.warning("Token data not available for cost calculation")
                return

            # Get pricing for the current model
            model_key = self.current_model or "_default"
            pricing = MODEL_PRICING.get(model_key)

            if pricing is None:
                # Try to find a partial match (e.g., "gpt-4" in "gpt-4-0125-preview")
                pricing = None
                for key in MODEL_PRICING.keys():
                    if key != "_default" and model_key and key in model_key:
                        pricing = MODEL_PRICING[key]
                        self.logger.debug(f"Using pricing for '{key}' for model '{model_key}'")
                        break

                if pricing is None:
                    pricing = MODEL_PRICING["_default"]
                    self.logger.warning(f"Unknown model '{model_key}', using default pricing (zero cost)")

            # Calculate cost in USD
            input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
            output_cost = (completion_tokens / 1_000_000) * pricing["output"]
            turn_cost = input_cost + output_cost

            self.turn_costs.append({
                "model": self.current_model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "input_cost_usd": round(input_cost, 6),
                "output_cost_usd": round(output_cost, 6),
                "total_cost_usd": round(turn_cost, 6),
            })

            self.total_cost_usd += turn_cost
            self.logger.debug(f"Turn cost: ${turn_cost:.6f} (Input: {prompt_tokens} tokens, Output: {completion_tokens} tokens)")

    def get_value(self) -> Dict[str, Any]:
        if not self.turn_costs:
            return {
                "total_cost_usd": 0.0,
                "average_cost_per_turn_usd": None,
                "total_turns": 0,
                "turn_breakdown": []
            }

        avg_cost = self.total_cost_usd / len(self.turn_costs) if self.turn_costs else 0

        return {
            "total_cost_usd": round(self.total_cost_usd, 6),
            "average_cost_per_turn_usd": round(avg_cost, 6),
            "total_turns": len(self.turn_costs),
            "turn_breakdown": self.turn_costs
        }

    def reset(self) -> None:
        super().reset()
        self.turn_costs = []
        self.total_cost_usd = 0.0
        self.current_model = None
