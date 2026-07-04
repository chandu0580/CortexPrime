from memory_architecture.short_term_memory.storage import (
    load_memory
)


class MemoryRetriever:

    def retrieve_relevant_memories(
        self,
        current_goal: str,
        limit: int = 3
    ):

        memories = load_memory()

        if not memories:
            return []

        # ==========================================
        # SIMPLE KEYWORD MATCHING
        # ==========================================

        scored_memories = []

        current_words = set(
            current_goal.lower().split()
        )

        for memory in memories:

            memory_goal = (
                memory.get(
                    "user_goal",
                    ""
                )
                .lower()
                .split()
            )

            memory_words = set(memory_goal)

            overlap = len(
                current_words.intersection(
                    memory_words
                )
            )

            scored_memories.append(
                (overlap, memory)
            )

        # ==========================================
        # SORT BY RELEVANCE
        # ==========================================

        scored_memories.sort(
            key=lambda x: x[0],
            reverse=True
        )

        relevant = [
            memory
            for score, memory in scored_memories
            if score > 0
        ]

        return relevant[:limit]