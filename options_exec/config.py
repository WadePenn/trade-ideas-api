from pydantic import BaseModel

class Settings(BaseModel):
    ib_host: str = "127.0.0.1"
    ib_port: int = 7497
    ib_client_id: int = 1

settings = Settings()
