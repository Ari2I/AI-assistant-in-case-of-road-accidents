import os
from pathlib import Path
from dotenv import load_dotenv


load_dotenv(Path(__file__).parent / ".env")

GIGA_AUTH = os.getenv("GIGA_AUTH")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_B2B")