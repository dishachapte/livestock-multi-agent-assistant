"""Request and response shapes for the API. Pydantic checks every request and response."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Lang = Literal["en", "hi", "kn"]
Color = Literal["green", "yellow", "red"]
ActionStatus = Literal["proposed", "approved", "rejected", "completed", "failed"]


class HealthResponse(BaseModel):
    status: str
    ai_mode: Literal["gemini", "demo"]
    gemini_key_configured: bool
    database: str
    server_time: datetime


class HealthIndicator(BaseModel):
    color: Color
    explanations: list[str]


class HerdAnimal(BaseModel):
    id: int
    tag_id: str
    name: str
    breed: str
    sex: str
    age_months: int
    lactating: bool
    is_monitored: bool
    data_source: str
    health_indicator: HealthIndicator


class HerdResponse(BaseModel):
    count: int
    green: int
    yellow: int
    red: int
    animals: list[HerdAnimal]


class HealthRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recorded_at: datetime
    temperature_c: float | None
    symptoms: str | None
    severity: str
    notes: str | None


class MilkRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recorded_on: date
    liters: float


class CowDetail(BaseModel):
    animal: HerdAnimal
    health_history: list[HealthRecordOut]
    milk_history: list[MilkRecordOut]


class Alert(BaseModel):
    level: Literal["high", "medium", "low"]
    category: str
    message: str


class BriefingResponse(BaseModel):
    language: Lang
    language_note: str | None
    translation_mode: Literal["gemini", "demo", "not_needed"]
    generated_at: datetime
    summary: str
    alerts: list[Alert]
    priorities: list[str]


# ---- Asking the Manager (Stage 3) ----------------------------------------

class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=3, max_length=500)
    language: Lang = "en"


class AgentFindingOut(BaseModel):
    agent: str
    status: Literal["ok", "attention", "critical"]
    summary: str
    findings: list[str]


class MemoryMatch(BaseModel):
    id: int
    title: str
    summary: str
    outcome: str | None
    matched_terms: list[str]
    score: int


class ProposedActionOut(BaseModel):
    id: int
    action_type: Literal["reorder_feed", "book_vet", "flag_animal"]
    description: str
    priority: Literal["high", "medium", "low"]
    parameters: dict
    status: ActionStatus
    result: dict | None
    created_at: datetime


class AskResponse(BaseModel):
    question: str
    language: Lang
    language_note: str | None
    ai_mode_used: Literal["gemini", "demo"]
    fallback_reason: str | None
    agents_consulted: list[str]
    final_recommendation: str
    agent_findings: list[AgentFindingOut]
    memory_matches: list[MemoryMatch]
    proposed_actions: list[ProposedActionOut]
    generated_at: datetime


# ---- Stage 4: inventory, memory, actions, orders, appointments -----------

class FeedItemOut(BaseModel):
    id: int
    name: str
    category: str
    quantity_kg: float
    reorder_level_kg: float
    unit_cost_inr: float
    supplier: str | None
    quality_grade: str
    low_stock: bool


class InventoryResponse(BaseModel):
    count: int
    low_stock_count: int
    low_stock_alerts: list[str]
    items: list[FeedItemOut]


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    summary: str
    keywords: str
    outcome: str | None
    created_at: datetime


class MemoryResponse(BaseModel):
    count: int
    incidents: list[MemoryOut]


class ActionListResponse(BaseModel):
    count: int
    actions: list[ProposedActionOut]


class RejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class ActionDecisionResponse(BaseModel):
    message: str
    action: ProposedActionOut


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feed_item_id: int
    quantity_kg: float
    status: str
    action_id: int | None
    created_at: datetime


class OrdersResponse(BaseModel):
    count: int
    orders: list[OrderOut]


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    animal_id: int | None
    reason: str
    requested_for: date
    status: str
    action_id: int | None
    created_at: datetime


class AppointmentsResponse(BaseModel):
    count: int
    appointments: list[AppointmentOut]


# ---- Stage 5: photo diagnosis ---------------------------------------------

class FileInfo(BaseModel):
    type: str
    size_kb: float


class PossibleCondition(BaseModel):
    name: str
    likelihood: Literal["low", "medium", "high"]


class DiagnosisResponse(BaseModel):
    ai_mode_used: Literal["gemini", "demo"]
    fallback_reason: str | None
    animal_tag: str | None
    file: FileInfo
    observations: list[str]
    possible_conditions: list[PossibleCondition]
    urgency: Literal["routine", "see_vet_soon", "urgent", "unknown"]
    next_steps: list[str]
    disclaimer: str


# ---- Public research benchmark (INRAE) -----------------------------------

class PublicLactationOut(BaseModel):
    lactation_number: int
    calving_date: date | None
    milk_305_kg: float | None
    milk_total_kg: float | None
    avg_daily_milk_kg: float | None
    mastitis_count: int | None
    lameness_count: int | None


class BenchmarkResponse(BaseModel):
    source: str
    cow_id: str
    breed: str
    lactation_count: int
    cow_avg_305_kg: float | None
    dataset_avg_305_kg: float | None
    percent_vs_dataset: float | None
    lactations: list[PublicLactationOut]
    note: str


# ---- Symptom screening (Health Agent) -------------------------------------

class CowReport(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    cow_id: str = Field(min_length=1, max_length=32)
    temperature_c: float | None = Field(default=None, ge=30, le=45)
    milk_before_l: float | None = Field(default=None, ge=0, le=100)
    milk_now_l: float | None = Field(default=None, ge=0, le=100)
    appetite: Literal["normal", "reduced", "none"] = "normal"
    udder: Literal["normal", "swollen", "hot_painful"] = "normal"
    milk_appearance: Literal["normal", "abnormal"] = "normal"
    days_since_calving: int | None = Field(default=None, ge=0, le=500)
    limping: bool = False
    foot_lesions: bool = False
    mouth_blisters: bool = False
    skin_nodules: bool = False
    cough_or_nasal_discharge: bool = False
    breathing_difficulty: bool = False
    bloated_left_side: bool = False
    unable_to_stand: bool = False
    trembling: bool = False
    notes: str | None = Field(default=None, max_length=300)


class AssessedCondition(BaseModel):
    name: str
    matched_signs: list[str]


class AssessmentResponse(BaseModel):
    report_id: int
    animal_label: str
    priority: Literal["urgent", "high", "medium", "low"]
    possible_conditions: list[AssessedCondition]
    concerns: list[str]
    urgent_reasons: list[str]
    recommended_next_steps: list[str]
    milk_drop_percent: float | None
    milk_production_anomaly: bool
    proposed_actions: list[ProposedActionOut]
    assessed_on: str
    disclaimer: str
