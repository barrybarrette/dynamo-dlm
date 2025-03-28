from dynamo_dlm.lock import DynamoDbLock, LockNotAcquiredError

DEFAULT_TABLE_NAME = "dynamo_dlm_locks"
DEFAULT_DURATION = 10

__all__ = [DynamoDbLock, LockNotAcquiredError, DEFAULT_TABLE_NAME, DEFAULT_DURATION]
