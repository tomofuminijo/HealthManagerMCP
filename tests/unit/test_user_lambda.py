"""
UserLambda関数のユニットテスト（MCP形式対応）
"""

import json
import os
import pytest
from unittest.mock import Mock, patch
from moto import mock_aws
import boto3
from botocore.exceptions import ClientError

# Lambda関数をインポート
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from user.handler import lambda_handler, add_user, update_user, get_user


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-west-2'


@pytest.fixture
def dynamodb_table(aws_credentials):
    """DynamoDBテーブルのモック"""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        
        # テーブル作成
        table = dynamodb.create_table(
            TableName='healthmate-users',
            KeySchema=[
                {
                    'AttributeName': 'userId',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'userId',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # 環境変数を設定
        os.environ['USERS_TABLE_NAME'] = 'healthmate-users'
        
        yield table


class TestUserLambdaHandler:
    """lambda_handler関数のテスト"""

    def test_add_user_success(self, dynamodb_table):
        """addUser: 正常系"""
        event = {
            "userId": "user123",
            "username": "太郎",
            "email": "taro@example.com"
        }

        result = lambda_handler(event, None)

        assert result["success"] is True
        assert result["userId"] == "user123"
        assert "ユーザー情報をcreatedしました" in result["message"]

    def test_update_user_success(self, dynamodb_table):
        """updateUser: 正常系"""
        # まずユーザーを作成
        add_event = {
            "userId": "user123",
            "username": "太郎",
            "email": "taro@example.com"
        }
        lambda_handler(add_event, None)

        # 更新
        update_event = {
            "userId": "user123",
            "username": "太郎2"
        }

        result = lambda_handler(update_event, None)

        assert result["success"] is True
        assert result["userId"] == "user123"
        assert "ユーザー情報をupdatedしました" in result["message"]

    def test_get_user_success(self, dynamodb_table):
        """getUser: 正常系"""
        # まずユーザーを作成
        add_event = {
            "userId": "user123",
            "username": "太郎",
            "email": "taro@example.com"
        }
        lambda_handler(add_event, None)

        # 取得
        get_event = {
            "userId": "user123"
        }

        result = lambda_handler(get_event, None)

        assert result["success"] is True
        assert result["user"]["userId"] == "user123"
        assert result["user"]["username"] == "太郎"

    def test_missing_user_id(self, dynamodb_table):
        """userIdが欠落: エラー"""
        event = {
            "username": "太郎",
            "email": "taro@example.com"
        }

        result = lambda_handler(event, None)

        assert result["success"] is False
        assert result["errorType"] == "ValidationError"
        assert "userId is required" in result["error"]


class TestAddUser:
    """add_user関数のテスト"""

    def test_add_user_with_all_parameters(self, dynamodb_table):
        """すべてのパラメータを指定"""
        parameters = {
            "userId": "user123",
            "username": "太郎",
            "email": "taro@example.com"
        }

        result = add_user(parameters)

        assert result["success"] is True
        assert result["userId"] == "user123"
        assert result["user"]["username"] == "太郎"
        assert result["user"]["email"] == "taro@example.com"

    def test_add_user_missing_user_id(self, dynamodb_table):
        """userIdが欠落: エラー"""
        parameters = {
            "username": "太郎",
            "email": "taro@example.com"
        }

        with pytest.raises(ValueError, match="userId is required"):
            add_user(parameters)

    def test_add_user_missing_username(self, dynamodb_table):
        """usernameが欠落: エラー"""
        parameters = {
            "userId": "user123",
            "email": "taro@example.com"
        }

        with pytest.raises(ValueError, match="username is required"):
            add_user(parameters)

    def test_add_user_without_email(self, dynamodb_table):
        """emailなし: 正常系（emailはオプション）"""
        parameters = {
            "userId": "user123",
            "username": "太郎"
        }

        result = add_user(parameters)

        assert result["success"] is True
        assert result["userId"] == "user123"
        assert result["user"]["username"] == "太郎"
        assert result["user"]["email"] == ""


class TestUpdateUser:
    """update_user関数のテスト"""

    def test_update_user_username(self, dynamodb_table):
        """usernameを更新"""
        # まずユーザーを作成
        add_user({
            "userId": "user123",
            "username": "太郎",
            "email": "taro@example.com"
        })

        # 更新
        parameters = {
            "userId": "user123",
            "username": "新しい名前"
        }

        result = update_user(parameters)

        assert result["success"] is True
        assert result["userId"] == "user123"
        assert result["user"]["username"] == "新しい名前"

    def test_update_user_last_login(self, dynamodb_table):
        """lastLoginAtを更新"""
        # まずユーザーを作成
        add_user({
            "userId": "user123",
            "username": "太郎",
            "email": "taro@example.com"
        })

        # 更新
        parameters = {
            "userId": "user123",
            "lastLoginAt": "2024-12-07T10:00:00Z"
        }

        result = update_user(parameters)

        assert result["success"] is True
        assert result["userId"] == "user123"
        assert result["user"]["lastLoginAt"] == "2024-12-07T10:00:00Z"

    def test_update_user_missing_user_id(self, dynamodb_table):
        """userIdが欠落: エラー"""
        parameters = {
            "username": "新しい名前"
        }

        with pytest.raises(ValueError, match="userId is required"):
            update_user(parameters)

    def test_update_nonexistent_user(self, dynamodb_table):
        """存在しないユーザーを更新: エラー"""
        parameters = {
            "userId": "nonexistent",
            "username": "新しい名前"
        }

        with pytest.raises(ValueError, match="User not found"):
            update_user(parameters)


class TestGetUser:
    """get_user関数のテスト"""

    def test_get_existing_user(self, dynamodb_table):
        """存在するユーザーを取得"""
        # まずユーザーを作成
        add_user({
            "userId": "user123",
            "username": "太郎",
            "email": "taro@example.com"
        })

        # 取得
        parameters = {
            "userId": "user123"
        }

        result = get_user(parameters)

        assert result["success"] is True
        assert result["user"]["userId"] == "user123"
        assert result["user"]["username"] == "太郎"
        assert result["user"]["email"] == "taro@example.com"

    def test_get_nonexistent_user(self, dynamodb_table):
        """存在しないユーザーを取得: エラーレスポンス"""
        parameters = {
            "userId": "nonexistent"
        }

        result = get_user(parameters)
        
        assert result["success"] is False
        assert "ユーザーが見つかりません" in result["message"]

    def test_get_user_missing_user_id(self, dynamodb_table):
        """userIdが欠落: エラー"""
        parameters = {}

        with pytest.raises(ValueError, match="userId is required"):
            get_user(parameters)