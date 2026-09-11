from pydantic import BaseModel


class TelegramChat(BaseModel):
    id: int


class TelegramMessage(BaseModel):
    chat: TelegramChat
    text: str | None = None
    caption: str | None = None


class TelegramUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None

    @property
    def user_text(self) -> str | None:
        """Texto procesable del update (solo mensajes de usuario)."""
        if self.message is None:
            return None

        text = self.message.text or self.message.caption

        if text is None or not text.strip():
            return None

        return text.strip()

    @property
    def chat_id(self) -> int | None:
        if self.message is None:
            return None

        return self.message.chat.id
