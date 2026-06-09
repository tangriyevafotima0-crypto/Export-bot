"""SQLAlchemy 2.0 ORM models for the Anti-Stalker Intelligence System.

Defines all database tables for tracking users, events, and analysis results.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, JSON, Text, Integer, Float, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class TrackedUser(Base):
    """A Telegram user being monitored for stalking behavior."""

    __tablename__ = "tracked_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    suspicion_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    story_views: Mapped[list["StoryView"]] = relationship(
        back_populates="tracked_user", cascade="all, delete-orphan"
    )
    online_events: Mapped[list["OnlineEvent"]] = relationship(
        back_populates="tracked_user", cascade="all, delete-orphan"
    )
    suspicion_patterns: Mapped[list["SuspicionPattern"]] = relationship(
        back_populates="tracked_user", cascade="all, delete-orphan"
    )


class StoryView(Base):
    """A story view event by a tracked user."""

    __tablename__ = "story_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tracked_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracked_users.id"), nullable=False
    )
    story_id: Mapped[int] = mapped_column(Integer, nullable=False)
    viewed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    view_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reaction: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    tracked_user: Mapped["TrackedUser"] = relationship(back_populates="story_views")


class OnlineEvent(Base):
    """An online/offline status change event for a tracked user."""

    __tablename__ = "online_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tracked_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracked_users.id"), nullable=False
    )
    went_online: Mapped[datetime] = mapped_column(nullable=False)
    went_offline: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    overlaps_with_me: Mapped[bool] = mapped_column(Boolean, default=False)

    tracked_user: Mapped["TrackedUser"] = relationship(back_populates="online_events")


class SuspicionPattern(Base):
    """A detected suspicion pattern for a tracked user."""

    __tablename__ = "suspicion_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tracked_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracked_users.id"), nullable=False
    )
    pattern_type: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    tracked_user: Mapped["TrackedUser"] = relationship(
        back_populates="suspicion_patterns"
    )


class BioLinkVisit(Base):
    """A visit to a tracking link placed in bio or messages."""

    __tablename__ = "bio_link_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    link_id: Mapped[str] = mapped_column(String(100), nullable=False)
    visitor_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    referer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    device_info: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    visited_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    matched_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tracked_users.id"), nullable=True
    )


class DailyReport(Base):
    """A daily summary report of monitoring activity."""

    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    total_events: Mapped[int] = mapped_column(Integer, default=0)
    total_alerts: Mapped[int] = mapped_column(Integer, default=0)
    top_suspects: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Alert(Base):
    """An alert generated when suspicion threshold is exceeded."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tracked_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracked_users.id"), nullable=False
    )
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
