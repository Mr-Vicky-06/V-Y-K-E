"""Security policy gate deciding ACT, CONFIRM, or REFUSE for tool calls."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from voicecore.config import PolicyConfig
from voicecore.nlu.base import ToolCall
from voicecore.tools.registry import ToolRegistry


class Decision:
    ACT = "ACT"
    CONFIRM = "CONFIRM"
    REFUSE = "REFUSE"


@dataclass
class PolicyDecision:
    """Outcome of the policy gate evaluation."""
    decision: str  # ACT | CONFIRM | REFUSE
    reason: str = ""


class PolicyGate:
    """Evaluates proposed tool calls against risk tiers, confidence scores, and safety flags."""

    def __init__(
        self,
        config: Optional[PolicyConfig] = None,
        registry: Optional[ToolRegistry] = None,
    ) -> None:
        self.config = config or PolicyConfig()
        self.registry = registry or ToolRegistry()

    def decide(
        self,
        call: ToolCall,
        confidence: float,
        negation: bool = False,
        ungrounded: Optional[List[str]] = None,
    ) -> PolicyDecision:
        """Evaluate a single tool call and return ACT, CONFIRM, or REFUSE."""
        ungrounded = ungrounded or []

        # 1. Hard constraint: Negation detected
        if negation:
            return PolicyDecision(
                decision=Decision.REFUSE,
                reason="Negation detected in utterance",
            )

        # 2. Hard constraint: Check for ungrounded arguments for this tool
        tool_prefix = f"{call.name}."
        tool_ungrounded = [u for u in ungrounded if u == call.name or u.startswith(tool_prefix)]
        if tool_ungrounded:
            return PolicyDecision(
                decision=Decision.REFUSE,
                reason=f"Ungrounded arguments detected: {', '.join(tool_ungrounded)}",
            )

        # 3. Hard constraint: Tool must be registered
        tool_def = self.registry.get(call.name)
        if not tool_def:
            return PolicyDecision(
                decision=Decision.REFUSE,
                reason=f"Tool '{call.name}' is not in the authorized registry",
            )

        tier = tool_def.tier

        # 4. Hard constraint: T2 tools are forbidden in P0
        if tier == "T2":
            return PolicyDecision(
                decision=Decision.REFUSE,
                reason="Tier T2 (privileged/destructive) operations are forbidden in P0",
            )

        # 5. Pre-check independent of confidence (runs before ACT or CONFIRM)
        if tool_def.precheck is not None:
            try:
                ok, precheck_reason = tool_def.precheck(call.arguments)
                if not ok:
                    return PolicyDecision(
                        decision=Decision.REFUSE,
                        reason=f"Pre-check failed: {precheck_reason}",
                    )
            except Exception as e:
                return PolicyDecision(
                    decision=Decision.REFUSE,
                    reason=f"Pre-check error: {e}",
                )

        # 6. Confidence threshold gating for T0 and T1
        if confidence < self.config.confirm_threshold:
            return PolicyDecision(
                decision=Decision.REFUSE,
                reason=(
                    f"Confidence {confidence:.4f} is below confirm threshold "
                    f"{self.config.confirm_threshold:.2f}"
                ),
            )

        if confidence >= self.config.act_threshold:
            return PolicyDecision(
                decision=Decision.ACT,
                reason=f"Confidence {confidence:.4f} meets or exceeds act threshold {self.config.act_threshold:.2f}",
            )

        # Between confirm_threshold and act_threshold
        return PolicyDecision(
            decision=Decision.CONFIRM,
            reason=(
                f"Confidence {confidence:.4f} requires user confirmation "
                f"(between {self.config.confirm_threshold:.2f} and {self.config.act_threshold:.2f})"
            ),
        )

