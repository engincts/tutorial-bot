import asyncio
from app.infrastructure.database import init_db, get_session_factory
from app.settings import get_settings
from sqlalchemy import text

async def fix():
    settings = get_settings()
    init_db(settings)
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(text("UPDATE mastery_scores SET subject = 'tyt_matematik' WHERE subject = 'matematik'"))
        await session.execute(text("UPDATE mastery_scores SET subject = 'tyt_fizik' WHERE subject = 'fizik'"))
        await session.execute(text("UPDATE mastery_scores SET subject = 'tyt_kimya' WHERE subject = 'kimya'"))
        await session.execute(text("UPDATE mastery_scores SET subject = 'tyt_biyoloji' WHERE subject = 'biyoloji'"))
        await session.commit()
        print('Fixed hardcoded subjects.')

asyncio.run(fix())
