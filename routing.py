from dataclasses import dataclass


@dataclass
class RoutingResult:

    modality: str

    scores: dict

    reason: str


KEYWORDS = {

    "Music Therapy": {

        "music": 4,
        "song": 3,
        "songs": 3,
        "sound": 2,
        "relax": 3,
        "relaxation": 3,
        "calm": 3,
        "stress": 2,
        "sleep": 2,
        "creative": 2,
        "emotional balance": 3,
        "mood": 2,

    },

    "Pranik Healing": {

        "energy": 4,
        "energetic": 4,
        "blocked energy": 5,
        "energy block": 5,
        "balance": 2,
        "healing": 2,
        "grounding": 3,
        "chakra": 4,

    },

    "Akashic Record Reading": {

        "life purpose": 5,
        "purpose": 3,
        "life direction": 4,
        "patterns": 3,
        "recurring": 2,
        "meaning": 3,
        "past": 1,
        "why does this keep happening": 4,
        "personal patterns": 4,

    },

    "Telepathic Communication": {

        "relationship": 2,
        "communication": 3,
        "connection": 3,
        "understanding another person": 5,
        "partner": 2,
        "family": 1,
        "someone i love": 2,

    }
}


def _build_text(
    intake
):

    parts = [

        intake.get(
            "primary_concern"
        ) or "",

        intake.get(
            "concern_details"
        ) or "",

        intake.get(
            "duration"
        ) or "",

        intake.get(
            "relevant_context"
        ) or "",

        intake.get(
            "preferred_modality"
        ) or "",

        intake.get(
            "additional_notes"
        ) or "",

        " ".join(
            intake.get(
                "impact",
                []
            ) or []
        ),

        " ".join(
            intake.get(
                "goals",
                []
            ) or []
        ),

        " ".join(
            intake.get(
                "previous_attempts",
                []
            ) or []
        ),

        " ".join(
            intake.get(
                "modality_interest",
                []
            ) or []
        )
    ]

    return " ".join(
        parts
    ).lower()


def route_intake(
    intake
):

    text = _build_text(
        intake
    )

    scores = {
        modality: 0
        for modality in KEYWORDS
    }

    for modality, keywords in KEYWORDS.items():

        for phrase, weight in keywords.items():

            if phrase in text:

                scores[modality] += weight

    preferred = (
        intake.get(
            "preferred_modality"
        )
        or ""
    ).lower()

    for modality in scores:

        if modality.lower() in preferred:

            scores[modality] += 5

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    best_modality, best_score = ranked[0]

    second_score = ranked[1][1]

    if best_score == 0:

        return RoutingResult(
            modality="Human practitioner review",
            scores=scores,
            reason=(
                "No sufficiently specific modality "
                "signals were found in the intake."
            )
        )

    if (
        best_score - second_score <= 1
    ):

        return RoutingResult(
            modality="Human practitioner review",
            scores=scores,
            reason=(
                "The intake contains overlapping or "
                "similarly strong signals. Human "
                "practitioner review is required."
            )
        )

    return RoutingResult(
        modality=best_modality,
        scores=scores,
        reason=(
            "Automated routing based on explicitly "
            "provided intake information. This is "
            "only an internal triage signal and "
            "requires human practitioner review."
        )
    )