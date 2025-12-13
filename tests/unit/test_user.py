"""
UserLambda関数のユニットテスト
"""

import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

# Lambda関数をインポート
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from user.handler import lambda_handler, add_user, update_user


@pytest.fixture
def mock_dynamodb_table():
    """DynamoDBテーブルのモック"""
    with patch("user.handler.table") as mock_table:
        yield mock_table


@pytest.fixture
def sample_event_add_user():
    """addUserイベントのサンプル"""
    return {
        "actionGroup": "UserManagement",
        "apiPath": "/addUser",
        "httpMethod": "POST",
        "parameters": [
            {"name": "userId", "value": "user123"},
            {"name": "username", "value": "太郎"},
            {"name": "email", "value": "taro@example.com"},
        ],
        "sessionAttributes": {},
    }


@pytest.fixture
def sample_event_update_user():
    """updateUserイベントのサンプル"""
    return {
        "actionGroup": "UserManagement",
        "apiPath": "/updateUser",
        "httpMethod": "POST",
        "parameters": [
            {"name": "userId", "value": "user123"},
            {"name": "username", "value": "太郎2"},
        ],
        "sessionAttributes": {},
    }


class TestLambdaHandler:
    """lambda_handler関数のテスト"""

    def test_add_user_success(self, mock_dynamodb_table, sample_event_add_user):
        """addUser: 正常系"""
        mock_dynamodb_table.put_item.return_value = {}

        result = lambda_handler(sample_event_add_user, None)

        assert result["response"]["actionGroup"] == "UserManagement"
        assert result["response"]["apiPath"] == "/addUser"
        assert result["response"]["httpStatusCode"] == 200
        response_body = json.loads(
            result["response"]["responseBody"]["application/json"]["body"]
        )
        assert response_body["success"] is True
        assert response_body["userId"] == "user123"

    def test_update_user_success(self, mock_dynamodb_table, sample_event_update_user):
        """updateUser: 正常系"""
        mock_dynamodb_table.update_item.return_value = {}

        result = lambda_handler(sample_event_update_user, None)

        assert result["response"]["httpStatusCode"] == 200
        response_body = json.loads(
            result["response"]["responseBody"]["application/json"]["body"]
        )
        assert response_body["success"] is True
        assert response_body["userId"] == "user123"

    def test_unknown_api_path(self, mock_dynamodb_table):
        """未知のAPIパス: エラー"""
        event = {
            "actionGroup": "UserManagement",
            "apiPath": "/unknownPath",
            "httpMethod": "POST",
            "parameters": [],
            "sessionAttributes": {},
        }

        result = lambda_handler(event, None)

        assert result["response"]["httpStatusCode"] == 500
        response_body = json.loads(
            result["response"]["responseBody"]["application/json"]["body"]
        )
        assert response_body["success"] is False
        assert "error" in response_body


class TestAddUser:
    """add_user関数のテスト"""

    def test_add_user_with_all_parameters(self, mock_dynamodb_table):
        """すべてのパラメータを指定"""
        mock_dynamodb_table.put_item.return_value = {}

        parameters = {
            "userId": "user123",
            "username": "太郎",
            "email": "taro@example.com",
        }

        result = add_user(parameters)

        assert result["success"] is True
        assert result["userId"] == "user123"
        mock_dynamodb_table.put_item.assert_called_once()

    def test_add_user_missing_user_id(self, mock_dynamodb_table):
        """userIdが欠落: エラー"""
        parameters = {"username": "太郎", "email": "taro@example.com"}

        with pytest.raises(
            ValueError, match="userId and username are required"
        ):
            add_user(parameters)

    def test_add_user_missing_username(self, mock_dynamodb_table):
        """usernameが欠落: エラー"""
        parameters = {"userId": "user123", "email": "taro@example.com"}

        with pytest.raises(
            ValueError, match="userId and username are required"
        ):
            add_user(parameters)

    def test_add_user_without_email(self, mock_dynamodb_table):
        """emailなし: 正常系（emailはオプション）"""
        mock_dynamodb_table.put_item.return_value = {}

        parameters = {"userId": "user123", "username": "太郎"}

        result = add_user(parameters)

        assert result["success"] is True
        assert result["userId"] == "user123"
        mock_dynamodb_table.put_item.assert_called_once()

    def test_add_user_already_exists(self, mock_dynamodb_table):
        """ユーザーが既に存在する場合"""
        # ConditionalCheckFailedExceptionをシミュレート
        error_response = {"Error": {"Code": "ConditionalCheckFailedException"}}
        mock_dynamodb_table.put_item.side_effect = ClientError(
            error_response, "PutItem"
        )

        parameters = {
            "userId": "user123",
            "username": "太郎",
            "email": "taro@example.com",
        }

        result = add_user(parameters)

        assert result["success"] is False
        assert "既に存在" in result["message"]


class TestUpdateUser:
    """update_user関数のテスト"""

    def test_update_user_username(self, mock_dynamodb_table):
        """usernameを更新"""
        mock_dynamodb_table.update_item.return_value = {}

        parameters = {"userId": "user123", "username": "新しい名前"}

        result = update_user(parameters)

        assert result["success"] is True
        assert result["userId"] == "user123"
        mock_dynamodb_table.update_item.assert_called_once()

    def test_update_user_last_login(self, mock_dynamodb_table):
        """lastLoginAtを更新"""
        mock_dynamodb_table.update_item.return_value = {}

        parameters = {
            "userId": "user123",
            "lastLoginAt": "2024-12-07T10:00:00Z",
        }

        result = update_user(parameters)

        assert result["success"] is True
        assert result["userId"] == "user123"
        mock_dynamodb_table.update_item.assert_called_once()

    def test_update_user_both_fields(self, mock_dynamodb_table):
        """usernameとlastLoginAtの両方を更新"""
        mock_dynamodb_table.update_item.return_value = {}

        parameters = {
            "userId": "user123",
            "username": "新しい名前",
            "lastLoginAt": "2024-12-07T10:00:00Z",
        }

        result = update_user(parameters)

        assert result["success"] is True
        mock_dynamodb_table.update_item.assert_called_once()

    def test_update_user_missing_user_id(self, mock_dynamodb_table):
        """userIdが欠落: エラー"""
        parameters = {"username": "新しい名前"}

        with pytest.raises(ValueError, match="userId is required"):
            update_user(parameters)

    def test_update_user_auto_last_login(self, mock_dynamodb_table):
        """lastLoginAtが指定されていない場合、自動的に現在時刻が設定される"""
        mock_dynamodb_table.update_item.return_value = {}

        parameters = {"userId": "user123", "username": "新しい名前"}

        result = update_user(parameters)

        assert result["success"] is True
        # lastLoginAtが自動的に設定されることを確認
        call_args = mock_dynamodb_table.update_item.call_args
        assert ":lastLoginAt" in call_args[1]["ExpressionAttributeValues"]
