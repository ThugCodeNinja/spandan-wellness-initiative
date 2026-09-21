from typing import List, Optional

from pydantic import BaseModel, Field


class Intake(BaseModel):

    name: Optional[str] = None

    primary_concern: Optional[str] = None

    concern_details: Optional[str] = None

    duration: Optional[str] = None

    impact: List[str] = Field(
        default_factory=list
    )

    goals: List[str] = Field(
        default_factory=list
    )

    previous_attempts: List[str] = Field(
        default_factory=list
    )

    relevant_context: Optional[str] = None

    preferred_modality: Optional[str] = None

    modality_interest: List[str] = Field(
        default_factory=list
    )

    emergency_flag: bool = False

    additional_notes: Optional[str] = None


LIST_FIELDS = {
    "impact",
    "goals",
    "previous_attempts",
    "modality_interest",
}


def merge_intake(
    existing: dict,
    extracted: dict
) -> dict:

    result = dict(existing)

    for key, value in extracted.items():

        if value is None:
            continue

        if key in LIST_FIELDS:

            old_values = list(
                result.get(
                    key,
                    []
                ) or []
            )

            new_values = value or []

            for item in new_values:

                if item not in old_values:

                    old_values.append(item)

            result[key] = old_values

        elif key == "emergency_flag":

            result[key] = (
                bool(
                    result.get(
                        key,
                        False
                    )
                )
                or bool(value)
            )

        else:

            result[key] = value

    return result