"""SQLAlchemy models for the persona simulation database."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Allowed values, shared by the CLI validation layer.
ACTIONS = ("ignore", "like", "comment", "share", "click", "convert", "reject")
SENTIMENTS = ("positive", "neutral", "negative")
REACTION_STATUSES = ("pending", "ok", "failed")
RUN_STATUSES = ("running", "completed", "partial")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Idea(Base):
    """A product/service idea being tested."""

    __tablename__ = "ideas"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    ad_copy: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    research: Mapped[list[Research]] = relationship(back_populates="idea", cascade="all, delete-orphan")
    runs: Mapped[list[Run]] = relationship(back_populates="idea", cascade="all, delete-orphan")


class Research(Base):
    """A market-research finding linked to an idea."""

    __tablename__ = "research"

    id: Mapped[int] = mapped_column(primary_key=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id", ondelete="CASCADE"))
    topic: Mapped[str] = mapped_column(String(200))
    finding: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    idea: Mapped[Idea] = relationship(back_populates="research")


class Persona(Base):
    """A reusable simulated social media user."""

    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(String(50))
    occupation: Mapped[str | None] = mapped_column(String(200))
    income_level: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(200))
    segment: Mapped[str | None] = mapped_column(String(200))
    bio: Mapped[str | None] = mapped_column(Text)
    personality: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    interests: Mapped[list[str] | None] = mapped_column(JSON)
    platforms: Mapped[list[str] | None] = mapped_column(JSON)
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    origin: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    state: Mapped[PersonaState | None] = relationship(
        back_populates="persona", cascade="all, delete-orphan", uselist=False
    )
    reactions: Mapped[list[Reaction]] = relationship(back_populates="persona", cascade="all, delete-orphan")


class PersonaState(Base):
    """Mutable state of a persona: mood, interest and memory of past exposures."""

    __tablename__ = "persona_state"

    persona_id: Mapped[int] = mapped_column(ForeignKey("personas.id", ondelete="CASCADE"), primary_key=True)
    mood: Mapped[str | None] = mapped_column(String(100))
    interest_level: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    memory: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    persona: Mapped[Persona] = relationship(back_populates="state")


class Run(Base):
    """One simulation round of an idea against a set of personas."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="running")
    notes: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    idea: Mapped[Idea] = relationship(back_populates="runs")
    reactions: Mapped[list[Reaction]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Reaction(Base):
    """A persona's reaction to an idea within a run (one row per run+persona)."""

    __tablename__ = "reactions"
    __table_args__ = (UniqueConstraint("run_id", "persona_id", name="uq_reaction_run_persona"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    persona_id: Mapped[int] = mapped_column(ForeignKey("personas.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    action: Mapped[str | None] = mapped_column(String(20))
    sentiment: Mapped[str | None] = mapped_column(String(20))
    purchase_intent: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    objections: Mapped[list[str] | None] = mapped_column(JSON)
    react_trace: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    run: Mapped[Run] = relationship(back_populates="reactions")
    persona: Mapped[Persona] = relationship(back_populates="reactions")
