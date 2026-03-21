from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class StepTracker:
    step_number: int = 1
    step_name: str = "Identify zone"

    def advance(self, scene: Dict[str, bool]) -> Tuple[int, str, str]:
        """
        Returns: (step_number, step_name, warning_message)
        Warning message is empty when no warning is active.
        """
        warning = ""

        if self.step_number == 1:
            if scene.get("red_present"):
                self.step_number, self.step_name = 2, "Select scalpel"
        elif self.step_number == 2:
            if scene.get("blue_present"):
                self.step_number, self.step_name = 3, "Incision and clamp prep"
            elif scene.get("red_present"):
                warning = "Incorrect instrument detected - scalpel required."
        elif self.step_number == 3:
            if scene.get("green_present"):
                self.step_number, self.step_name = 4, "Closure"
        else:
            self.step_number, self.step_name = 4, "Closure"

        return self.step_number, self.step_name, warning
