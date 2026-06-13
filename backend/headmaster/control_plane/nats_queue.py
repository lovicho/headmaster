"""NATS Queue Adapter.

Provides a distributed queue adapter using NATS JetStream, replacing the in-memory
FastAPI BackgroundTasks for production environments.
"""

import json
from typing import Callable, Awaitable, Any

import nats
from nats.aio.client import Client as NATS
from nats.js.client import JetStreamContext
from nats.js.api import StreamConfig

from headmaster.schemas.task_spec import TaskSpec


class NatsTaskQueue:
    """A distributed task queue powered by NATS JetStream."""

    def __init__(self, nats_url: str = "nats://localhost:4222", stream_name: str = "headmaster_tasks") -> None:
        self.nats_url = nats_url
        self.stream_name = stream_name
        self._nc: NATS | None = None
        self._js: JetStreamContext | None = None
        self._subject = f"{self.stream_name}.submit"

    async def connect(self) -> None:
        self._nc = await nats.connect(self.nats_url)
        self._js = self._nc.jetstream()
        
        # Ensure the stream exists
        try:
            await self._js.stream_info(self.stream_name)
        except Exception:
            # Create stream if not exists
            await self._js.add_stream(
                StreamConfig(
                    name=self.stream_name,
                    subjects=[f"{self.stream_name}.*"],
                )
            )

    async def enqueue(self, spec: TaskSpec, harness_id: str) -> None:
        if not self._js:
            raise RuntimeError("NATS client is not connected")
        
        payload = {
            "spec": spec.model_dump(mode="json"),
            "harness_id": harness_id,
        }
        await self._js.publish(self._subject, json.dumps(payload).encode("utf-8"))

    async def consume(self, handler: Callable[[TaskSpec, str], Awaitable[None]]) -> None:
        if not self._js:
            raise RuntimeError("NATS client is not connected")
        
        async def message_handler(msg: Any) -> None:
            try:
                data = json.loads(msg.data.decode("utf-8"))
                spec = TaskSpec(**data["spec"])
                harness_id = data["harness_id"]
                
                await handler(spec, harness_id)
                await msg.ack()
            except Exception as err:
                print(f"Error processing message: {err}")
                await msg.nak()

        # Subscribe to the stream as a durable consumer
        await self._js.subscribe(
            self._subject,
            durable="headmaster_worker",
            cb=message_handler,
            manual_ack=True
        )

    async def close(self) -> None:
        if self._nc and not self._nc.is_closed:
            await self._nc.close()
