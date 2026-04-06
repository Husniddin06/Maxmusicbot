import os
import aiosqlite
from datetime import date

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT    DEFAULT '',
                first_name  TEXT    DEFAULT '',
                language    TEXT    DEFAULT 'uz',
                is_banned   INTEGER DEFAULT 0,
                dl_today    INTEGER DEFAULT 0,
                dl_date     TEXT    DEFAULT '',
                joined_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
                last_active TEXT    DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS admins (
                user_id  INTEGER PRIMARY KEY,
                added_by INTEGER DEFAULT 0,
                added_at TEXT    DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS search_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                query       TEXT,
                searched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS favorites (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER,
                title    TEXT,
                artist   TEXT,
                url      TEXT,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS downloads (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER,
                title         TEXT,
                platform      TEXT,
                media_type    TEXT,
                downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS error_logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER DEFAULT 0,
                error_text TEXT,
                logged_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_search_user ON search_history(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_fav_user ON favorites(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_dl_user ON downloads(user_id)")
        try:
            await db.execute("ALTER TABLE users ADD COLUMN dl_today INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN dl_date TEXT DEFAULT ''")
        except Exception:
            pass
        await db.commit()


async def register_user(user_id, username, first_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name))
        await db.execute(
            "UPDATE users SET last_active=CURRENT_TIMESTAMP, username=?, first_name=? WHERE user_id=?",
            (username, first_name, user_id))
        await db.commit()


async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None


async def is_banned(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            return bool(row[0]) if row else False


async def ban_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
        await db.commit()


async def unban_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
        await db.commit()


async def get_all_users(include_banned=False):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = "SELECT * FROM users ORDER BY joined_at DESC" if include_banned \
              else "SELECT * FROM users WHERE is_banned=0 ORDER BY joined_at DESC"
        async with db.execute(sql) as c:
            return [dict(r) for r in await c.fetchall()]


async def get_banned_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE is_banned=1") as c:
            return [dict(r) for r in await c.fetchall()]


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async def count(sql, *args):
            async with db.execute(sql, args) as c:
                return (await c.fetchone())[0]
        today = date.today().isoformat()
        return {
            "total_users":     await count("SELECT COUNT(*) FROM users"),
            "active_users":    await count("SELECT COUNT(*) FROM users WHERE is_banned=0"),
            "banned_users":    await count("SELECT COUNT(*) FROM users WHERE is_banned=1"),
            "total_downloads": await count("SELECT COUNT(*) FROM downloads"),
            "audio_downloads": await count("SELECT COUNT(*) FROM downloads WHERE media_type='audio'"),
            "video_downloads": await count("SELECT COUNT(*) FROM downloads WHERE media_type='video'"),
            "today_downloads": await count("SELECT COUNT(*) FROM downloads WHERE downloaded_at LIKE ?", f"{today}%"),
            "today_users":     await count("SELECT COUNT(*) FROM users WHERE last_active LIKE ?", f"{today}%"),
            "total_searches":  await count("SELECT COUNT(*) FROM search_history"),
            "total_favorites": await count("SELECT COUNT(*) FROM favorites"),
            "total_admins":    await count("SELECT COUNT(*) FROM admins"),
        }


async def check_daily_limit(user_id, limit=30):
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT dl_today, dl_date FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
        if not row:
            return True, limit
        dl_today, dl_date = row[0] or 0, row[1] or ""
        if dl_date != today:
            await db.execute("UPDATE users SET dl_today=0, dl_date=? WHERE user_id=?", (today, user_id))
            await db.commit()
            return True, limit
        if dl_today >= limit:
            return False, 0
        return True, limit - dl_today


async def increment_daily_download(user_id):
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET dl_today=CASE WHEN dl_date=? THEN dl_today+1 ELSE 1 END, dl_date=? WHERE user_id=?",
            (today, today, user_id))
        await db.commit()


async def add_search_history(user_id, query):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO search_history (user_id, query) VALUES (?, ?)", (user_id, query))
        await db.execute(
            "DELETE FROM search_history WHERE user_id=? AND id NOT IN "
            "(SELECT id FROM search_history WHERE user_id=? ORDER BY searched_at DESC LIMIT 50)",
            (user_id, user_id))
        await db.commit()


async def get_search_history(user_id, limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT DISTINCT query, searched_at FROM search_history WHERE user_id=? ORDER BY searched_at DESC LIMIT ?",
            (user_id, limit)) as c:
            return [dict(r) for r in await c.fetchall()]


async def clear_history(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM search_history WHERE user_id=?", (user_id,))
        await db.commit()


async def add_favorite(user_id, title, artist, url):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM favorites WHERE user_id=? AND url=?", (user_id, url)) as c:
            if await c.fetchone():
                return False
        await db.execute("INSERT INTO favorites (user_id, title, artist, url) VALUES (?, ?, ?, ?)",
                         (user_id, title, artist, url))
        await db.commit()
        return True


async def get_favorites(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM favorites WHERE user_id=? ORDER BY added_at DESC", (user_id,)) as c:
            return [dict(r) for r in await c.fetchall()]


async def remove_favorite(fav_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM favorites WHERE id=? AND user_id=?", (fav_id, user_id))
        await db.commit()


async def log_download(user_id, title, platform, media_type):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO downloads (user_id, title, platform, media_type) VALUES (?, ?, ?, ?)",
                         (user_id, title, platform, media_type))
        await db.commit()
    await increment_daily_download(user_id)


async def get_user_downloads(user_id, limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT title, platform, media_type, downloaded_at FROM downloads WHERE user_id=? ORDER BY downloaded_at DESC LIMIT ?",
            (user_id, limit)) as c:
            return [dict(r) for r in await c.fetchall()]


async def set_language(user_id, lang):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET language=? WHERE user_id=?", (lang, user_id))
        await db.commit()


async def get_language(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT language FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            return row[0] if row else "uz"


async def add_admin(user_id, added_by=0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", (user_id, added_by))
        await db.commit()


async def remove_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        await db.commit()


async def get_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM admins") as c:
            return [r[0] for r in await c.fetchall()]


async def log_error(user_id, error_text):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO error_logs (user_id, error_text) VALUES (?, ?)", (user_id, error_text))
        await db.execute(
            "DELETE FROM error_logs WHERE id NOT IN (SELECT id FROM error_logs ORDER BY logged_at DESC LIMIT 200)")
        await db.commit()
