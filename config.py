import os
from dotenv import load_dotenv

load_dotenv()

GIGA_AUTH = os.getenv("GIGA_AUTH")
SPEECH_AUTH = os.getenv("SPEECH_AUTH")