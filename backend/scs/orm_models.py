"""SQLAlchemy ORM table definitions."""
from __future__ import annotations

from sqlalchemy import (
    Boolean, Column, Date, Float, Integer, String, Text,
    ARRAY, UniqueConstraint,
)
from scs.db import Base


class SupplierRow(Base):
    __tablename__ = "suppliers"

    id          = Column(String, primary_key=True)
    name        = Column(String, nullable=False)
    legal_name  = Column(String)
    country     = Column(String(2), nullable=False, index=True)
    category    = Column(String, nullable=False)
    cin         = Column(String)
    website     = Column(String)
    incorporated = Column(Date)
    aliases     = Column(ARRAY(String), nullable=False, server_default="{}")
    is_illustrative = Column(Boolean, nullable=False, default=False)
    note        = Column(Text)
    address     = Column(String)
    lat         = Column(Float)
    lng         = Column(Float)

    __table_args__ = (UniqueConstraint("id", name="uq_supplier_id"),)


class NewsArticleRow(Base):
    __tablename__ = "news_articles"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    article_id  = Column(String, nullable=False, index=True)
    supplier_id = Column(String, nullable=False, index=True)
    title       = Column(String)
    body        = Column(Text, nullable=False)
    url         = Column(String)
    published_at = Column(String)


class ReferenceListRow(Base):
    __tablename__ = "reference_lists"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    list_name   = Column(String, nullable=False, index=True)  # ofac_sdn, bis_crs, wb_debarred
    entity_name = Column(String, nullable=False)
    raw         = Column(Text)
