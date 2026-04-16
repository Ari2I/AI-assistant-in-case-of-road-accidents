from langchain_community.embeddings import GigaChatEmbeddings
from langchain_community.vectorstores import Chroma

from config import GIGA_AUTH


def get_embeddings():
    return GigaChatEmbeddings(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )


def load_db():
    """Основная база с документами по ДТП"""
    return Chroma(
        persist_directory="chroma_db",
        embedding_function=get_embeddings(),
    )


def load_feedback_db():
    """База с хорошими Q&A из фидбека"""
    return Chroma(
        persist_directory="chroma_feedback",
        embedding_function=get_embeddings(),
    )