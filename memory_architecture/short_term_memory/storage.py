import json
import os


MEMORY_FILE = "memory_architecture/short_term_memory/session_memory.json"


def load_memory():

    if not os.path.exists(MEMORY_FILE):

        return []

    with open(MEMORY_FILE, "r") as file:

        return json.load(file)


def save_memory(memory_records):

    with open(MEMORY_FILE, "w") as file:

        json.dump(
            memory_records,
            file,
            indent=4
        )