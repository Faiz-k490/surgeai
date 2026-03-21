# test_ws.py — quick WebSocket test script
import asyncio
import json

import websockets


async def test():
    async with websockets.connect("ws://localhost:5000/ws/training") as ws:
        await ws.send(json.dumps({"test": "hello"}))
        response = await ws.recv()
        print("Got:", response)


asyncio.run(test())
