"""SQLAlchemy async database session configuration."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import get_settings

settings = get_settings()

# Create Async Engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    future=True,
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing asynchronous database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


from sqlalchemy import text


def _migrate_sqlite_columns(sync_conn):
    """Add new columns to existing SQLite tables if not present."""
    columns_to_ensure = {
        "ocr_results": [
            ("corrected_text", "TEXT"),
            ("refinement_provider", "VARCHAR(50)"),
            ("refinement_model", "VARCHAR(100)"),
            ("refinement_status", "VARCHAR(50) DEFAULT 'PENDING'"),
            ("refinement_error", "TEXT"),
            ("refinement_timestamp", "DATETIME"),
            ("proposed_changes_json", "JSON DEFAULT '[]'"),
            ("uncertain_spans_json", "JSON DEFAULT '[]'"),
            ("is_teacher_approved", "BOOLEAN DEFAULT 0"),
        ],
        "extracted_answers": [
            ("corrected_text", "TEXT"),
            ("uncertain_spans_json", "JSON DEFAULT '[]'"),
        ],
        "evaluations": [
            ("points_addressed_json", "JSON DEFAULT '[]'"),
            ("missing_points_json", "JSON DEFAULT '[]'"),
            ("contradictions_json", "JSON DEFAULT '[]'"),
            ("evaluation_method", "VARCHAR(64) DEFAULT 'DETERMINISTIC_HEURISTIC_FALLBACK'"),
        ],
    }

    for table, columns in columns_to_ensure.items():
        try:
            cursor = sync_conn.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in cursor.fetchall()}
            if not existing:
                continue
            for col_name, col_def in columns:
                if col_name not in existing:
                    sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))
        except Exception:
            pass


async def init_db() -> None:
    """Initialize database tables with automatic backward-compatible column migration."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_sqlite_columns)

    # Seed default user accounts if not present (preserving existing user data)
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(select(User).where(User.email == "teacher@ktu.edu.in"))
            if not res.scalars().first():
                teacher = User(
                    id=1,
                    email="teacher@ktu.edu.in",
                    hashed_password=get_password_hash("teacher123"),
                    full_name="Prof. KTU Evaluator",
                    role=UserRole.TEACHER,
                    department="Computer Science & Engineering",
                )
                session.add(teacher)

            res_admin = await session.execute(select(User).where(User.email == "admin@ktu.edu.in"))
            if not res_admin.scalars().first():
                admin = User(
                    id=2,
                    email="admin@ktu.edu.in",
                    hashed_password=get_password_hash("admin123"),
                    full_name="KTU Controller of Examinations",
                    role=UserRole.ADMIN,
                    department="Examination Cell",
                )
                session.add(admin)

            res_t2 = await session.execute(select(User).where(User.email == "teacher2@ktu.edu.in"))
            if not res_t2.scalars().first():
                teacher2 = User(
                    id=3,
                    email="teacher2@ktu.edu.in",
                    hashed_password=get_password_hash("teacher123"),
                    full_name="Prof. External Examiner",
                    role=UserRole.TEACHER,
                    department="Civil Engineering",
                )
                session.add(teacher2)

            await session.commit()
        except Exception:
            await session.rollback()

