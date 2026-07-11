from app.errors import CapabilityUnavailableError


class UnavailableBotTokenValidator:
    async def validate(self, token: str):
        del token
        raise CapabilityUnavailableError(
            "Telegram token validation adapter is not configured"
        )

