import sqlite3
import json
import os

from datetime import datetime


# ==========================================
# CHECKPOINT MANAGER
# ==========================================

class CheckpointManager:

    def __init__(self):

        self.database_path = (
            "cortexprime_checkpoints.db"
        )

        self.initialize_database()

    # ==========================================
    # INITIALIZE DATABASE
    # ==========================================

    def initialize_database(self):

        connection = sqlite3.connect(
            self.database_path
        )

        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                session_id TEXT,

                workflow_status TEXT,

                cognitive_state TEXT,

                created_at TEXT
            )
            """
        )

        connection.commit()

        connection.close()

    # ==========================================
    # SAVE CHECKPOINT
    # ==========================================

    def save_checkpoint(
        self,
        cognitive_state
    ):

        print(
            "\n💾 Saving Cognitive Checkpoint...\n"
        )

        connection = sqlite3.connect(
            self.database_path
        )

        cursor = connection.cursor()

        serialized_state = json.dumps(

            cognitive_state.model_dump(),

            default=str
        )

        cursor.execute(
            """
            INSERT INTO checkpoints (

                session_id,

                workflow_status,

                cognitive_state,

                created_at

            )

            VALUES (?, ?, ?, ?)
            """,

            (

                cognitive_state.session_id,

                cognitive_state.workflow_status,

                serialized_state,

                datetime.utcnow().isoformat()
            )
        )

        connection.commit()

        connection.close()

        print(
            "\n✅ Checkpoint Saved.\n"
        )

    # ==========================================
    # LOAD LATEST CHECKPOINT
    # ==========================================

    def load_latest_checkpoint(
        self,
        session_id: str
    ):

        print(
            "\n📂 Loading Latest Checkpoint...\n"
        )

        connection = sqlite3.connect(
            self.database_path
        )

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT cognitive_state

            FROM checkpoints

            WHERE session_id = ?

            ORDER BY id DESC

            LIMIT 1
            """,

            (session_id,)
        )

        result = cursor.fetchone()

        connection.close()

        if not result:

            print(
                "\n⚠️ No checkpoint found.\n"
            )

            return None

        restored_state = json.loads(
            result[0]
        )

        print(
            "\n✅ Checkpoint Restored.\n"
        )

        return restored_state

    # ==========================================
    # LIST CHECKPOINTS
    # ==========================================

    def list_checkpoints(self):

        connection = sqlite3.connect(
            self.database_path
        )

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT

                id,
                session_id,
                workflow_status,
                created_at

            FROM checkpoints

            ORDER BY id DESC
            """
        )

        checkpoints = cursor.fetchall()

        connection.close()

        return checkpoints

    # ==========================================
    # DELETE CHECKPOINTS
    # ==========================================

    def delete_checkpoints(
        self,
        session_id: str
    ):

        print(
            "\n🗑️ Deleting Checkpoints...\n"
        )

        connection = sqlite3.connect(
            self.database_path
        )

        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM checkpoints

            WHERE session_id = ?
            """,

            (session_id,)
        )

        connection.commit()

        connection.close()

        print(
            "\n✅ Checkpoints Deleted.\n"
        )