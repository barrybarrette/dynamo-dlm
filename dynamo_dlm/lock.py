import logging
import time
import uuid

import backoff
import boto3
from boto3.dynamodb.conditions import Attr, Key

# Import own module to ensure we get user-defined custom table names defined there
import dynamo_dlm as dlm


# Adds default logging for backoff algorithm. Leaving this at the default log level of WARNING will log backoff events
logging.getLogger("backoff").addHandler(logging.StreamHandler())
_logger = logging.getLogger("dynamo_dlm")
_dynamo_db = boto3.resource("dynamodb")


class DynamoDbLock:

    def __init__(
        self,
        resource_id: str,
        duration: int = 10,
        table_name: str = None,
        concurrency: int = 1,
        wait_forever: bool = True,
    ):
        self._table = _dynamo_db.Table(table_name or dlm.DEFAULT_TABLE_NAME)
        self._resource_id = resource_id
        self._duration = duration or dlm.DEFAULT_DURATION
        self._release_code = None
        self._concurrency = concurrency
        self._concurrency_id = None
        self._wait_forever = wait_forever

    def __enter__(self):
        self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def acquire(self):
        if self._release_code:
            raise LockNotAcquiredError(
                "Cannot reacquire lock that hasn't been released yet"
            )
        self._release_code = uuid.uuid4().hex
        lock_confirmation = self._acquire_lock()
        if not lock_confirmation and not self._wait_forever:
            raise LockNotAcquiredError(
                "Failed to acquire immediately and wait_forever is false"
            )
        while lock_confirmation is None:
            lock_confirmation = self._acquire_lock()

    def release(self):
        if not self._release_code:
            raise LockNotAcquiredError("Cannot release a lock that was never acquired")
        self._release_lock()
        self._release_code = None

    def count(self):
        now = int(time.time())
        response = self._table.query(
            Select="COUNT",
            KeyConditionExpression=Key("resource_id").eq(self._resource_id),
            FilterExpression=Attr("expires").gte(now),
        )
        return response["Count"]

    def _acquire_lock(self):
        try:
            return self._put_lock_item()
        except _dynamo_db.meta.client.exceptions.ConditionalCheckFailedException:
            pass

    def _release_lock(self):
        try:
            self._delete_lock_item()
        except _dynamo_db.meta.client.exceptions.ConditionalCheckFailedException:
            _logger.warning(
                f"Warning: DynamoDbLock for resource {self._resource_id} attempted to release after "
                f"it was already acquired. This means the caller took too long to release "
                f"the lock, it expired, and was subsequently acquired by another caller."
            )

    @backoff.on_predicate(backoff.expo, jitter=backoff.full_jitter)
    def _put_lock_item(self):
        now = int(time.time())
        for self._concurrency_id in range(self._concurrency):
            try:
                return self._table.put_item(
                    Item={
                        "resource_id": self._resource_id,
                        "concurrency_id": self._concurrency_id,
                        "release_code": self._release_code,
                        "expires": now + self._duration,
                    },
                    ConditionExpression=Attr("resource_id").not_exists()
                    | Attr("expires").lte(now),
                )
            except (
                _dynamo_db.meta.client.exceptions.ConditionalCheckFailedException
            ) as e:
                if self._concurrency_id == self._concurrency - 1:
                    raise e
            except _dynamo_db.meta.client.exceptions.ClientError as e:
                if (
                    e.response["Error"]["Code"]
                    != "ProvisionedThroughputExceededException"
                ):
                    raise e

    @backoff.on_predicate(backoff.expo, jitter=backoff.full_jitter)
    def _delete_lock_item(self):
        try:
            return self._table.delete_item(
                Key={
                    "resource_id": self._resource_id,
                    "concurrency_id": self._concurrency_id,
                },
                ConditionExpression=Attr("release_code").eq(self._release_code),
            )
        except _dynamo_db.meta.client.exceptions.ClientError as error:
            if (
                error.response["Error"]["Code"]
                != "ProvisionedThroughputExceededException"
            ):
                raise error


class LockNotAcquiredError(RuntimeError):

    def __init__(self, msg: str):
        super().__init__()
        self.msg = msg

    def __str__(self):
        return f"LockNotAcquiredError: {self.msg}"

    def __repr__(self):
        return str(self)
