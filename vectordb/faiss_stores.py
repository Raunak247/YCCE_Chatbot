import os
import numpy as np
from typing import List

from langchain_community.vectorstores import FAISS
from config import FAISS_PATH

try:
    from langchain.embeddings import HuggingFaceEmbeddings
except Exception:
    HuggingFaceEmbeddings = None


class SentenceTransformerWrapper:
    """Minimal wrapper providing `embed_documents` and `embed_query` using
    `sentence_transformers.SentenceTransformer` so FAISS can use it in place
    of LangChain's HuggingFaceEmbeddings.
    """
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            raise ImportError(
                "sentence-transformers is required for the fallback embeddings. "
                "Install it with `pip install sentence-transformers`"
            ) from e
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return embeddings.astype(np.float32).tolist()

    def embed_query(self, text: str) -> List[float]:
        embedding = self.model.encode([text], show_progress_bar=False, convert_to_numpy=True)[0]
        return embedding.astype(np.float32).tolist()

    def __call__(self, texts):
        """
        Provide a callable interface that mirrors older embedding_function expectations.
        Accepts a single string or a list of strings and returns embeddings.
        """
        # If a single string provided, return single embedding vector
        if isinstance(texts, str):
            return self.embed_query(texts)

        # Otherwise assume iterable of strings
        return self.embed_documents(list(texts))


if HuggingFaceEmbeddings is not None:
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
else:
    # Fallback to sentence-transformers directly to avoid hard dependency on
    # langchain-huggingface while still producing embeddings.
    embeddings = SentenceTransformerWrapper("sentence-transformers/all-MiniLM-L6-v2")


def upsert_documents(documents):
    """Upsert documents to FAISS index with corruption recovery."""
    try:
        if os.path.exists(FAISS_PATH):
            # Check if index files exist and are valid
            faiss_file = os.path.join(FAISS_PATH, "index.faiss")
            pkl_file = os.path.join(FAISS_PATH, "index.pkl")
            
            if os.path.exists(faiss_file) and os.path.exists(pkl_file):
                try:
                    db = FAISS.load_local(
                        FAISS_PATH,
                        embeddings,
                        allow_dangerous_deserialization=True
                    )
                    db.add_documents(documents)
                    db.save_local(FAISS_PATH)
                    return
                except Exception as load_err:
                    print(f"[WARN] FAISS index corrupted, recreating: {load_err}")
                    # Fall through to create new index
            else:
                print("[INFO] No existing FAISS index, creating new one")
        else:
            print("[INFO] No FAISS directory, creating new index")
        
        # Create new index
        db = FAISS.from_documents(documents, embeddings)
        db.save_local(FAISS_PATH)
        print("[OK] New FAISS index created")
        
    except Exception as e:
        print(f"[ERROR] Failed to upsert documents: {e}")
        # Last resort: try to create fresh index
        try:
            db = FAISS.from_documents(documents, embeddings)
            db.save_local(FAISS_PATH)
            print("[OK] Emergency FAISS index created")
        except Exception as e2:
            print(f"[ERROR] Emergency index creation failed: {e2}")
            raise
