try:
    from backend.app.logic.step_tracker import StepTracker
except ModuleNotFoundError:
    from app.logic.step_tracker import StepTracker


def test_step_tracker_progression():
    tracker = StepTracker()
    assert tracker.step_number == 1

    step, name, warning = tracker.advance({"red_present": True})
    assert step == 2
    assert warning == ""

    step, name, warning = tracker.advance({"red_present": True})
    assert step == 2
    assert warning != ""

    step, name, warning = tracker.advance({"blue_present": True})
    assert step == 3
