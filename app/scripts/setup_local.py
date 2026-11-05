"""Create private local overrides without changing existing .env or application data."""
import json
from pathlib import Path
import secrets
from dotenv import dotenv_values
from app.core.provider_keys import encryption_key, new_encryption_key


def setup_local() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / ".env.local"
    if path.exists():
        current = dotenv_values(path).get("PROVIDER_ENCRYPTION_KEY")
        if current:
            encryption_key(current)
        else:
            with path.open("a", encoding="utf-8") as stream:
                stream.write("\nPROVIDER_ENCRYPTION_KEY=" + new_encryption_key() + "\n")
            print("Added an independent provider encryption key to existing .env.local.")
        print("Using existing .env.local; credentials were not changed.")
        return
    values = {
        "APP_ENV": "dev", "APP_HOST": "127.0.0.1", "APP_PORT": "8002",
        "FRONTEND_PORT": "5174", "DEBUG": "false", "AUTH_ENABLED": "true",
        "SECRET_KEY": secrets.token_urlsafe(48),
        "PROVIDER_ENCRYPTION_KEY": new_encryption_key(),
        "POSTGRES_HOST": "127.0.0.1", "POSTGRES_PORT": "5435",
        "POSTGRES_USER": "agentic", "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "POSTGRES_DB": "agentic_commerce", "REDIS_PORT": "6381",
        "REDIS_URL": "redis://127.0.0.1:6381/0",
        "MINIO_API_PORT": "9010", "MINIO_CONSOLE_PORT": "9011",
        "MINIO_ENDPOINT": "127.0.0.1:9010", "MINIO_ACCESS_KEY": "local" + secrets.token_hex(8),
        "MINIO_SECRET_KEY": secrets.token_urlsafe(32), "MINIO_BUCKET": "agentic-assets",
        "MINIO_SECURE": "false", "ALLOW_MOCK_ASSETS": "false",
        "BOOTSTRAP_ADMIN_EMAIL": "admin@agentic.com",
        "BOOTSTRAP_ADMIN_PASSWORD": secrets.token_urlsafe(18),
        "CORS_ORIGINS": json.dumps(["http://127.0.0.1:5174", "http://localhost:5174"]),
        "TRUSTED_HOSTS": json.dumps(["localhost", "127.0.0.1", "agentic-backend"]),
    }
    # Exclusive creation avoids silently rotating credentials used by existing volumes.
    with path.open("x", encoding="utf-8") as stream:
        stream.write("# Private local overrides. Do not commit or share this file.\n")
        for key, value in values.items():
            stream.write(f"{key}={value}\n")
    print("Created .env.local. Administrator credentials are stored there; model keys remain in .env.")


if __name__ == "__main__":
    setup_local()
