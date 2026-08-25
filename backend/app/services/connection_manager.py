"""
Tracks active WebSocket connections, keyed by user_id, so
notifications and chat messages can be pushed live to a user if
they're currently online.

LIMITATION, worth disclosing in Chapter 5: this is a single-process,
in-memory connection registry. It works correctly for one running
instance of the backend (which is all this project runs, and all a
final-year project demo needs), but would NOT work correctly if the
app were ever horizontally scaled across multiple server processes/
machines — a user connected to server A would never receive a push
triggered by an action handled on server B. A production version would
need a shared layer (e.g. Redis pub/sub) for this to work across
multiple instances. Out of scope here; noted rather than hidden.
"""
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)

    async def send_personal_message(self, user_id: str, payload: dict) -> bool:
        """Returns True if the user was online and the message was
        sent, False if they weren't connected (caller doesn't need to
        treat that as an error — the notification is already persisted
        to the database regardless)."""
        websocket = self.active_connections.get(user_id)
        if websocket is None:
            return False
        try:
            await websocket.send_json(payload)
            return True
        except Exception:
            # Connection is dead but wasn't cleanly closed — drop it
            # so future sends don't keep failing against a stale socket.
            self.disconnect(user_id)
            return False

    def is_online(self, user_id: str) -> bool:
        return user_id in self.active_connections


# Single shared instance for the whole app process.
manager = ConnectionManager()
