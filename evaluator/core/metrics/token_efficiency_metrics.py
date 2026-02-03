# evaluator/metrics/token_efficiency_metrics.py
from typing import Dict, Any, Optional
import logging

from evaluator.core.metrics.base_metrics import BaseMetric
from evaluator.core.events import AgentEvent


class TokenEfficiencyMetric(BaseMetric):
    """
    Tracks token efficiency - the ratio of input tokens (prompt) to output tokens (completion).

    Token Efficiency Ratio = Total Prompt Tokens / Total Completion Tokens

    A lower ratio indicates more concise agent responses (less input needed per output token).
    A higher ratio indicates verbose prompts or short responses.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0

    def get_name(self) -> str:
        return "token_efficiency_metrics"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)

        if event_type == AgentEvent.LLM_QUERY_END:
            status = data.get('status')
            if status == 'success':
                prompt_tokens = data.get('prompt_tokens', 0) or 0
                completion_tokens = data.get('completion_tokens', 0) or 0

                self.total_prompt_tokens += prompt_tokens
                self.total_completion_tokens += completion_tokens

                self.logger.debug(
                    f"LLM call used {prompt_tokens} prompt tokens, {completion_tokens} completion tokens. "
                    f"Total: {self.total_prompt_tokens} / {self.total_completion_tokens}"
                )

    def get_value(self) -> Dict[str, Any]:
        if self.total_completion_tokens == 0:
            # Avoid division by zero
            efficiency_ratio = None
        else:
            efficiency_ratio = self.total_prompt_tokens / self.total_completion_tokens

        return {
            "token_efficiency_ratio": round(efficiency_ratio, 2) if efficiency_ratio is not None else None,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "average_tokens_per_call": round(
                (self.total_prompt_tokens + self.total_completion_tokens) / max(1, self.total_completion_tokens),
                2
            ) if self.total_completion_tokens > 0 else None
        }

    def reset(self) -> None:
        super().reset()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
