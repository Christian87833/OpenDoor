import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "opendoor.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credential_id BLOB UNIQUE NOT NULL,
                public_key BLOB NOT NULL,
                sign_count INTEGER NOT NULL DEFAULT 0,
                name TEXT NOT NULL DEFAULT 'My Device',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def save_credential(credential_id: bytes, public_key: bytes, sign_count: int, name: str = "My Device"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO credentials (credential_id, public_key, sign_count, name) VALUES (?, ?, ?, ?)",
            (credential_id, public_key, sign_count, name),
        )
        await db.commit()


async def get_all_credentials() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM credentials ORDER BY created_at") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_credential_by_id(credential_id: bytes) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM credentials WHERE credential_id = ?", (credential_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_sign_count(credential_id: bytes, sign_count: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE credentials SET sign_count = ? WHERE credential_id = ?",
            (sign_count, credential_id),
        )
        await db.commit()


async def delete_credential(credential_id: bytes):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM credentials WHERE credential_id = ?", (credential_id,))
        await db.commit()
