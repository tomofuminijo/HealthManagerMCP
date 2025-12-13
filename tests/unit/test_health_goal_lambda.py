"""
HealthGoalLambda関数のユニットテスト（MCP形式対応）
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

from health_goal.handler import lambda_handler, add_goal, update_goal, delete_goal, get_goals


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
            TableName='healthmate-goals',
            KeySchema=[
                {
                    'AttributeName': 'userId',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'goalId',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'userId',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'goalId',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # 環境変数を設定
        os.environ['GOALS_TABLE_NAME'] = 'healthmate-goals'
        
        yield table


class TestHealthGoalLambdaHandler:
    """lambda_handler関数のテスト"""

    def test_add_goal_success(self, dynamodb_table):
        """addGoal: 正常系"""
        event = {
            "userId": "user123",
            "goalType": "fitness",
            "title": "アスリート体型になる",
            "description": "体脂肪率を15%以下にして筋肉量を増やす",
            "targetValue": "体脂肪率15%",
            "priority": 1
        }

        result = lambda_handler(event, None)

        assert result["success"] is True
        assert "goalId" in result
        assert result["goal"]["goalType"] == "fitness"
        assert result["goal"]["title"] == "アスリート体型になる"

    def test_get_goals_success(self, dynamodb_table):
        """getGoals: 正常系"""
        # まず目標を作成
        add_event = {
            "userId": "user123",
            "goalType": "fitness",
            "title": "アスリート体型になる"
        }
        add_result = lambda_handler(add_event, None)

        # 取得
        get_event = {
            "userId": "user123"
        }

        result = lambda_handler(get_event, None)

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["goals"]) == 1
        assert result["goals"][0]["goalType"] == "fitness"

    def test_missing_user_id(self, dynamodb_table):
        """userIdが欠落: エラー"""
        event = {
            "goalType": "fitness",
            "title": "アスリート体型になる"
        }

        result = lambda_handler(event, None)

        assert result["success"] is False
        assert result["errorType"] == "ValidationError"
        assert "userId is required" in result["error"]


class TestAddGoal:
    """add_goal関数のテスト"""

    def test_add_goal_with_all_parameters(self, dynamodb_table):
        """すべてのパラメータを指定"""
        parameters = {
            "userId": "user123",
            "goalType": "fitness",
            "title": "アスリート体型になる",
            "description": "体脂肪率を15%以下にして筋肉量を増やす",
            "targetValue": "体脂肪率15%",
            "targetDate": "2025-12-31",
            "priority": 1
        }

        result = add_goal(parameters)

        assert result["success"] is True
        assert "goalId" in result
        assert result["goal"]["goalType"] == "fitness"
        assert result["goal"]["title"] == "アスリート体型になる"
        assert result["goal"]["priority"] == 1
        assert result["goal"]["status"] == "active"

    def test_add_goal_missing_user_id(self, dynamodb_table):
        """userIdが欠落: エラー"""
        parameters = {
            "goalType": "fitness",
            "title": "アスリート体型になる"
        }

        with pytest.raises(ValueError, match="userId is required"):
            add_goal(parameters)

    def test_add_goal_missing_goal_type(self, dynamodb_table):
        """goalTypeが欠落: エラー"""
        parameters = {
            "userId": "user123",
            "title": "アスリート体型になる"
        }

        with pytest.raises(ValueError, match="goalType is required"):
            add_goal(parameters)

    def test_add_goal_without_title(self, dynamodb_table):
        """titleなし: デフォルト値が設定される"""
        parameters = {
            "userId": "user123",
            "goalType": "fitness"
        }

        result = add_goal(parameters)

        assert result["success"] is True
        assert result["goal"]["title"] == "Fitness Goal"  # デフォルト値

    def test_add_goal_invalid_goal_type(self, dynamodb_table):
        """無効なgoalType: エラー"""
        parameters = {
            "userId": "user123",
            "goalType": "invalid_type",
            "title": "テスト目標"
        }

        with pytest.raises(ValueError, match="goalType must be one of"):
            add_goal(parameters)

    def test_add_goal_invalid_priority(self, dynamodb_table):
        """無効なpriority: エラー"""
        parameters = {
            "userId": "user123",
            "goalType": "fitness",
            "title": "テスト目標",
            "priority": 10  # 1-5の範囲外
        }

        with pytest.raises(ValueError, match="priority must be an integer between 1 and 5"):
            add_goal(parameters)


class TestUpdateGoal:
    """update_goal関数のテスト"""

    def test_update_goal_success(self, dynamodb_table):
        """目標更新: 正常系"""
        # まず目標を作成
        add_result = add_goal({
            "userId": "user123",
            "goalType": "fitness",
            "title": "アスリート体型になる"
        })
        goal_id = add_result["goalId"]

        # 更新
        parameters = {
            "userId": "user123",
            "goalId": goal_id,
            "title": "更新されたタイトル",
            "status": "paused"
        }

        result = update_goal(parameters)

        assert result["success"] is True
        assert result["goal"]["title"] == "更新されたタイトル"
        assert result["goal"]["status"] == "paused"

    def test_update_nonexistent_goal(self, dynamodb_table):
        """存在しない目標を更新: エラー"""
        parameters = {
            "userId": "user123",
            "goalId": "nonexistent-goal-id",
            "title": "更新されたタイトル"
        }

        with pytest.raises(ValueError, match="Goal not found"):
            update_goal(parameters)


class TestDeleteGoal:
    """delete_goal関数のテスト"""

    def test_delete_goal_success(self, dynamodb_table):
        """目標削除: 正常系"""
        # まず目標を作成
        add_result = add_goal({
            "userId": "user123",
            "goalType": "fitness",
            "title": "アスリート体型になる"
        })
        goal_id = add_result["goalId"]

        # 削除
        parameters = {
            "userId": "user123",
            "goalId": goal_id
        }

        result = delete_goal(parameters)

        assert result["success"] is True
        assert result["goalId"] == goal_id

    def test_delete_nonexistent_goal(self, dynamodb_table):
        """存在しない目標を削除: エラー"""
        parameters = {
            "userId": "user123",
            "goalId": "nonexistent-goal-id"
        }

        with pytest.raises(ValueError, match="Goal not found"):
            delete_goal(parameters)


class TestGetGoals:
    """get_goals関数のテスト"""

    def test_get_goals_with_data(self, dynamodb_table):
        """目標が存在する場合"""
        # 複数の目標を作成
        add_goal({
            "userId": "user123",
            "goalType": "fitness",
            "title": "フィットネス目標"
        })
        add_goal({
            "userId": "user123",
            "goalType": "weight",
            "title": "体重目標"
        })

        parameters = {
            "userId": "user123"
        }

        result = get_goals(parameters)

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["goals"]) == 2

    def test_get_goals_empty(self, dynamodb_table):
        """目標が存在しない場合"""
        parameters = {
            "userId": "user123"
        }

        result = get_goals(parameters)

        assert result["success"] is True
        assert result["count"] == 0
        assert len(result["goals"]) == 0

    def test_get_goals_missing_user_id(self, dynamodb_table):
        """userIdが欠落: エラー"""
        parameters = {}

        with pytest.raises(ValueError, match="userId is required"):
            get_goals(parameters)