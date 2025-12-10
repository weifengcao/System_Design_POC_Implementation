from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractRobustConnection, AbstractRobustChannel, AbstractIncomingMessage

from . import AsyncQueueBackend
from ..config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RabbitMQBackend(AsyncQueueBackend):
    """
    An asynchronous RabbitMQ backend using aio-pika that includes dead-letter queue handling.
    """

    def __init__(
        self,
        amqp_url: str,
        queue_name: str = "ocr_jobs",
        dead_letter_exchange_name: str = "ocr_jobs_dle",
        dead_letter_queue_name: str = "ocr_jobs_dlq",
    ):
        self.amqp_url = amqp_url
        self.queue_name = queue_name
        self.dead_letter_exchange_name = dead_letter_exchange_name
        self.dead_letter_queue_name = dead_letter_queue_name
        self.connection: Optional[AbstractRobustConnection] = None
        self.channel: Optional[AbstractRobustChannel] = None

    async def connect(self):
        """
        Establishes a robust connection and a channel, then declares the main
        and dead-letter exchanges and queues.
        """
        logger.info("Connecting to RabbitMQ...")
        try:
            self.connection = await aio_pika.connect_robust(self.amqp_url, timeout=10)
            self.channel = await self.connection.channel()

            # Declare the dead-letter exchange
            dead_letter_exchange = await self.channel.declare_exchange(
                self.dead_letter_exchange_name, ExchangeType.FANOUT
            )

            # Declare the dead-letter queue and bind it to the dead-letter exchange
            dead_letter_queue = await self.channel.declare_queue(
                self.dead_letter_queue_name, durable=True
            )
            await dead_letter_queue.bind(dead_letter_exchange)

            # Declare the main queue with dead-lettering configuration
            await self.channel.declare_queue(
                self.queue_name,
                durable=True,
                arguments={"x-dead-letter-exchange": self.dead_letter_exchange_name},
            )
            logger.info("RabbitMQ connection, exchanges, and queues are set up.")
        except asyncio.TimeoutError:
            logger.error("Connection to RabbitMQ timed out.")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def disconnect(self):
        """
        Gracefully closes the channel and the connection.
        """
        logger.info("Disconnecting from RabbitMQ...")
        if self.channel and not self.channel.is_closed:
            await self.channel.close()
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        logger.info("RabbitMQ connection closed.")

    async def enqueue(self, job_id: str) -> None:
        """
        Publishes a job ID to the main queue. The message is persistent.
        """
        if not self.channel:
            raise RuntimeError("RabbitMQ channel is not available. Did you call connect()?")

        message = aio_pika.Message(
            body=json.dumps({"job_id": job_id}).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self.channel.default_exchange.publish(message, routing_key=self.queue_name)

    async def pop(self) -> Optional[str]:
        """
        Consumes a job ID from the main queue. It acknowledges valid messages
        and rejects malformed ones, routing them to the dead-letter queue.
        """
        if not self.channel:
            raise RuntimeError("RabbitMQ channel is not available. Did you call connect()?")

        message: Optional[AbstractIncomingMessage] = await self.channel.get(self.queue_name, no_ack=False)
        if not message:
            return None

        try:
            data = json.loads(message.body)
            job_id = data.get("job_id")
            if not job_id:
                raise ValueError("Message is missing 'job_id'")
            await message.ack()
            return job_id
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Malformed message received: {e}. Rejecting and sending to DLQ.")
            await message.reject(requeue=False)
            return None