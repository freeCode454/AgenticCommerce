"""Migrate one tenant's legacy provider keys without activating old configurations."""

import argparse
import asyncio

from sqlalchemy import select

from app.clients.postgres import AsyncSessionLocal
from app.conf.config import settings
from app.core.provider_keys import PREFIX, encrypt_api_key
from app.models.provider import Provider


async def migrate_keys(tenant_id: str, apply: bool = False) -> int:
    async with AsyncSessionLocal() as session:
        query = select(Provider).where(
            Provider.tenant_id == tenant_id, Provider.is_deleted == 0
        )
        if apply:
            query = query.with_for_update()
        rows = (await session.execute(query)).scalars().all()
        legacy = [
            row
            for row in rows
            if row.api_key_enc and not row.api_key_enc.startswith(PREFIX)
        ]
        if apply:
            for row in legacy:
                row.api_key_enc = encrypt_api_key(
                    row.api_key_enc, tenant_id, row.id, settings.PROVIDER_ENCRYPTION_KEY
                )
            await session.commit()
        return len(legacy)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write encrypted values; otherwise report count only",
    )
    args = parser.parse_args()
    count = asyncio.run(migrate_keys(args.tenant_id, args.apply))
    print(
        f"{'Encrypted' if args.apply else 'Legacy keys requiring encryption'}: {count}. No key values were printed."
    )
