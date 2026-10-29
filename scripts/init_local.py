"""Generate development-only secrets without printing them or replacing an existing file.

A new .env starts in training mode with the local volunteer account signed in automatically,
so a first run shows fictional data only. Switch DATA_MODE to production to read real sources.
"""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    print("Existing .env preserved")
else:
    content = (
        "DJANGO_ENV=development\n"
        "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver,api\n"
        "DATA_MODE=training\n"
        "LOCAL_AUTO_LOGIN=local-team\n"
    )
    for key in ["DJANGO_SECRET_KEY", "POSTGRES_ADMIN_PASSWORD", "DB_PASSWORD"]:
        content += f"{key}={secrets.token_urlsafe(50)}\n"
    with target.open("x") as output:
        output.write(content)
    target.chmod(0o600)
    print("Local .env created with private permissions, in training mode")
