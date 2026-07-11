import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class WorkerSettings(BaseSettings):
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    
    PAYMENTS_EXCHANGE_NAME: str = "payments_exchange"
    PAYMENTS_QUEUE_NAME: str = "payments_queue"
    PAYMENTS_ROUTING_KEY: str = "payment.process"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        extra="ignore"
    )

settings = WorkerSettings()
