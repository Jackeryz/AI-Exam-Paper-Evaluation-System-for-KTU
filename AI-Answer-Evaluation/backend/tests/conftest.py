import os
import sys

# Prevent OpenMP runtime collision between PyTorch and PaddleOCR on Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
try:
    import torch
except Exception:
    pass

import shutil
from pathlib import Path

# Ensure project root and backend are always in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR = _PROJECT_ROOT / "backend"
for p in [str(_PROJECT_ROOT), str(_BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from typing import AsyncGenerator
import pytest
from starlette.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.future import select

from app.core.config import get_settings
from app.core.security import create_access_token, get_password_hash
from app.database.session import Base, get_db, _migrate_sqlite_columns
from app.models.user import User, UserRole
from app.main import app


@pytest.fixture(scope="session")
def test_db_setup(tmp_path_factory):
    """Create a temporary, isolated SQLite test database for the entire test session."""
    temp_dir = tmp_path_factory.mktemp("isolated_test_db")
    db_file = temp_dir / "test_isolated_ai_evaluation.db"
    test_db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

    settings = get_settings()
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = test_db_url

    # Create dedicated async engine and sessionmaker for test db
    test_engine = create_async_engine(test_db_url, future=True)
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Initialize schema and seed accounts
    import asyncio

    async def _init_test_schema():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_migrate_sqlite_columns)

        async with TestSessionLocal() as session:
            t1 = User(
                id=1,
                email="teacher@ktu.edu.in",
                hashed_password=get_password_hash("teacher123"),
                full_name="Prof. Primary Evaluator",
                role=UserRole.TEACHER,
                department="Computer Science & Engineering",
            )
            admin = User(
                id=2,
                email="admin@ktu.edu.in",
                hashed_password=get_password_hash("admin123"),
                full_name="KTU Exam Controller",
                role=UserRole.ADMIN,
                department="Examination Cell",
            )
            t2 = User(
                id=3,
                email="teacher2@ktu.edu.in",
                hashed_password=get_password_hash("teacher123"),
                full_name="Prof. External Examiner",
                role=UserRole.TEACHER,
                department="Mechanical Engineering",
            )
            session.add_all([t1, admin, t2])
            await session.commit()

    asyncio.run(_init_test_schema())

    # Override get_db dependency in FastAPI app
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    yield {
        "db_file": db_file,
        "db_url": test_db_url,
        "engine": test_engine,
        "sessionmaker": TestSessionLocal,
    }

    # Teardown
    app.dependency_overrides.pop(get_db, None)
    settings.DATABASE_URL = original_db_url
    asyncio.run(test_engine.dispose())
    if db_file.exists():
        try:
            db_file.unlink()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def prevent_dev_db_pollution(test_db_setup):
    """Regression check safeguard: forbid any test from executing against production/dev DB."""
    settings = get_settings()
    db_url = str(settings.DATABASE_URL).lower()
    
    # Must NOT be the active development database file
    if "ai_evaluation.db" in db_url and "isolated" not in db_url and "test" not in db_url:
        raise RuntimeError(
            f"CRITICAL TEST SAFEGUARD: Attempted to run automated test against development/production database: {settings.DATABASE_URL}. "
            "All automated tests MUST execute exclusively against an isolated test database!"
        )


@pytest.fixture
def teacher1_token():
    return create_access_token({"sub": "teacher@ktu.edu.in", "role": "teacher", "user_id": 1})


@pytest.fixture
def teacher2_token():
    return create_access_token({"sub": "teacher2@ktu.edu.in", "role": "teacher", "user_id": 3})


@pytest.fixture
def admin_token():
    return create_access_token({"sub": "admin@ktu.edu.in", "role": "admin", "user_id": 2})


@pytest.fixture
def client(test_db_setup, teacher1_token):
    """Authenticated TestClient for Teacher 1 (default authenticated client)."""
    return TestClient(app, headers={"Authorization": f"Bearer {teacher1_token}"})


@pytest.fixture
def auth_client(client):
    """Alias for client."""
    return client


@pytest.fixture
def teacher2_client(test_db_setup, teacher2_token):
    """Authenticated TestClient for Teacher 2 (used for authorization & multi-user isolation tests)."""
    return TestClient(app, headers={"Authorization": f"Bearer {teacher2_token}"})


@pytest.fixture
def admin_client(test_db_setup, admin_token):
    """Authenticated TestClient for Administrator."""
    return TestClient(app, headers={"Authorization": f"Bearer {admin_token}"})


@pytest.fixture
def unauth_client(test_db_setup):
    """Unauthenticated TestClient (used to verify 401 rejections)."""
    return TestClient(app)
