"""
CortexPrime Database Layer
--------------------------
Async SQLAlchemy + pgvector integration.

Public API
----------
- engine          : AsyncEngine singleton
- AsyncSessionLocal: bound session factory
- Base            : DeclarativeBase for all ORM models
- get_session()   : FastAPI dependency that yields an AsyncSession
- init_db()       : create all tables (dev / test only)
"""
from backend.database.engine  import engine, AsyncSessionLocal, init_db  # noqa: F401
from backend.database.base    import Base                                  # noqa: F401
from backend.database.session import get_session                           # noqa: F401
