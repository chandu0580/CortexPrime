from memory_architecture.vector_memory.embedding_manager import (
    EmbeddingManager
)

from memory_architecture.vector_memory.vector_store import (
    VectorStore
)


# ==========================================
# SEMANTIC RETRIEVER
# ==========================================

class SemanticRetriever:

    def __init__(self):

        self.embedding_manager = (
            EmbeddingManager()
        )

        self.vector_store = (
            VectorStore()
        )

    # ==========================================
    # RETRIEVE SEMANTIC MEMORIES
    # ==========================================

    def retrieve(
        self,
        query: str,
        top_k: int = 3
    ):

        try:

            # ==========================================
            # GENERATE QUERY EMBEDDING
            # ==========================================

            embedding = (
                self.embedding_manager
                .generate_embedding(query)
            )

            if embedding is None:

                return []

            # ==========================================
            # SEARCH VECTOR STORE
            # ==========================================

            results = (
                self.vector_store.search(
                    embedding,
                    top_k=top_k
                )
            )

            return results

        except Exception as e:

            print(
                f"\n❌ Semantic retrieval failed: {str(e)}\n"
            )

            return []
        