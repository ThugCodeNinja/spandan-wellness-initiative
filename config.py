import os

from dotenv import load_dotenv


load_dotenv()


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "")

EMERGENCY_MESSAGE = os.getenv(
    "EMERGENCY_MESSAGE",
    (
        "If you are in immediate danger or may hurt yourself "
        "or someone else, please contact your local emergency "
        "service or a qualified crisis or mental-health "
        "professional immediately."
    )
)


def validate_config():

    required = {
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "GROQ_API_KEY": GROQ_API_KEY,
        "ADMIN_TELEGRAM_ID": ADMIN_TELEGRAM_ID
    }

    missing = [
        key
        for key, value in required.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )