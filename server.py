import asyncio
import websockets
import json
from random import randint, choice
from datetime import datetime

async def handler(websocket):
    try:
        for i in range(100):
            data = {
                "id": i,
                "orderNumber": randint(1000, 9999),
                "customerName": f"Customer {randint(1, 100)}",
                "totalAmount": round(randint(1000, 5000) + randint(0, 99)/100, 2),
                "orderDate": datetime.now().isoformat(),
                "isPaid": choice([True, False]),
                "userName": choice(["محمد", "Sarah", "Mike", "Emma"])
            }
            await websocket.send(json.dumps(data))
    except websockets.exceptions.ConnectionClosedOK:
        print("Client disconnected")

async def main():
    async with websockets.serve(handler, "localhost", 8765):
        await asyncio.Future()

asyncio.run(main())