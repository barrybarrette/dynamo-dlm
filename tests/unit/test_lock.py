import unittest
from unittest.mock import patch, MagicMock, call

from boto3.dynamodb.conditions import Attr


# Constants
NOW = 12345678
UUID = "a_fake_uuid"


# Mock setup
class MockConditionalCheckFailedException(BaseException):
    pass


class MockClientError(BaseException):
    pass


table_mock = MagicMock()
dynamo_db_mock = MagicMock()
dynamo_db_mock.Table.return_value = table_mock
dynamo_db_mock.meta.client.exceptions.ConditionalCheckFailedException = (
    MockConditionalCheckFailedException
)
dynamo_db_mock.meta.client.exceptions.ClientError = MockClientError
boto_mock = MagicMock()
boto_mock.return_value = dynamo_db_mock
time_mock = MagicMock()
time_mock.return_value = NOW
uuid_mock = MagicMock()
uuid_mock.return_value.hex = UUID

# Patched import of main module to apply boto3 mocks
with patch("boto3.resource", boto_mock):
    import dynamo_dlm as dlm


@patch("uuid.uuid4", uuid_mock)
@patch("time.time", time_mock)
class TestDynamoDbLock(unittest.TestCase):

    def setUp(self):
        self.original_default_table_name = dlm.DEFAULT_TABLE_NAME
        dynamo_db_mock.Table.reset_mock()
        table_mock.put_item.reset_mock(side_effect=True)
        table_mock.delete_item.reset_mock(side_effect=True)
        self.resource_id = "test_id"

    def tearDown(self):
        dlm.DEFAULT_TABLE_NAME = self.original_default_table_name

    def test_uses_default_table_name_if_not_specified(self):
        _ = dlm.DynamoDbLock(self.resource_id)
        dynamo_db_mock.Table.assert_called_once_with(dlm.DEFAULT_TABLE_NAME)

    def test_can_overwrite_default_table_name(self):
        dlm.DEFAULT_TABLE_NAME = "my_custom_table"
        _ = dlm.DynamoDbLock(self.resource_id)
        dynamo_db_mock.Table.assert_called_once_with("my_custom_table")

    def test_can_specify_table_name_per_lock(self):
        _ = dlm.DynamoDbLock(self.resource_id, table_name="table1")
        _ = dlm.DynamoDbLock(self.resource_id, table_name="table2")
        dynamo_db_mock.Table.assert_any_call("table1")
        dynamo_db_mock.Table.assert_any_call("table2")

    def test_puts_item_when_lock_is_acquired(self):
        lock = dlm.DynamoDbLock(self.resource_id)
        lock.acquire()
        table_mock.put_item.assert_called_once_with(
            Item={
                "resource_id": f"{self.resource_id}",
                "concurrency_id": 0,
                "release_code": UUID,
                "expires": NOW + dlm.DEFAULT_DURATION,
            },
            ConditionExpression=Attr("resource_id").not_exists()
            | Attr("expires").lte(NOW),
        )

    def test_uses_specified_duration(self):
        lock = dlm.DynamoDbLock(self.resource_id, duration=20)
        lock.acquire()
        table_mock.put_item.assert_called_once_with(
            Item={
                "resource_id": f"{self.resource_id}",
                "concurrency_id": 0,
                "release_code": UUID,
                "expires": NOW + 20,
            },
            ConditionExpression=Attr("resource_id").not_exists()
            | Attr("expires").lte(NOW),
        )

    def test_keeps_trying_to_acquire_lock_if_unable(self):
        table_mock.put_item.side_effect = [
            MockConditionalCheckFailedException,
            MockConditionalCheckFailedException,
            "success",
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
            Key={"resource_id": f"{self.resource_id}", "concurrency_id": 0},
            ConditionExpression=Attr("release_code").eq(UUID),
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

    def test_lock_cannot_be_reacquired_unless_released(self):
        lock = dlm.DynamoDbLock(self.resource_id)
        lock.acquire()
        with self.assertRaises(dlm.LockNotAcquiredError):
            lock.acquire()
        lock.release()
        lock.acquire()

    def test_can_support_multiple_concurrent_locks(self):
        table_mock.put_item.side_effect = [
            "success",  # lock1 acquires id 0
            MockConditionalCheckFailedException,  # lock2 fails to acquire id 0
            "success",  # lock2 acquires id 1
            MockConditionalCheckFailedException,  # lock3 fails to acquire id 0
            MockConditionalCheckFailedException,  # lock3 fails to acquire id 1
            "success",  # lock3 acquires, implies lock1 released
        ]
        lock1 = dlm.DynamoDbLock(self.resource_id, concurrency=2)
        lock2 = dlm.DynamoDbLock(self.resource_id, concurrency=2)
        lock3 = dlm.DynamoDbLock(self.resource_id, concurrency=2)
        lock1.acquire()
        lock2.acquire()
        lock3.acquire()
        self.assertEqual(6, table_mock.put_item.call_count)
        table_mock.put_item.assert_has_calls(
            [
                call(  # lock1 acquires id 0
                    Item={
                        "resource_id": f"{self.resource_id}",
                        "concurrency_id": 0,
                        "release_code": UUID,
                        "expires": NOW + dlm.DEFAULT_DURATION,
                    },
                    ConditionExpression=Attr("resource_id").not_exists()
                    | Attr("expires").lte(NOW),
                ),
                call(  # lock2 fails to acquire id 0
                    Item={
                        "resource_id": f"{self.resource_id}",
                        "concurrency_id": 0,
                        "release_code": UUID,
                        "expires": NOW + dlm.DEFAULT_DURATION,
                    },
                    ConditionExpression=Attr("resource_id").not_exists()
                    | Attr("expires").lte(NOW),
                ),
                call(  # lock2 acquires id 1
                    Item={
                        "resource_id": f"{self.resource_id}",
                        "concurrency_id": 1,
                        "release_code": UUID,
                        "expires": NOW + dlm.DEFAULT_DURATION,
                    },
                    ConditionExpression=Attr("resource_id").not_exists()
                    | Attr("expires").lte(NOW),
                ),
                call(  # lock3 fails to acquire id 0
                    Item={
                        "resource_id": f"{self.resource_id}",
                        "concurrency_id": 0,
                        "release_code": UUID,
                        "expires": NOW + dlm.DEFAULT_DURATION,
                    },
                    ConditionExpression=Attr("resource_id").not_exists()
                    | Attr("expires").lte(NOW),
                ),
                call(  # lock3 fails to acquire id 1
                    Item={
                        "resource_id": f"{self.resource_id}",
                        "concurrency_id": 1,
                        "release_code": UUID,
                        "expires": NOW + dlm.DEFAULT_DURATION,
                    },
                    ConditionExpression=Attr("resource_id").not_exists()
                    | Attr("expires").lte(NOW),
                ),
                call(  # lock3 acquires, implies lock1 released
                    Item={
                        "resource_id": f"{self.resource_id}",
                        "concurrency_id": 0,
                        "release_code": UUID,
                        "expires": NOW + dlm.DEFAULT_DURATION,
                    },
                    ConditionExpression=Attr("resource_id").not_exists()
                    | Attr("expires").lte(NOW),
                ),
            ]
        )
