from pathlib import Path

from langchain_gigachat import GigaChatEmbeddings
from langchain_chroma import Chroma

from config import GIGA_AUTH


BASE_DIR = Path(__file__).resolve().parents[1]


def get_embeddings():
    return GigaChatEmbeddings(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )


def load_db():
    """Основная база с документами по ДТП"""
    return Chroma(
        persist_directory=str(BASE_DIR / "chroma_db"),
        embedding_function=get_embeddings(),
    )


def load_feedback_db():
    """База с хорошими Q&A из фидбека"""
    return Chroma(
        persist_directory=str(BASE_DIR / "chroma_feedback"),
        embedding_function=get_embeddings(),
    )
