import os
import sys
from dotenv import load_dotenv

# Ensure we're running from the right directory
load_dotenv()

try:
    from backend.app.loop_b.tts_pipeline import speak
except ImportError:
    print("Please run this script from the root repository directory (where the .env file is).")
    print("Example: python test_elevenlabs.py")
    sys.exit(1)

print("Starting ElevenLabs TTS test...")
print(f"API Key loaded: {'YES' if os.environ.get('ELEVENLABS_API_KEY') else 'NO'}")

test_phrase = "Hello doctor. This is a standalone test of the Eleven Labs audio streaming system. No other APIs have been called."

try:
    speak(test_phrase)
    print("Test complete! Did you hear the audio?")
except Exception as e:
    print(f"Something went wrong: {e}")
