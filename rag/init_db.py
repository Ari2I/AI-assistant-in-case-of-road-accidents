from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

def load_db():
    """Основная база с документами по ДТП"""
    return Chroma(
        persist_directory="chroma_db",
        embedding_function=get_embeddings()
    )

def load_feedback_db():
    """База с хорошими Q&A из фидбека"""
    return Chroma(
        persist_directory="chroma_feedback",
        embedding_function=get_embeddings()
    )