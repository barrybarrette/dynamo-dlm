# dynamo-dlm
Distributed lock manager for Python using AWS DynamoDB for persistence

## Installation and usage

`pip install dynamo-dlm`

Locks are scoped to a logical resource, represented by a uniquely identifying string.
All instances of `DynamoDbLock` with the same table name and resource id will respect the lock rules

```python
from dynamo_dlm import DynamoDbLock

table_name = 'my_dynamo_db_lock_table'
resource_id = 'resource_identifier'
lock = DynamoDbLock(table_name, resource_id)
lock.acquire()
# Code executed here is protected by the lock
lock.release()
```

The lock class also implements the context manager interface:
```python
from dynamo_dlm import DynamoDbLock

table_name = 'my_dynamo_db_lock_table'
resource_id = 'resource_identifier'
with DynamoDbLock(table_name, resource_id):
    pass
    # Code executed inside the "with" block is protected by the lock
```

By default, locks last for 10 seconds if not released. This can be overridden in the constructor with an optional argument:
```python
from dynamo_dlm import DynamoDbLock

table_name = 'my_dynamo_db_lock_table'
resource_id = 'resource_identifier'
lock = DynamoDbLock(table_name, resource_id, duration=5)
```
