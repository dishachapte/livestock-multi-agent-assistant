"""Database tables for the farm assistant."""
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Animal(Base):
    """One animal in the herd."""

    __tablename__ = "animals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    species: Mapped[str] = mapped_column(String(50), default="cattle")
    breed: Mapped[str] = mapped_column(String(100), default="Unknown")
    sex: Mapped[str] = mapped_column(String(10), default="female")
    age_months: Mapped[int] = mapped_column(Integer, default=0)
    lactating: Mapped[bool] = mapped_column(Boolean, default=False)
    is_monitored: Mapped[bool] = mapped_column(Boolean, default=False)
    data_source: Mapped[str] = mapped_column(String(50), default="SYNTHETIC_DEMO")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    health_records: Mapped[list["HealthRecord"]] = relationship(
        back_populates="animal", cascade="all, delete-orphan"
    )
    milk_records: Mapped[list["MilkRecord"]] = relationship(
        back_populates="animal", cascade="all, delete-orphan"
    )
    breeding_records: Mapped[list["BreedingRecord"]] = relationship(
        back_populates="animal", cascade="all, delete-orphan"
    )
    feeding_records: Mapped[list["FeedingRecord"]] = relationship(
        back_populates="animal", cascade="all, delete-orphan"
    )


class HealthRecord(Base):
    """A health check: temperature, symptoms, and severity."""

    __tablename__ = "health_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="none")  # none/mild/moderate/severe
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    animal: Mapped[Animal] = relationship(back_populates="health_records")


class MilkRecord(Base):
    """Milk yield for one animal on one day."""

    __tablename__ = "milk_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), index=True)
    recorded_on: Mapped[date] = mapped_column(Date)
    liters: Mapped[float] = mapped_column(Float)

    animal: Mapped[Animal] = relationship(back_populates="milk_records")


class BreedingRecord(Base):
    """Heat observations, insemination, and pregnancy checks."""

    __tablename__ = "breeding_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(30))  # heat_observed/insemination/pregnancy_check
    event_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    animal: Mapped[Animal] = relationship(back_populates="breeding_records")


class FeedingRecord(Base):
    """What an animal was fed and how much (used by the Nutrition Agent)."""

    __tablename__ = "feeding_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), index=True)
    feed_name: Mapped[str] = mapped_column(String(150))
    amount_kg: Mapped[float] = mapped_column(Float)
    recorded_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    animal: Mapped[Animal] = relationship(back_populates="feeding_records")


class FeedItem(Base):
    """A feed or supplement in the store (inventory)."""

    __tablename__ = "feed_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    category: Mapped[str] = mapped_column(String(50), default="concentrate")
    quantity_kg: Mapped[float] = mapped_column(Float, default=0.0)
    reorder_level_kg: Mapped[float] = mapped_column(Float, default=0.0)
    unit_cost_inr: Mapped[float] = mapped_column(Float, default=0.0)
    supplier: Mapped[str | None] = mapped_column(String(150), nullable=True)
    quality_grade: Mapped[str] = mapped_column(String(10), default="A")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class FarmMemory(Base):
    """Past farm incidents and their outcomes, used for retrieval."""

    __tablename__ = "farm_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), unique=True)
    category: Mapped[str] = mapped_column(String(50), default="general")
    summary: Mapped[str] = mapped_column(Text)
    keywords: Mapped[str] = mapped_column(String(300), default="")  # comma-separated
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProposedAction(Base):
    """An AI-proposed action waiting for the farmer's approval."""

    __tablename__ = "proposed_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_type: Mapped[str] = mapped_column(String(30))  # reorder_feed/book_vet/flag_animal
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), default="medium")  # high/medium/low
    parameters_json: Mapped[str] = mapped_column(Text, default="{}")
    # proposed / approved / rejected / completed / failed
    status: Mapped[str] = mapped_column(String(20), default="proposed", index=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ActionLog(Base):
    """Audit trail: every step taken on an action is recorded here."""

    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("proposed_actions.id"), index=True)
    event: Mapped[str] = mapped_column(String(50))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Order(Base):
    """A feed reorder placed after the farmer approved it."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_item_id: Mapped[int] = mapped_column(ForeignKey("feed_items.id"))
    quantity_kg: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="placed")
    action_id: Mapped[int | None] = mapped_column(ForeignKey("proposed_actions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class VetAppointment(Base):
    """A veterinary visit booked after the farmer approved it."""

    __tablename__ = "vet_appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    requested_for: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    action_id: Mapped[int | None] = mapped_column(ForeignKey("proposed_actions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PublicCow(Base):
    """A cow from a public research dataset. Kept out of the live herd on purpose."""

    __tablename__ = "public_cows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(50), default="PUBLIC_INRAE")
    breed: Mapped[str] = mapped_column(String(100), default="Unknown")
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    lactations: Mapped[list["PublicLactation"]] = relationship(
        back_populates="cow", cascade="all, delete-orphan"
    )


class PublicLactation(Base):
    """One lactation (birth-to-dry-off cycle) for a public-dataset cow."""

    __tablename__ = "public_lactations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cow_id: Mapped[int] = mapped_column(ForeignKey("public_cows.id"), index=True)
    lactation_number: Mapped[int] = mapped_column(Integer)
    lactation_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    calving_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    milk_305_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    milk_total_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_daily_milk_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    mastitis_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lameness_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gestation_days: Mapped[float | None] = mapped_column(Float, nullable=True)

    cow: Mapped[PublicCow] = relationship(back_populates="lactations")


class SymptomReport(Base):
    """A farmer's symptom report and the Health Agent's screening result."""

    __tablename__ = "symptom_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    input_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
