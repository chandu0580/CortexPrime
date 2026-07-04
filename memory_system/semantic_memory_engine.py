import os
import json
import faiss
import numpy as np

from dotenv import load_dotenv

from openai import AzureOpenAI


# ==========================================
# LOAD ENV
# ==========================================

load_dotenv()


# ==========================================
# AZURE OPENAI CLIENT
# ==========================================

client = AzureOpenAI(

    api_key=os.getenv(
        "AZURE_OPENAI_API_KEY"
    ),

    api_version=os.getenv(
        "AZURE_OPENAI_API_VERSION"
    ),

    azure_endpoint=os.getenv(
        "AZURE_OPENAI_ENDPOINT"
    )
)


# ==========================================
# SEMANTIC MEMORY ENGINE
# ==========================================

class SemanticMemoryEngine:

    def __init__(self):

        self.embedding_dimension = 3072

        self.index = faiss.IndexFlatL2(
            self.embedding_dimension
        )

        self.memory_store = []

        self.memory_file = (
            "semantic_memory.json"
        )

        self.load_memory()

    # ==========================================
    # GENERATE EMBEDDING
    # ==========================================

    def generate_embedding(
        self,
        text: str
    ):

        response = (
            client.embeddings.create(

                model=os.getenv(
                    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
                ),

                input=text
            )
        )

        embedding = (
            response.data[0].embedding
        )

        return np.array(
            embedding,
            dtype=np.float32
        )

    # ==========================================
    # STORE MEMORY
    # ==========================================

    def store_memory(

        self,

        memory_text: str,

        metadata: dict = None
    ):

        print(
            "\n🧠 Storing Semantic Memory...\n"
        )

        embedding = (
            self.generate_embedding(
                memory_text
            )
        )

        self.index.add(

            np.array(
                [embedding]
            )
        )

        memory_record = {

            "memory_text": memory_text,

            "metadata": metadata or {}
        }

        self.memory_store.append(
            memory_record
        )

        self.save_memory()

        print(
            "\n✅ Memory Stored.\n"
        )

    # ==========================================
    # SEARCH MEMORY
    # ==========================================

    def search_memory(

        self,

        query: str,

        top_k: int = 5
    ):

        print(
            "\n🔍 Searching Semantic Memory...\n"
        )

        if not self.memory_store:

            return []

        query_embedding = (
            self.generate_embedding(
                query
            )
        )

        distances, indices = (
            self.index.search(

                np.array(
                    [query_embedding]
                ),

                top_k
            )
        )

        retrieved_memories = []

        for idx in indices[0]:

            if idx < len(
                self.memory_store
            ):

                retrieved_memories.append(

                    self.memory_store[idx]
                )

        print(
            "\n✅ Memory Retrieval Complete.\n"
        )

        return retrieved_memories

    # ==========================================
    # SAVE MEMORY
    # ==========================================

    def save_memory(self):

        with open(

            self.memory_file,

            "w",

            encoding="utf-8"

        ) as file:

            json.dump(

                self.memory_store,

                file,

                indent=4,

                ensure_ascii=False
            )

    # ==========================================
    # LOAD MEMORY
    # ==========================================

    def load_memory(self):

        if not os.path.exists(
            self.memory_file
        ):

            return

        with open(

            self.memory_file,

            "r",

            encoding="utf-8"

        ) as file:

            self.memory_store = json.load(
                file
            )

        # ==========================================
        # REBUILD FAISS INDEX
        # ==========================================

        for memory in self.memory_store:

            embedding = (
                self.generate_embedding(

                    memory[
                        "memory_text"
                    ]
                )
            )

            self.index.add(

                np.array(
                    [embedding]
                )
            )

        print(
            "\n🧠 Semantic Memory Loaded.\n"
        )