from dynamo_dlm.lock import DynamoDbLock, LockNotAcquiredError

DEFAULT_TABLE_NAME = 'dynamo_dlm_locks'
DEFAULT_DURATION = 10