import unittest
from unittest.mock import patch, MagicMock

from boto3.dynamodb.conditions import Attr


# Constants
NOW = 12345678
UUID = 'a_fake_uuid'

# Mock setup
class MockConditionalCheckFailedException(BaseException):
    pass
class MockClientError(BaseException):
    pass
table_mock = MagicMock()
dynamo_db_mock = MagicMock()
dynamo_db_mock.Table.return_value = table_mock
dynamo_db_mock.meta.client.exceptions.ConditionalCheckFailedException = MockConditionalCheckFailedException
dynamo_db_mock.meta.client.exceptions.ClientError = MockClientError
boto_mock = MagicMock()
boto_mock.return_value = dynamo_db_mock
time_mock = MagicMock()
time_mock.return_value = NOW
uuid_mock = MagicMock()
uuid_mock.return_value.hex = UUID

# Patched import of main module to apply boto3 mocks
with patch('boto3.resource', boto_mock):
    import dynamo_dlm as dlm


@patch('uuid.uuid4', uuid_mock)
@patch('time.time', time_mock)
class TestDynamoDbLock(unittest.TestCase):

    def setUp(self):
        self.original_default_table_name = dlm.DEFAULT_TABLE_NAME
        dynamo_db_mock.Table.reset_mock()
        table_mock.put_item.reset_mock(side_effect=True)
        table_mock.delete_item.reset_mock(side_effect=True)
        self.resource_id = 'test_id'


    def tearDown(self):
        dlm.DEFAULT_TABLE_NAME = self.original_default_table_name


    def test_uses_default_table_name_if_not_specified(self):
        lock = dlm.DynamoDbLock(self.resource_id)
        dynamo_db_mock.Table.assert_called_once_with(dlm.DEFAULT_TABLE_NAME)


    def test_can_overwrite_default_table_name(self):
        dlm.DEFAULT_TABLE_NAME = 'my_custom_table'
        lock = dlm.DynamoDbLock(self.resource_id)
        dynamo_db_mock.Table.assert_called_once_with('my_custom_table')


    def test_can_specify_table_name_per_lock(self):
        lock1 = dlm.DynamoDbLock(self.resource_id, table_name='table1')
        lock2 = dlm.DynamoDbLock(self.resource_id, table_name='table2')
        dynamo_db_mock.Table.assert_any_call('table1')
        dynamo_db_mock.Table.assert_any_call('table2')


    def test_puts_item_when_lock_is_acquired(self):
        lock = dlm.DynamoDbLock(self.resource_id)
        lock.acquire()
        table_mock.put_item.assert_called_once_with(
            Item={
                'resource_id': self.resource_id,
                'release_code': UUID,
                'expires': NOW + dlm.DEFAULT_DURATION
            },
            ConditionExpression=Attr('resource_id').not_exists() | Attr('expires').lte(NOW)
        )


    def test_uses_specified_duration(self):
        lock = dlm.DynamoDbLock(self.resource_id, duration=20)
        lock.acquire()
        table_mock.put_item.assert_called_once_with(
            Item={
                'resource_id': self.resource_id,
                'release_code': UUID,
                'expires': NOW + 20
            },
            ConditionExpression=Attr('resource_id').not_exists() | Attr('expires').lte(NOW)
        )


    def test_keeps_trying_to_acquire_lock_if_unable(self):
        table_mock.put_item.side_effect = [
            MockConditionalCheckFailedException,
            MockConditionalCheckFailedException,
            'success'
        ]
        lock = dlm.DynamoDbLock(self.resource_id)
        lock.acquire()
        self.assertEqual(table_mock.put_item.call_count, 3)


    def test_releasing_lock_that_has_not_been_acquired_raises_error(self):
        lock = dlm.DynamoDbLock(self.resource_id)
        with self.assertRaises(dlm.LockNotAcquiredError):
            lock.release()


    def test_releasing_lock_deletes_item_from_table(self):
        lock = dlm.DynamoDbLock(self.resource_id)
        lock.acquire()
        lock.release()
        table_mock.delete_item.assert_called_once_with(
            Key={'resource_id': self.resource_id},
            ConditionExpression=Attr('release_code').eq(UUID)
        )


    def test_releasing_lock_that_has_already_been_reacquired_is_idempotent(self):
        table_mock.delete_item.side_effect = MockConditionalCheckFailedException
        lock = dlm.DynamoDbLock(self.resource_id)
        lock.acquire()
        # implied timeout - someone else has acquired a new lock on the resource
        lock.release()


    def test_implements_context_manager_correctly(self):
        with dlm.DynamoDbLock(self.resource_id):
            table_mock.put_item.assert_called_once()
            table_mock.delete_item.assert_not_called()
        table_mock.delete_item.assert_called_once()
