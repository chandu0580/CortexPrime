import faiss
import numpy as np
import os
import json


# ==========================================
# FILE PATHS
# ==========================================

INDEX_FILE = (
    "memory_architecture/vector_memory/vector_index.faiss"
)

METADATA_FILE = (
    "memory_architecture/vector_memory/vector_metadata.json"
)


# ==========================================
# EMBEDDING VECTOR DIMENSION
# ==========================================

VECTOR_DIMENSION = 1536


# ==========================================
# VECTOR STORE
# ==========================================

class VectorStore:

    def __init__(self):

        # ==========================================
        # LOAD / CREATE FAISS INDEX
        # ==========================================

        if os.path.exists(INDEX_FILE):

            self.index = faiss.read_index(
                INDEX_FILE
            )

        else:

            self.index = faiss.IndexFlatL2(
                VECTOR_DIMENSION
            )

        # ==========================================
        # LOAD / CREATE METADATA STORE
        # ==========================================

        if os.path.exists(METADATA_FILE):

            with open(
                METADATA_FILE,
                "r"
            ) as file:

                self.metadata = json.load(
                    file
                )

        else:

            self.metadata = []

    # ==========================================
    # ADD VECTOR
    # ==========================================

    def add_vector(
        self,
        embedding,
        memory_record
    ):

        if embedding is None:
            return

        vector = np.array(
            [embedding],
            dtype="float32"
        )

        self.index.add(vector)

        self.metadata.append(
            memory_record
        )

        self.save()

    # ==========================================
    # SEARCH VECTOR
    # ==========================================

    def search(
        self,
        embedding,
        top_k=3
    ):

        if embedding is None:
            return []

        if self.index.ntotal == 0:
            return []

        vector = np.array(
            [embedding],
            dtype="float32"
        )

        distances, indices = (
            self.index.search(
                vector,
                top_k
            )
        )

        results = []

        for idx in indices[0]:

            if idx < len(self.metadata):

                results.append(
                    self.metadata[idx]
                )

        return results

    # ==========================================
    # SAVE INDEX + METADATA
    # ==========================================

    def save(self):

        faiss.write_index(
            self.index,
            INDEX_FILE
        )

        with open(
            METADATA_FILE,
            "w"
        ) as file:

            json.dump(
                self.metadata,
                file,
                indent=4
            )