import asyncio
from sqlalchemy import select, text
from app.clients.postgres import AsyncSessionLocal

async def check():
    try:
        async with AsyncSessionLocal() as s:
            r = await s.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))
            tables = [row[0] for row in r.fetchall()]
            print(f"Tables ({len(tables)}):")
            for t in tables:
                print(f"  {t}")

            from app.models.user import User
            r2 = await s.execute(select(User))
            users = r2.scalars().all()
            print(f"\nUsers: {len(users)}")
            for u in users:
                print(f"  email={u.email} name={u.name} role={u.role} status={u.status}")
    except Exception as e:
        print(f"ERROR: {e}")

asyncio.run(check())
