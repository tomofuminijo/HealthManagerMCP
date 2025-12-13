"""
HealthPolicyLambda関数のユニットテスト（MCP形式対応）
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

from health_policy.handler import lambda_handler, add_policy, update_policy, delete_policy, get_policies


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
            TableName='healthmate-policies',
            KeySchema=[
                {
                    'AttributeName': 'userId',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'policyId',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'userId',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'policyId',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # 環境変数を設定
        os.environ['POLICIES_TABLE_NAME'] = 'healthmate-policies'
        
        yield table


class TestHealthPolicyLambdaHandler:
    """lambda_handler関数のテスト"""

    def test_add_policy_success(self, dynamodb_table):
        """addPolicy: 正常系"""
        event = {
            "userId": "user123",
            "policyType": "fasting",
            "title": "16時間ファスティング",
            "description": "毎日16時間のファスティングを実施",
            "rules": {
                "fastingHours": 16,
                "eatingWindow": "12:00-20:00"
            }
        }

        result = lambda_handler(event, None)

        assert result["success"] is True
        assert "policyId" in result
        assert result["policy"]["policyType"] == "fasting"
        assert result["policy"]["title"] == "16時間ファスティング"

    def test_add_policy_with_parameters_field(self, dynamodb_table):
        """parametersフィールドをrulesとして処理"""
        event = {
            "userId": "user123",
            "policyType": "diet",
            "description": "Low-carb diet policy",
            "parameters": {
                "carb": "low"
            }
        }

        result = lambda_handler(event, None)

        assert result["success"] is True
        assert result["policy"]["policyType"] == "diet"
        assert result["policy"]["title"] == "Diet Policy"  # デフォルト値
        assert result["policy"]["rules"]["carb"] == "low"

    def test_get_policies_success(self, dynamodb_table):
        """getPolicies: 正常系"""
        # まずポリシーを作成
        add_event = {
            "userId": "user123",
            "policyType": "fasting",
            "title": "16時間ファスティング"
        }
        lambda_handler(add_event, None)

        # 取得
        get_event = {
            "userId": "user123"
        }

        result = lambda_handler(get_event, None)

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["policies"]) == 1
        assert result["policies"][0]["policyType"] == "fasting"


class TestAddPolicy:
    """add_policy関数のテスト"""

    def test_add_policy_with_all_parameters(self, dynamodb_table):
        """すべてのパラメータを指定"""
        parameters = {
            "userId": "user123",
            "policyType": "fasting",
            "title": "16時間ファスティング",
            "description": "毎日16時間のファスティングを実施",
            "rules": {
                "fastingHours": 16,
                "eatingWindow": "12:00-20:00"
            },
            "startDate": "2025-01-01",
            "endDate": "2025-12-31"
        }

        result = add_policy(parameters)

        assert result["success"] is True
        assert "policyId" in result
        assert result["policy"]["policyType"] == "fasting"
        assert result["policy"]["title"] == "16時間ファスティング"
        assert result["policy"]["isActive"] == "true"

    def test_add_policy_with_parameters_field(self, dynamodb_table):
        """parametersフィールドをrulesとして処理"""
        parameters = {
            "userId": "user123",
            "policyType": "diet",
            "description": "Low-carb diet policy",
            "parameters": {
                "carb": "low"
            }
        }

        result = add_policy(parameters)

        assert result["success"] is True
        assert result["policy"]["rules"]["carb"] == "low"

    def test_add_policy_without_title(self, dynamodb_table):
        """titleなし: デフォルト値が設定される"""
        parameters = {
            "userId": "user123",
            "policyType": "diet"
        }

        result = add_policy(parameters)

        assert result["success"] is True
        assert result["policy"]["title"] == "Diet Policy"  # デフォルト値

    def test_add_policy_missing_user_id(self, dynamodb_table):
        """userIdが欠落: エラー"""
        parameters = {
            "policyType": "fasting",
            "title": "16時間ファスティング"
        }

        with pytest.raises(ValueError, match="userId is required"):
            add_policy(parameters)

    def test_add_policy_missing_policy_type(self, dynamodb_table):
        """policyTypeが欠落: エラー"""
        parameters = {
            "userId": "user123",
            "title": "16時間ファスティング"
        }

        with pytest.raises(ValueError, match="policyType is required"):
            add_policy(parameters)

    def test_add_policy_invalid_policy_type(self, dynamodb_table):
        """無効なpolicyType: エラー"""
        parameters = {
            "userId": "user123",
            "policyType": "invalid_type",
            "title": "テストポリシー"
        }

        with pytest.raises(ValueError, match="policyType must be one of"):
            add_policy(parameters)


class TestUpdatePolicy:
    """update_policy関数のテスト"""

    def test_update_policy_success(self, dynamodb_table):
        """ポリシー更新: 正常系"""
        # まずポリシーを作成
        add_result = add_policy({
            "userId": "user123",
            "policyType": "fasting",
            "title": "16時間ファスティング"
        })
        policy_id = add_result["policyId"]

        # 更新
        parameters = {
            "userId": "user123",
            "policyId": policy_id,
            "title": "更新されたタイトル",
            "isActive": False
        }

        result = update_policy(parameters)

        assert result["success"] is True
        assert result["policy"]["title"] == "更新されたタイトル"
        assert result["policy"]["isActive"] == "false"

    def test_update_nonexistent_policy(self, dynamodb_table):
        """存在しないポリシーを更新: エラー"""
        parameters = {
            "userId": "user123",
            "policyId": "nonexistent-policy-id",
            "title": "更新されたタイトル"
        }

        with pytest.raises(ValueError, match="Policy not found"):
            update_policy(parameters)


class TestDeletePolicy:
    """delete_policy関数のテスト"""

    def test_delete_policy_success(self, dynamodb_table):
        """ポリシー削除: 正常系"""
        # まずポリシーを作成
        add_result = add_policy({
            "userId": "user123",
            "policyType": "fasting",
            "title": "16時間ファスティング"
        })
        policy_id = add_result["policyId"]

        # 削除
        parameters = {
            "userId": "user123",
            "policyId": policy_id
        }

        result = delete_policy(parameters)

        assert result["success"] is True
        assert result["policyId"] == policy_id

    def test_delete_nonexistent_policy(self, dynamodb_table):
        """存在しないポリシーを削除: エラー"""
        parameters = {
            "userId": "user123",
            "policyId": "nonexistent-policy-id"
        }

        with pytest.raises(ValueError, match="Policy not found"):
            delete_policy(parameters)


class TestGetPolicies:
    """get_policies関数のテスト"""

    def test_get_policies_with_data(self, dynamodb_table):
        """ポリシーが存在する場合"""
        # 複数のポリシーを作成
        add_policy({
            "userId": "user123",
            "policyType": "fasting",
            "title": "ファスティングポリシー"
        })
        add_policy({
            "userId": "user123",
            "policyType": "diet",
            "title": "ダイエットポリシー"
        })

        parameters = {
            "userId": "user123"
        }

        result = get_policies(parameters)

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["policies"]) == 2

    def test_get_policies_empty(self, dynamodb_table):
        """ポリシーが存在しない場合"""
        parameters = {
            "userId": "user123"
        }

        result = get_policies(parameters)

        assert result["success"] is True
        assert result["count"] == 0
        assert len(result["policies"]) == 0

    def test_get_policies_missing_user_id(self, dynamodb_table):
        """userIdが欠落: エラー"""
        parameters = {}

        with pytest.raises(ValueError, match="userId is required"):
            get_policies(parameters)