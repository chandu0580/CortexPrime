from fastapi import WebSocket

from typing import List


# ==========================================
# CONNECTION MANAGER
# ==========================================

class ConnectionManager:

    def __init__(self):

        self.active_connections: List[
            WebSocket
        ] = []


    # ==========================================
    # CONNECT
    # ==========================================

    async def connect(

        self,

        websocket: WebSocket

    ):

        await websocket.accept()

        self.active_connections.append(
            websocket
        )

        print(
            "🟢 WebSocket connected"
        )


    # ==========================================
    # DISCONNECT
    # ==========================================

    def disconnect(

        self,

        websocket: WebSocket

    ):

        if (

            websocket

            in self.active_connections
        ):

            self.active_connections.remove(
                websocket
            )

        print(
            "🔴 WebSocket disconnected"
        )


    # ==========================================
    # SEND TO SINGLE CLIENT
    # ==========================================

    async def send_personal_message(

        self,

        message: dict,

        websocket: WebSocket

    ):

        await websocket.send_json(
            message
        )


    # ==========================================
    # BACKWARD COMPATIBILITY
    # ==========================================

    async def send_message(

        self,

        websocket: WebSocket,

        message: dict

    ):

        await self.send_personal_message(

            message=message,

            websocket=websocket
        )


    # ==========================================
    # BROADCAST
    # ==========================================

    async def broadcast(

        self,

        message: dict

    ):

        disconnected_clients = []

        for connection in (

            self.active_connections
        ):

            try:

                await connection.send_json(
                    message
                )

            except Exception:

                disconnected_clients.append(
                    connection
                )

        # ==========================================
        # CLEANUP DEAD CONNECTIONS
        # ==========================================

        for connection in (
            disconnected_clients
        ):

            self.disconnect(
                connection
            )


    # ==========================================
    # CONNECTION COUNT
    # ==========================================

    def get_connection_count(self):

        return len(
            self.active_connections
        )


# ==========================================
# GLOBAL SINGLETON
# ==========================================

manager = ConnectionManager()


# ==========================================
# OPTIONAL LEGACY EXPORT
# ==========================================

connection_manager = manager