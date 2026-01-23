# evaluator/metrics/tool_hallucination_metrics.py
from typing import Dict, Any, Optional, List, Set
import logging

from evaluator.core.metrics.base_metrics import BaseMetric
from evaluator.core.events import AgentEvent


class ToolHallucinationMetric(BaseMetric):
    """
    Tracks tool hallucinations - when the agent attempts to call tools that don't exist.

    A hallucination is detected when the agent calls a tool name that is not in the
    list of available tools (built-in + MCP server tools).

    Tracks:
    - Whether any hallucinations occurred (boolean flag)
    - Total count of hallucinated tool calls
    - Which tool names were hallucinated
    - How many turns had at least one hallucination
    - Detailed list of each hallucination with turn number and timestamp
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.available_tools: Set[str] = set()  # Set of valid tool names
        self.current_turn: int = 0  # Track which turn we're on (starts at 0, increments on LLM_QUERY_START)

        # Hallucination tracking
        self.hallucinated_tool_names: Set[str] = set()  # Unique hallucinated tool names
        self.hallucination_details: List[Dict[str, Any]] = []  # Each hallucination with details
        self.turns_with_hallucinations: Set[int] = set()  # Which turns had hallucinations

    def get_name(self) -> str:
        return "tool_hallucination_metrics"

    def process_event(self, event_type: AgentEvent, data: Dict[str, Any]) -> None:
        super().process_event(event_type, data)
        timestamp = data.get('timestamp')

        if event_type == AgentEvent.TOOLS_INITIALIZED:
            # Receive the list of available tools
            tool_names = data.get('tool_names', [])
            self.available_tools = set(tool_names)
            self.logger.info(f"Initialized with {len(self.available_tools)} available tools: {sorted(self.available_tools)}")

        elif event_type == AgentEvent.LLM_QUERY_START:
            # Each LLM query marks the start of a new turn
            self.current_turn += 1
            self.logger.debug(f"Starting turn {self.current_turn}")

        elif event_type == AgentEvent.TOOL_CALL_START:
            # Validate that the tool exists
            tool_name = data.get('tool_name')

            if not tool_name:
                self.logger.warning("TOOL_CALL_START event missing 'tool_name' field")
                return

            # Check if this tool is in the available tools list
            if tool_name not in self.available_tools:
                # Hallucination detected!
                self.logger.warning(
                    f"HALLUCINATION DETECTED: Agent attempted to call non-existent tool '{tool_name}' "
                    f"in turn {self.current_turn}. Available tools: {sorted(self.available_tools)}"
                )

                # Record the hallucination
                self.hallucinated_tool_names.add(tool_name)
                self.turns_with_hallucinations.add(self.current_turn)

                self.hallucination_details.append({
                    "turn": self.current_turn,
                    "tool_name": tool_name,
                    "timestamp": timestamp,
                    "args": data.get('args', {})
                })
            else:
                self.logger.debug(f"Valid tool call: '{tool_name}' in turn {self.current_turn}")

    def get_value(self) -> Dict[str, Any]:
        """
        Return hallucination metrics.

        Returns:
            Dict containing:
            - hallucination_detected: Boolean flag (True if any hallucinations occurred)
            - total_hallucinated_calls: Total count of hallucinated tool calls
            - hallucinated_tool_names: List of unique tool names that were hallucinated
            - turns_with_hallucinations: Count of turns that had at least one hallucination
            - hallucination_details: List of all hallucinations with turn, tool name, and timestamp
        """
        hallucination_detected = len(self.hallucination_details) > 0

        return {
            "hallucination_detected": hallucination_detected,
            "total_hallucinated_calls": len(self.hallucination_details),
            "hallucinated_tool_names": sorted(list(self.hallucinated_tool_names)),
            "turns_with_hallucinations": len(self.turns_with_hallucinations),
            "total_turns": self.current_turn,
            "hallucination_details": self.hallucination_details
        }

    def reset(self) -> None:
        """Reset all tracking state."""
        super().reset()
        self.available_tools = set()
        self.current_turn = 0
        self.hallucinated_tool_names = set()
        self.hallucination_details = []
        self.turns_with_hallucinations = set()
