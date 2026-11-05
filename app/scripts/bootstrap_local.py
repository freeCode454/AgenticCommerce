"""Initialize development records and the private local asset bucket."""
import asyncio
from app.conf.config import settings
from app.clients.minio import ensure_bucket_exists
from app.scripts.seed_data import seed_data


async def main() -> None:
    if settings.is_production:
        raise RuntimeError("Local bootstrap is disabled outside dev/test")
    await seed_data()
    await asyncio.to_thread(ensure_bucket_exists)


if __name__ == "__main__":
    asyncio.run(main())
