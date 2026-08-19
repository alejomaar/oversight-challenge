from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.url import async_database_url

engine = create_async_engine(async_database_url(), pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session
