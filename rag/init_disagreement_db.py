from langchain_gigachat import GigaChatEmbeddings
from langchain_chroma import Chroma

from config import GIGA_AUTH


def load_disagreement_db():
    """База знаний по разногласиям при ДТП."""
    return Chroma(
        persist_directory="chroma_disagreement",
        embedding_function=_get_embeddings(),
    )


def _get_embeddings():
    return GigaChatEmbeddings(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )