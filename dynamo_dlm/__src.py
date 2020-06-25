import time
from uuid import uuid4

import boto3
from boto3.dynamodb.conditions import Attr


_dynamo_db =  boto3.resource('dynamodb')


class DynamoDbLock:

    def __init__(self, table_name: str, resource_id: str, duration: int=10):
        self._table = _dynamo_db.Table(table_name)
        self._resource_id = resource_id
        self._duration = duration
        self._release_code = None


    def __enter__(self):
        self.acquire()


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


    def acquire(self):
        self._release_code = uuid4().hex
        lock_confirmation = self._acquire_lock()
        while lock_confirmation is None:
            # TODO: Determine if waiting/backoff is a good idea
            lock_confirmation = self._acquire_lock()


    def release(self):
        if not self._release_code:
            raise RuntimeError('Cannot release a lock that was never acquired')
        try:
            self._table.delete_item(
                Key={'resource_id': self._resource_id},
                ConditionExpression=Attr('release_code').eq(self._release_code)
            )
        except _dynamo_db.meta.client.exceptions.ConditionalCheckFailedException:
            #TODO: Log warning as this indicates the lock expired; someone else has acquired a new lock on the resource
            pass


    def _acquire_lock(self):
        try:
            return self._put_lock_item()
        except _dynamo_db.meta.client.exceptions.ConditionalCheckFailedException:
            pass



    def _put_lock_item(self):
        now = int(time.time())
        return self._table.put_item(
            Item={
                'resource_id': self._resource_id,
                'release_code': self._release_code,
                'expires': now + self._duration
            },
            ConditionExpression=Attr('resource_id').not_exists() | Attr('expires').lte(now)
        )


if __name__ == '__main__':
    with DynamoDbLock('locks', 'mything', duration=10):
        print('doing long op')
        time.sleep(5)
        print('done')