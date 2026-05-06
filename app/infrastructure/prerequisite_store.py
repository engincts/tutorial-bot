from sqlalchemy import Column, String, DateTime, text
from sqlalchemy.orm import declarative_base
from app.infrastructure.database import Base

class KCPrerequisiteORM(Base):
    __tablename__ = "kc_prerequisites"

    kc_id = Column(String(255), primary_key=True)
    prereq_kc_id = Column(String(255), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class PrerequisiteStore:
    async def get_prerequisites(self, session: AsyncSession, kc_ids: list[str]) -> dict[str, list[str]]:
        if not kc_ids:
            return {}
        stmt = select(KCPrerequisiteORM).where(KCPrerequisiteORM.kc_id.in_(kc_ids))
        result = await session.execute(stmt)
        
        prereqs = {}
        for row in result.scalars().all():
            prereqs.setdefault(row.kc_id, []).append(row.prereq_kc_id)
        return prereqs
