"""
Deterministic surgical-step state machine driven by YOLO object detections.

Steps:
  1. Identify incision zone  — expects: banana (patient arm)
  2. Incision                — expects: scalpel (knife)
  3. Clamp application       — expects: clamp (scissors)
  4. Completion              — no expected tool
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("surgeai.logic.steps")


@dataclass
class _Step:
    number: int
    name: str
    expected: Optional[str]  # YOLO label required to advance


STEPS: List[_Step] = [
    _Step(1, "Identify incision zone", "banana"),
    _Step(2, "Incision", "knife"),
    _Step(3, "Clamp application", "scissors"),
    _Step(4, "Completion", None),
]

_TOOL_LABELS = {"knife", "scissors", "fork"}
_TOOL_DISPLAY = {"knife": "scalpel", "scissors": "clamp", "fork": "forceps"}

# Static fallback guidance per step (used when Cortex is unavailable)
FALLBACK_GUIDANCE: Dict[int, str] = {
    1: "Identify the incision zone on the patient arm.",
    2: "Select the scalpel for a controlled incision.",
    3: "Apply the clamp to secure the incision site.",
    4: "Procedure complete. Verify closure.",
}


@dataclass
class StepTracker:
    """Object-detection-based state machine with debounce and wrong-tool warnings."""

    step_index: int = 0
    _last_transition_time: float = field(default=0.0, repr=False)
    _debounce_sec: float = field(default=1.5, repr=False)
    _conf_threshold: float = field(default=0.35, repr=False)

    @property
    def current_step(self) -> _Step:
        return STEPS[min(self.step_index, len(STEPS) - 1)]

    @property
    def step_number(self) -> int:
        return self.current_step.number

    @property
    def step_name(self) -> str:
        return self.current_step.name

    def advance(self, detections: List[Dict[str, Any]]) -> Tuple[int, str, str]:
        """Evaluate detections and possibly transition steps.

        Parameters
        ----------
        detections : list[dict]
            Each dict has at minimum ``label`` (str) and ``confidence`` (float).
            These come from ``YoloDetector.detect()["objects"]``.

        Returns
        -------
        tuple[int, str, str]
            (step_number, step_name, warning_message)
            ``warning_message`` is empty when no warning is active.
        """
        warning = ""
        step = self.current_step

        if step.expected is None:
            return step.number, step.name, warning

        labels_present = {
            d["label"] for d in detections
            if d.get("confidence", 0) >= self._conf_threshold
        }

        now = time.time()
        in_cooldown = (now - self._last_transition_time) < self._debounce_sec

        if step.expected in labels_present and not in_cooldown:
            logger.info(
                "Step %d -> %d: '%s' detected",
                step.number,
                step.number + 1,
                step.expected,
            )
            self.step_index = min(self.step_index + 1, len(STEPS) - 1)
            self._last_transition_time = now
            return self.current_step.number, self.current_step.name, warning

        # Wrong-tool check: if we expect a specific tool and see a *different* tool
        if step.expected in _TOOL_LABELS:
            wrong = labels_present & _TOOL_LABELS - {step.expected}
            if wrong:
                names = ", ".join(_TOOL_DISPLAY.get(w, w) for w in wrong)
                expected_display = _TOOL_DISPLAY.get(step.expected, step.expected)
                warning = f"Incorrect instrument ({names}). {expected_display.capitalize()} required."

        return step.number, step.name, warning
