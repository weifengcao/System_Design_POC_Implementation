from __future__ import annotations

import asyncio
import json
from typing import Optional

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractRobustConnection

from . import AsyncQueueBackend
from ..config import settings


class RabbitMQBackend(AsyncQueueBackend):
    """
    An asynchronous RabbitMQ backend that uses aio-pika.
    """

    def __init__(self, amqp_url: str, queue_name: str = "ocr_jobs"):
        self.amqp_url = amqp_url
        self.queue_name = queue_name
        self.connection: Optional[AbstractRobustConnection] = None
        self.channel: Optional[aio_pika.Channel] = None

    async def connect(self):
        """
        Establishes a connection and a channel, and declares the queue.
        """
        self.connection = await aio_pika.connect_robust(self.amqp_url)
        self.channel = await self.connection.channel()
        await self.channel.declare_queue(self.queue_name, durable=True)

    async def disconnect(self):
        """
        Closes the channel and the connection.
        """
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()

    async def enqueue(self, job_id: str) -> None:
        """
        Publishes a job ID to the specified queue.
        The message is persistent.
        """
        if not self.channel:
            await self.connect()

        message = aio_pika.Message(
            body=json.dumps({"job_id": job_id}).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self.channel.default_exchange.publish(message, routing_key=self.queue_name)

    async def pop(self) -> Optional[str]:
        """
        Consumes a job ID from the queue.
        It waits for a message and acknowledges it upon receipt.
        """
        if not self.channel:
            await self.connect()

        message = await self.channel.get(self.queue_name, no_ack=False)
        if not message:
            return None

        try:
            data = json.loads(message.body)
            job_id = data.get("job_id")
            await message.ack()
            return job_id
        except (json.JSONDecodeError, KeyError):
            # In case of a malformed message, reject it so it doesn't get re-queued
            await message.reject(requeue=False)
            return None

    @classmethod
    async def create(cls) -> "RabbitMQBackend":
        """
        Creates and connects a RabbitMQ backend instance.
        """
        backend = cls(amqp_url=settings.AMQP_URL)
        await backend.connect()
        return backend
