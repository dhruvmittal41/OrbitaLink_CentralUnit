import httpx
import os


async def fetch_users():
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{ os.environ['PRISMA_SERVICE_URL']}/users")
        r.raise_for_status()
        return r.json()
