"""Runtime patch for asyncpg.connect — required when DATABASE_URL points at a
transaction-mode pgbouncer (e.g. Supabase's pooler on port 6543).

Pgbouncer transaction mode multiplexes backend connections per-query, so any
prepared statement the client caches is invalidated the moment pgbouncer hands
the query to a different backend. asyncpg's default statement cache therefore
triggers `prepared statement "__asyncpg_stmt_1__" does not exist` under load.

We patch asyncpg.connect ONCE at import time, forcing both caches to 0 whenever
the caller didn't already specify them. Direct Postgres connections are
unaffected — these two args are always safe, just slightly slower.

Import this module at top of app/main.py (before any other app.* import that
might open a connection).
"""

from __future__ import annotations

from typing import Any

import asyncpg

_PATCHED_FLAG = "_saath_pooler_patched"


def _patch_asyncpg_connect() -> None:
    if getattr(asyncpg, _PATCHED_FLAG, False):
        return

    _original_connect = asyncpg.connect

    async def _patched_connect(*args: Any, **kwargs: Any) -> asyncpg.Connection:
        # asyncpg accepts only `statement_cache_size` (not `prepared_statement_cache_size`).
        kwargs.setdefault("statement_cache_size", 0)
        return await _original_connect(*args, **kwargs)

    asyncpg.connect = _patched_connect  # type: ignore[assignment]
    setattr(asyncpg, _PATCHED_FLAG, True)


_patch_asyncpg_connect()
