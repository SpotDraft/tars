from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

# ---------------------------------------------------------------------------
# Engine + session factory
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEPLOYMENT_ENV == "DEV",
    pool_pre_ping=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Declarative base — all ORM models must inherit from this
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# RuntimeBaseModel
# Every control-plane table inherits from this.
# workspace_id is a raw bigint — no FK to Django's CompanyProfile.
# created_by_org_user_id / updated_by_org_user_id are raw bigints — no FK.
# ---------------------------------------------------------------------------


class RuntimeBaseModel(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    workspace_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    created_by_org_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_by_org_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


# ---------------------------------------------------------------------------
# SoftDeleteMixin
# Composed onto admin-managed entities that support soft delete.
# Not used on append-only / immutable tables.
# ---------------------------------------------------------------------------


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by_org_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
