"""
HealthPolicyLambda関数のユニットテスト
"""

import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Lambda関数をインポート
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from health_policy.handler import (
    lambda_handler,
    add_policy,
    update_policy,
    delete_policy,
    get_policy,
)


@pytest.fixture
def mock_dynamodb_table():
    """DynamoDBテーブルのモック"""
    with patch("health_policy.handler.table") as mock_table:
        yield mock_table


@pytest.fixture
def sample_event_add_policy():
    """addPolicyイベントのサンプル"""
    return {
        "actionGroup": "HealthPolicyManagement",
        "apiPath": "/addPolicy",
        "httpMethod": "POST",
        "parameters": [
            {"name": "userId", "value": "user123"},
            {"name": "policyType", "value": "diet"},
            {"name": "description", "value": "ローカーボ食"},
            {"name": "parameters", "value": {"carbs": "50g"}},
        ],
        "sessionAttributes": {},
    }


@pytest.fixture
def sample_event_get_policy():
    """getPolicyイベントのサンプル"""
    return {
        "actionGroup": "HealthPolicyManagement",
        "apiPath": "/getPolicy",
        "httpMethod": "POST",
        "parameters": [{"name": "userId", "value": "user123"}],
        "sessionAttributes": {},
    }


class TestLambdaHandler:
    """lambda_handler関数のテスト"""

    def test_add_policy_success(self, mock_dynamodb_table, sample_event_add_policy):
        """addPolicy: 正常系"""
        mock_dynamodb_table.put_item.return_value = {}

        result = lambda_handler(sample_event_add_policy, None)

        assert result["response"]["actionGroup"] == "HealthPolicyManagement"
        assert result["response"]["apiPath"] == "/addPolicy"
        assert result["response"]["httpStatusCode"] == 200
        response_body = json.loads(
            result["response"]["responseBody"]["application/json"]["body"]
        )
        assert response_body["success"] is True
        assert "policyId" in response_body

    def test_get_policy_success(self, mock_dynamodb_table, sample_event_get_policy):
        """getPolicy: 正常系"""
        mock_dynamodb_table.query.return_value = {
            "Items": [
                {
                    "userId": "user123",
                    "policyId": "policy1",
                    "policyType": "diet",
                    "details": {"description": "ローカーボ食"},
                }
            ]
        }

        result = lambda_handler(sample_event_get_policy, None)

        assert result["response"]["httpStatusCode"] == 200
        response_body = json.loads(
            result["response"]["responseBody"]["application/json"]["body"]
        )
        assert response_body["success"] is True
        assert response_body["count"] == 1
        assert len(response_body["policies"]) == 1

    def test_unknown_api_path(self, mock_dynamodb_table):
        """未知のAPIパス: エラー"""
        event = {
            "actionGroup": "HealthPolicyManagement",
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


class TestAddPolicy:
    """add_policy関数のテスト"""

    def test_add_policy_with_all_parameters(self, mock_dynamodb_table):
        """すべてのパラメータを指定"""
        mock_dynamodb_table.put_item.return_value = {}

        parameters = {
            "userId": "user123",
            "policyType": "diet",
            "description": "ローカーボ食",
            "parameters": {"carbs": "50g"},
        }

        result = add_policy(parameters)

        assert result["success"] is True
        assert "policyId" in result
        mock_dynamodb_table.put_item.assert_called_once()

    def test_add_policy_missing_user_id(self, mock_dynamodb_table):
        """userIdが欠落: エラー"""
        parameters = {"policyType": "diet"}

        with pytest.raises(ValueError, match="userId and policyType are required"):
            add_policy(parameters)

    def test_add_policy_missing_policy_type(self, mock_dynamodb_table):
        """policyTypeが欠落: エラー"""
        parameters = {"userId": "user123"}

        with pytest.raises(ValueError, match="userId and policyType are required"):
            add_policy(parameters)


class TestUpdatePolicy:
    """update_policy関数のテスト"""

    def test_update_policy_description(self, mock_dynamodb_table):
        """descriptionを更新"""
        mock_dynamodb_table.update_item.return_value = {}

        parameters = {
            "userId": "user123",
            "policyId": "policy1",
            "description": "新しい説明",
        }

        result = update_policy(parameters)

        assert result["success"] is True
        assert result["policyId"] == "policy1"
        mock_dynamodb_table.update_item.assert_called_once()

    def test_update_policy_missing_policy_id(self, mock_dynamodb_table):
        """policyIdが欠落: エラー"""
        parameters = {"userId": "user123"}

        with pytest.raises(ValueError, match="userId and policyId are required"):
            update_policy(parameters)


class TestDeletePolicy:
    """delete_policy関数のテスト"""

    def test_delete_policy_success(self, mock_dynamodb_table):
        """正常系"""
        mock_dynamodb_table.delete_item.return_value = {}

        parameters = {"userId": "user123", "policyId": "policy1"}

        result = delete_policy(parameters)

        assert result["success"] is True
        assert result["policyId"] == "policy1"
        mock_dynamodb_table.delete_item.assert_called_once()

    def test_delete_policy_missing_parameters(self, mock_dynamodb_table):
        """パラメータが欠落: エラー"""
        parameters = {"userId": "user123"}

        with pytest.raises(ValueError, match="userId and policyId are required"):
            delete_policy(parameters)


class TestGetPolicy:
    """get_policy関数のテスト"""

    def test_get_policy_with_results(self, mock_dynamodb_table):
        """ポリシーが存在する場合"""
        mock_dynamodb_table.query.return_value = {
            "Items": [
                {"userId": "user123", "policyId": "policy1", "policyType": "diet"},
                {"userId": "user123", "policyId": "policy2", "policyType": "exercise"},
            ]
        }

        parameters = {"userId": "user123"}

        result = get_policy(parameters)

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["policies"]) == 2

    def test_get_policy_no_results(self, mock_dynamodb_table):
        """ポリシーが存在しない場合"""
        mock_dynamodb_table.query.return_value = {"Items": []}

        parameters = {"userId": "user123"}

        result = get_policy(parameters)

        assert result["success"] is True
        assert result["count"] == 0
        assert len(result["policies"]) == 0

    def test_get_policy_missing_user_id(self, mock_dynamodb_table):
        """userIdが欠落: エラー"""
        parameters = {}

        with pytest.raises(ValueError, match="userId is required"):
            get_policy(parameters)
