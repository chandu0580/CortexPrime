import json
import os

from memory_architecture.vector_memory.embedding_manager import (
    EmbeddingManager
)

from memory_architecture.vector_memory.vector_store import (
    VectorStore
)

from memory_architecture.vector_memory.schemas import (
    VectorMemoryRecord
)


# ==========================================
# MEMORY FILE
# ==========================================

MEMORY_FILE = (
    "memory_architecture/short_term_memory/"
    "memory_store.json"
)


# ==========================================
# SHORT TERM MEMORY MANAGER
# ==========================================

class ShortTermMemoryManager:

    def __init__(self):

        self.embedding_manager = (
            EmbeddingManager()
        )

        self.vector_store = (
            VectorStore()
        )

    # ==========================================
    # LOAD MEMORY
    # ==========================================

    def load_memory(self):

        if not os.path.exists(
            MEMORY_FILE
        ):

            return []

        with open(
            MEMORY_FILE,
            "r"
        ) as file:

            return json.load(file)

    # ==========================================
    # SAVE MEMORY
    # ==========================================

    def save_memory(
        self,
        memory_data
    ):

        with open(
            MEMORY_FILE,
            "w"
        ) as file:

            json.dump(
                memory_data,
                file,
                indent=4
            )

    # ==========================================
    # STORE EXECUTION
    # ==========================================

    def store_execution(
        self,
        state
    ):

        memories = self.load_memory()

        # ==========================================
        # VECTOR MEMORY RECORD
        # ==========================================

        record = VectorMemoryRecord(
            session_id=state.session_id,
            created_at=state.created_at,
            user_goal=state.user_goal,
            final_output=state.final_output,
            workflow_status=state.workflow_status,
            final_confidence=state.final_confidence
        )

        # ==========================================
        # SAVE JSON MEMORY
        # ==========================================

        memories.append(
            record.model_dump()
        )

        self.save_memory(
            memories
        )

        # ==========================================
        # GENERATE SEMANTIC EMBEDDING
        # ==========================================

        combined_text = f"""
        USER GOAL:
        {state.user_goal}

        FINAL OUTPUT:
        {state.final_output}
        """

        embedding = (
            self.embedding_manager
            .generate_embedding(
                combined_text
            )
        )

        # ==========================================
        # STORE VECTOR MEMORY
        # ==========================================

        self.vector_store.add_vector(
            embedding,
            record.model_dump()
        )

        print(
            "\n🧠 Memory stored successfully.\n"
        )