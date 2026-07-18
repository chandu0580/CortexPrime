
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

import chromadb

log = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except Exception:
    SentenceTransformer = None  # type: ignore
    _ST_AVAILABLE = False



# ==========================================
# VECTOR MEMORY
# ==========================================

class VectorMemory:

    def __init__(self):

        self.client          = None
        self.collection      = None
        self.embedding_model = None

        # ==========================================
        # CHROMA CLIENT
        # ==========================================

        try:
            self.client = chromadb.PersistentClient(
                path="./cortex_memory"
            )

            # ==========================================
            # COLLECTION
            # ==========================================

            self.collection = (

                self.client.get_or_create_collection(

                    name="cortexprime_memory"
                )
            )

        except BaseException as _chroma_err:
            log.warning(
                "ChromaDB unavailable — vector memory disabled: %s", _chroma_err
            )

        # ==========================================
        # EMBEDDING MODEL
        # ==========================================

        if _ST_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer(
                    "all-MiniLM-L6-v2"
                )
            except Exception as _st_err:
                log.warning(
                    "SentenceTransformer load failed: %s", _st_err
                )
        else:
            log.warning(
                "SentenceTransformer unavailable — vector memory embeddings disabled"
            )

        if self.client and self.embedding_model:
            log.info(
                "Vector memory initialized"
            )


    # ==========================================
    # CREATE EMBEDDING
    # ==========================================

    def create_embedding(

        self,

        text: str

    ) -> List[float]:

        if self.embedding_model is None:
            return []

        embedding = (

            self.embedding_model.encode(
                text
            )
        )

        return embedding.tolist()


    # ==========================================
    # STORE MEMORY
    # ==========================================

    def store_memory(

        self,

        objective: str,

        content: Dict[str, Any],

        metadata: Dict[str, Any] | None = None

    ) -> str:

        # ==========================================
        # MEMORY ID
        # ==========================================

        memory_id = str(
            uuid.uuid4()
        )

        # ==========================================
        # DOCUMENT
        # ==========================================

        document = f"""

        OBJECTIVE:
        {objective}

        CONTENT:
        {str(content)}

        """

        # ==========================================
        # EMBEDDING
        # ==========================================

        embedding = (

            self.create_embedding(
                document
            )
        )

        # ==========================================
        # METADATA
        # ==========================================

        memory_metadata = {

            "objective":
                objective,

            "timestamp":
                datetime.utcnow()
                .isoformat(),

            "memory_type":
                "execution_memory"
        }

        if metadata:

            memory_metadata.update(
                metadata
            )

        # ==========================================
        # STORE
        # ==========================================

        if self.collection is None or not embedding:
            return memory_id

        self.collection.add(

            ids=[memory_id],

            documents=[document],

            embeddings=[embedding],

            metadatas=[
                memory_metadata
            ]
        )

        log.info(
            "Memory stored: %s", memory_id
        )

        return memory_id


    # ==========================================
    # SEARCH MEMORIES
    # ==========================================

    def search_memories(

        self,

        query: str,

        limit: int = 5

    ) -> Dict[str, Any]:

        # ==========================================
        # EMBEDDING
        # ==========================================

        query_embedding = (

            self.create_embedding(
                query
            )
        )

        # ==========================================
        # SEARCH
        # ==========================================

        if self.collection is None or not query_embedding:
            return {"ids": [], "documents": [], "metadatas": [], "distances": []}

        results = self.collection.query(

            query_embeddings=[
                query_embedding
            ],

            n_results=limit
        )

        return results


    # ==========================================
    # GET MEMORY COUNT
    # ==========================================

    def get_memory_count(self) -> int:

        if self.collection is None:
            return 0
        return self.collection.count()


    # ==========================================
    # DELETE MEMORY
    # ==========================================

    def delete_memory(

        self,

        memory_id: str

    ):

        if self.collection is None:
            return

        self.collection.delete(

            ids=[memory_id]
        )

        log.info(
            "Deleted memory: %s", memory_id
        )


    # ==========================================
    # RESET MEMORY
    # ==========================================

    def reset_memory(self):

        if self.client is None:
            return

        self.client.delete_collection(
            "cortexprime_memory"
        )

        self.collection = (

            self.client.get_or_create_collection(

                name="cortexprime_memory"
            )
        )

        log.info(
            "Vector memory reset"
        )


# ==========================================
# SINGLETON
# ==========================================

vector_memory = VectorMemory()
