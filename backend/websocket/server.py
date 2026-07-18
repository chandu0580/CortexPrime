import logging

from fastapi import WebSocket

log = logging.getLogger(__name__)

# ==========================================
# WEBSOCKET MANAGER
# ==========================================

class WebSocketManager:

    def __init__(self):

        self.active_connections = []

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

        log.info(
            "WebSocket Client Connected."
        )

    # ==========================================
    # DISCONNECT
    # ==========================================

    def disconnect(
        self,
        websocket: WebSocket
    ):

        if websocket in (
            self.active_connections
        ):

            self.active_connections.remove(
                websocket
            )

        log.info(
            "WebSocket Client Disconnected."
        )

    # ==========================================
    # SEND MESSAGE
    # ==========================================

    async def send_message(

        self,

        websocket: WebSocket,

        message: dict
    ):

        await websocket.send_json(
            message
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

    def get_connection_count(
        self
    ):

        return len(
            self.active_connections
        )


# ==========================================
# GLOBAL WEBSOCKET MANAGER
# ==========================================

websocket_manager = (
    WebSocketManager()
)
