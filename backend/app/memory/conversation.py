class ConversationMemory:

    def __init__(self):
        self.conversations = {}

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ):
        if session_id not in self.conversations:
            self.conversations[session_id] = []

        self.conversations[session_id].append({
            "role": role,
            "content": content
        })

    def get_messages(self, session_id: str):
        return self.conversations.get(session_id, [])

    def clear(self, session_id: str):
        self.conversations.pop(session_id, None)