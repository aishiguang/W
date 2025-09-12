from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, Enum, Index, JSON, UniqueConstraint, LargeBinary, Boolean, DateTime, func
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .db import Base

class Place(Base):
    __tablename__ = "places"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text())

class Transition(Base):
    __tablename__ = "transitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text())

class Arc(Base):
    """
    Either Place -> Transition (PT) or Transition -> Place (TP).
    Exactly one of source_place_id/source_transition_id set, and similarly for target_*.
    """
    __tablename__ = "arcs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
    source_transition_id: Mapped[int | None] = mapped_column(ForeignKey("transitions.id"))
    target_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
    target_transition_id: Mapped[int | None] = mapped_column(ForeignKey("transitions.id"))
    weight: Mapped[int] = mapped_column(Integer, default=1)

class Marking(Base):
    __tablename__ = "markings"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)

class MarkingToken(Base):
    __tablename__ = "marking_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    marking_id: Mapped[int] = mapped_column(ForeignKey("markings.id", ondelete="CASCADE"), index=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id", ondelete="CASCADE"), index=True)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("marking_id", "place_id", name="uq_marking_place"),)

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    content: Mapped[str] = mapped_column(Text())
    related_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
    related_transition_id: Mapped[int | None] = mapped_column(ForeignKey("transitions.id"))
    tags: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

# MySQL FULLTEXT index for simple retrieval
Index("ix_documents_fulltext", Document.title, Document.content, mysql_prefix="FULLTEXT")

class Embedding(Base):
    __tablename__ = "embeddings"
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), unique=True)
    dim: Mapped[int] = mapped_column(Integer)
    normalized: Mapped[bool] = mapped_column(Boolean, default=True)
    vector: Mapped[bytes] = mapped_column(LargeBinary)  # store float32 bytes
