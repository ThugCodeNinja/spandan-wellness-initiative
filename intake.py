from pydantic import BaseModel
from typing import List, Optional


class Intake(BaseModel):

    name: Optional[str] = None

    primary_concern: Optional[str] = None

    concern_details: Optional[str] = None

    duration: Optional[str] = None

    impact: List[str] = []

    goals: List[str] = []

    previous_attempts: List[str] = []

    relevant_context: Optional[str] = None

    preferred_modality: Optional[str] = None

    modality_interest: List[str] = []

    emergency_flag: bool = False

    additional_notes: Optional[str] = None

    recommended_modality: Optional[str] = None

    recommendation_reason: Optional[str] = None