import logging

from groq import Groq


from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
)


logger = logging.getLogger(
    "spandan.llm"
)


client = Groq(
    api_key=GROQ_API_KEY
)


SYSTEM_PROMPT = """
You are the intake assistant for Spandan,
a holistic wellness initiative.

Spandan connects people with human practitioners
who may offer:

1. Music Therapy
2. Pranik Healing
3. Akashic Record Reading
4. Telepathic Communication

YOUR ROLE

Your role is ONLY to understand the user's situation
and collect information for a human Spandan practitioner.

You are NOT:

- a doctor
- a psychologist
- a psychiatrist
- a therapist
- an emergency service
- a Spandan practitioner

Do not diagnose medical or psychological conditions.

Do not claim that any Spandan modality cures,
treats or prevents disease.

Do not present spiritual or paranormal claims
as scientifically established facts.

Do not promise outcomes.

CONVERSATION STYLE

Be warm, respectful and concise.

Ask ONE useful question at a time.

Do not repeatedly ask for information that the
user has already provided.

If the user gives several pieces of information,
acknowledge them and ask only for the most useful
missing information.

The intake should understand:

- what is troubling the person
- how long it has been happening
- how it affects their life
- what they want help with
- what they have already tried
- relevant context
- whether they have a modality preference

SAFETY

If the user indicates:

- suicidal intent
- self-harm
- immediate danger
- intention to harm another person
- severe medical emergency
- another urgent safety situation

stop normal intake.

Do not recommend a modality.

The application will handle the safety response.

COMPLETION

Do not tell the user that a particular modality
has been selected.

The application will determine when enough
information has been collected.

When the conversation is complete, the user will
be told that their information will be reviewed
by a human Spandan practitioner.
"""


def conversational_reply(
    history
):

    response = client.chat.completions.create(

        model=GROQ_MODEL,

        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            *history,
        ],

        temperature=0.25,

        max_tokens=350,

        reasoning_effort="low",
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    if not content:

        return (
            "Thank you for sharing that. "
            "Could you tell me a little more "
            "about what you would like help with?"
        )

    return content.strip()


EXTRACTION_SCHEMA = {

    "type": "object",

    "properties": {

        "name": {
            "type": [
                "string",
                "null"
            ]
        },

        "primary_concern": {
            "type": [
                "string",
                "null"
            ]
        },

        "concern_details": {
            "type": [
                "string",
                "null"
            ]
        },

        "duration": {
            "type": [
                "string",
                "null"
            ]
        },

        "impact": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },

        "goals": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },

        "previous_attempts": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },

        "relevant_context": {
            "type": [
                "string",
                "null"
            ]
        },

        "preferred_modality": {
            "type": [
                "string",
                "null"
            ]
        },

        "modality_interest": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },

        "emergency_flag": {
            "type": "boolean"
        },

        "additional_notes": {
            "type": [
                "string",
                "null"
            ]
        },
    },

    "required": [

        "name",
        "primary_concern",
        "concern_details",
        "duration",
        "impact",
        "goals",
        "previous_attempts",
        "relevant_context",
        "preferred_modality",
        "modality_interest",
        "emergency_flag",
        "additional_notes",
    ],

    "additionalProperties": False,
}


EXTRACTION_PROMPT = """
Extract information explicitly stated by the user.

Do NOT infer information.

Do NOT diagnose.

Do NOT recommend a modality.

Unknown fields should be null.

Unknown lists should be empty.

preferred_modality means only an explicit preference
stated by the user.

modality_interest means only modalities explicitly
mentioned by the user.

emergency_flag should only be true when the user
indicates immediate danger, self-harm, suicidal intent,
intent to harm another person, severe medical emergency,
or similarly urgent danger.

Return the structured fields exactly according
to the supplied JSON schema.
"""


def extract_intake(
    history
):

    response = client.chat.completions.create(

        model=GROQ_MODEL,

        messages=[

            {
                "role": "system",
                "content": EXTRACTION_PROMPT,
            },

            {
                "role": "user",
                "content": str(history),
            },
        ],

        temperature=0,

        max_tokens=500,

        reasoning_effort="low",

        response_format={
            "type": "json_schema",

            "json_schema": {

                "name": "spandan_intake",

                "strict": True,

                "schema": EXTRACTION_SCHEMA,
            }
        },
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    import json

    return json.loads(
        content
    )