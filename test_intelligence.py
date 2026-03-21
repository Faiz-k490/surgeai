# test_intelligence.py
import asyncio
from dotenv import load_dotenv
load_dotenv()
from intelligence_pipeline import run_pipeline

async def test():
    result = await run_pipeline("What are the steps for a laparoscopic cholecystectomy?")
    print("Answer:", result.answer)
    print("Error:", result.error)

asyncio.run(test())
