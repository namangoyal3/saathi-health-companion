"""pytest fixtures shared across all tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.main import app


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.DefaultEventLoopPolicy:
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture()
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
