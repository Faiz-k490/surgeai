"""Completion must be an affirmative command, not a mention of being done."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.runtime.voice import COMPLETION_PHRASES, VoiceRuntime


class CompletionIntentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.voice = VoiceRuntime(SimpleNamespace(backend_root=Path(self.directory.name)))

    def test_documented_completion_phrases(self):
        for phrase in COMPLETION_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertTrue(self.voice.is_completion_intent(phrase))

    def test_natural_affirmative_commands(self):
        for phrase in ["I'm done!", "We're done.", "Hey surgeon, I am done",
                       "Okay, I am done now. Thanks!", "All done, thank you.",
                       "Session complete.", "The procedure is complete."]:
            with self.subTest(phrase=phrase):
                self.assertTrue(self.voice.is_completion_intent(phrase))

    def test_negated_completion_does_not_end_session(self):
        for phrase in ["I am not done yet", "I'm not finished", "We are not done",
                       "The procedure is not complete", "I never said I am done"]:
            with self.subTest(phrase=phrase):
                self.assertFalse(self.voice.is_completion_intent(phrase))

    def test_questions_and_future_conditions_do_not_end_session(self):
        for phrase in ["Am I done?", "I'm done?", "Are we finished?", "Are we all done?",
                       "Is the procedure complete?", "Tell me when I am done",
                       "What should I do when I am finished?",
                       "If we are done, what happens next?"]:
            with self.subTest(phrase=phrase):
                self.assertFalse(self.voice.is_completion_intent(phrase))

    def test_partial_tasks_and_substrings_do_not_end_session(self):
        for phrase in ["I am done with setup", "All done buttons should be blue",
                       "I am donegal", "That is iteration two", "Procedure completeness"]:
            with self.subTest(phrase=phrase):
                self.assertFalse(self.voice.is_completion_intent(phrase))

    def test_empty_and_unrelated_input(self):
        for phrase in [None, "", " ", "What is next?", "Show the current view"]:
            with self.subTest(phrase=phrase):
                self.assertFalse(self.voice.is_completion_intent(phrase))


if __name__ == "__main__":
    unittest.main()
