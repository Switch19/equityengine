"""
Database engine and session management.

get_db() is a FastAPI dependency: each request gets its own SQLAlchemy
session, and the session is always closed afterwards, even if the
request raises an exception.
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------
# Additive column sync
# ---------------------------------------------------------------------
#
# SQLAlchemy's create_all() — which main.py uses instead of Alembic, see
# the rationale in its module docstring — creates missing TABLES but
# never alters an existing one. So a column added to a model after the
# table already exists in someone's database is simply absent at
# runtime, and the first query touching it fails with an
# UndefinedColumn error rather than anything that points at the cause.
#
# This closes that specific gap for plain, nullable, additive columns:
# it compares the live table against the model and issues one ALTER
# TABLE ... ADD COLUMN per genuinely missing column. It deliberately
# does NOT attempt anything else a migration tool does — no dropping,
# renaming, retyping, backfilling, or constraint changes — because
# those need a considered data-migration decision, not an implicit one
# at startup. If this project ever needs any of those, that is the
# point to adopt Alembic properly rather than to grow this function.

# {table_name: [column_name, ...]} — each must be nullable in the model.
ADDITIVE_COLUMNS = {
    "applications": ["primary_reason", "growth_tip"],
}


def sync_additive_columns() -> list[str]:
    """
    Adds any column listed in ADDITIVE_COLUMNS that the live table is
    missing, using the type SQLAlchemy already declares for it in the
    model, so there is no second, hand-written source of truth for the
    column type. Returns the qualified names actually added (empty on
    an already-current database), which main.py logs on startup.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    added: list[str] = []

    for table_name, column_names in ADDITIVE_COLUMNS.items():
        # Nothing to patch if create_all() just built the table — it
        # will already have every column the model declares.
        if table_name not in existing_tables:
            continue

        table = Base.metadata.tables.get(table_name)
        if table is None:
            continue

        live_columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name in column_names:
            if column_name in live_columns or column_name not in table.c:
                continue

            column = table.c[column_name]
            column_type = column.type.compile(dialect=engine.dialect)
            with engine.begin() as connection:
                connection.execute(
                    text(f'ALTER TABLE {table_name} ADD COLUMN "{column_name}" {column_type} NULL')
                )
            added.append(f"{table_name}.{column_name}")

    return added
