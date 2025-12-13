"""
ActivityLambda関数のユニットテスト（MCP形式対応）
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

from activity.handler import lambda_handler, add_activities, update_activity, update_activities, delete_activity, get_activities, get_activities_in_range


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
            TableName='healthmate-activities',
            KeySchema=[
                {
                    'AttributeName': 'userId',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'date',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'userId',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'date',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # 環境変数を設定
        os.environ['ACTIVITIES_TABLE_NAME'] = 'healthmate-activities'
        
        yield table


class TestActivityLambdaHandler:
    """lambda_handler関数のテスト"""

    def test_add_activities_success(self, dynamodb_table):
        """addActivities: 正常系"""
        event = {
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "08:00",
                    "activityType": "wakeUp",
                    "description": "起床",
                    "items": []
                },
                {
                    "time": "08:30",
                    "activityType": "exercise",
                    "description": "運動",
                    "items": ["ジョギング30分", "筋トレ20分"]
                }
            ]
        }

        result = lambda_handler(event, None)

        assert result["success"] is True
        assert result["date"] == "2025-12-14"
        assert result["addedCount"] == 2

    def test_get_activities_success(self, dynamodb_table):
        """getActivities: 正常系"""
        # まず活動を追加
        add_event = {
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "08:00",
                    "activityType": "wakeUp",
                    "description": "起床",
                    "items": []
                }
            ]
        }
        lambda_handler(add_event, None)

        # 取得
        get_event = {
            "userId": "user123",
            "date": "2025-12-14"
        }

        result = lambda_handler(get_event, None)

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["activities"]) == 1
        assert result["activities"][0]["activityType"] == "wakeUp"

    def test_missing_user_id(self, dynamodb_table):
        """userIdが欠落: エラー"""
        event = {
            "date": "2025-12-14",
            "activities": []
        }

        result = lambda_handler(event, None)

        assert result["success"] is False
        assert result["errorType"] == "ValidationError"
        assert "userId is required" in result["error"]


class TestAddActivities:
    """add_activities関数のテスト"""

    def test_add_activities_to_new_date(self, dynamodb_table):
        """新しい日付に活動を追加"""
        parameters = {
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "08:00",
                    "activityType": "wakeUp",
                    "description": "起床",
                    "items": []
                },
                {
                    "time": "13:00",
                    "activityType": "bowelMovement",
                    "description": "排便",
                    "items": ["うんこが出た"]
                }
            ]
        }

        result = add_activities(parameters)

        assert result["success"] is True
        assert result["addedCount"] == 2

    def test_add_activities_to_existing_date(self, dynamodb_table):
        """既存の日付に活動を追加"""
        # 最初の活動を追加
        add_activities({
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "08:00",
                    "activityType": "wakeUp",
                    "description": "起床",
                    "items": []
                }
            ]
        })

        # 追加の活動を追加
        parameters = {
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "12:00",
                    "activityType": "meal",
                    "description": "昼食",
                    "items": ["サラダ", "チキン"]
                }
            ]
        }

        result = add_activities(parameters)

        assert result["success"] is True
        assert result["addedCount"] == 1

        # 合計2つの活動があることを確認
        get_result = get_activities({
            "userId": "user123",
            "date": "2025-12-14"
        })
        assert get_result["count"] == 2

    def test_add_activities_missing_required_fields(self, dynamodb_table):
        """必須フィールドが欠落: エラー"""
        parameters = {
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "08:00",
                    # activityTypeが欠落
                    "description": "起床",
                    "items": []
                }
            ]
        }

        with pytest.raises(ValueError, match="Activity at index 0 must have activityType"):
            add_activities(parameters)

    def test_add_activities_empty_list(self, dynamodb_table):
        """空の活動リスト: エラー"""
        parameters = {
            "userId": "user123",
            "date": "2025-12-14",
            "activities": []
        }

        with pytest.raises(ValueError, match="activities must be a non-empty list"):
            add_activities(parameters)


class TestUpdateActivity:
    """update_activity関数のテスト"""

    def test_update_activity_success(self, dynamodb_table):
        """活動更新: 正常系"""
        # まず活動を追加
        add_activities({
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "08:00",
                    "activityType": "wakeUp",
                    "description": "起床",
                    "items": []
                }
            ]
        })

        # 更新
        parameters = {
            "userId": "user123",
            "date": "2025-12-14",
            "time": "08:00",
            "description": "早起き",
            "items": ["気分良好"]
        }

        result = update_activity(parameters)

        assert result["success"] is True
        assert result["updatedActivity"]["description"] == "早起き"
        assert result["updatedActivity"]["items"] == ["気分良好"]

    def test_update_nonexistent_activity(self, dynamodb_table):
        """存在しない活動を更新: エラー"""
        parameters = {
            "userId": "user123",
            "date": "2025-12-14",
            "time": "08:00",
            "description": "更新"
        }

        with pytest.raises(ValueError, match="No activities found for date"):
            update_activity(parameters)


class TestUpdateActivities:
    """update_activities関数のテスト"""

    def test_update_activities_replace_all(self, dynamodb_table):
        """全活動の置き換え: 正常系"""
        # まず活動を追加
        add_activities({
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "08:00",
                    "activityType": "wakeUp",
                    "description": "起床",
                    "items": []
                }
            ]
        })

        # 全置き換え
        parameters = {
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "07:30",
                    "activityType": "wakeUp",
                    "description": "早起き",
                    "items": []
                },
                {
                    "time": "08:00",
                    "activityType": "exercise",
                    "description": "朝の運動",
                    "items": ["ストレッチ"]
                }
            ]
        }

        result = update_activities(parameters)

        assert result["success"] is True
        assert result["updatedCount"] == 2

        # 置き換えられたことを確認
        get_result = get_activities({
            "userId": "user123",
            "date": "2025-12-14"
        })
        assert get_result["count"] == 2
        assert get_result["activities"][0]["time"] == "07:30"


class TestDeleteActivity:
    """delete_activity関数のテスト"""

    def test_delete_activity_success(self, dynamodb_table):
        """活動削除: 正常系"""
        # まず活動を追加
        add_activities({
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "08:00",
                    "activityType": "wakeUp",
                    "description": "起床",
                    "items": []
                },
                {
                    "time": "12:00",
                    "activityType": "meal",
                    "description": "昼食",
                    "items": []
                }
            ]
        })

        # 削除
        parameters = {
            "userId": "user123",
            "date": "2025-12-14",
            "time": "08:00"
        }

        result = delete_activity(parameters)

        assert result["success"] is True
        assert result["remainingCount"] == 1

    def test_delete_last_activity(self, dynamodb_table):
        """最後の活動を削除（レコード自体が削除される）"""
        # 活動を1つ追加
        add_activities({
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "08:00",
                    "activityType": "wakeUp",
                    "description": "起床",
                    "items": []
                }
            ]
        })

        # 削除
        parameters = {
            "userId": "user123",
            "date": "2025-12-14",
            "time": "08:00"
        }

        result = delete_activity(parameters)

        assert result["success"] is True
        assert result["remainingCount"] == 0


class TestGetActivities:
    """get_activities関数のテスト"""

    def test_get_activities_with_data(self, dynamodb_table):
        """活動が存在する場合"""
        # 活動を追加
        add_activities({
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "08:00",
                    "activityType": "wakeUp",
                    "description": "起床",
                    "items": []
                }
            ]
        })

        parameters = {
            "userId": "user123",
            "date": "2025-12-14"
        }

        result = get_activities(parameters)

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["activities"]) == 1

    def test_get_activities_empty(self, dynamodb_table):
        """活動が存在しない場合"""
        parameters = {
            "userId": "user123",
            "date": "2025-12-14"
        }

        result = get_activities(parameters)

        assert result["success"] is True
        assert result["count"] == 0
        assert len(result["activities"]) == 0


class TestGetActivitiesInRange:
    """get_activities_in_range関数のテスト"""

    def test_get_activities_in_range_success(self, dynamodb_table):
        """期間内の活動取得: 正常系"""
        # 複数日の活動を追加
        add_activities({
            "userId": "user123",
            "date": "2025-12-14",
            "activities": [
                {
                    "time": "08:00",
                    "activityType": "wakeUp",
                    "description": "起床",
                    "items": []
                }
            ]
        })
        add_activities({
            "userId": "user123",
            "date": "2025-12-15",
            "activities": [
                {
                    "time": "08:30",
                    "activityType": "wakeUp",
                    "description": "起床",
                    "items": []
                }
            ]
        })

        parameters = {
            "userId": "user123",
            "startDate": "2025-12-14",
            "endDate": "2025-12-15"
        }

        result = get_activities_in_range(parameters)

        assert result["success"] is True
        assert result["totalDays"] == 2
        assert result["totalActivities"] == 2

    def test_get_activities_in_range_invalid_date_format(self, dynamodb_table):
        """無効な日付形式: エラー"""
        parameters = {
            "userId": "user123",
            "startDate": "invalid-date",
            "endDate": "2025-12-15"
        }

        with pytest.raises(ValueError, match="Invalid date format"):
            get_activities_in_range(parameters)

    def test_get_activities_in_range_too_long(self, dynamodb_table):
        """期間が長すぎる: エラー"""
        parameters = {
            "userId": "user123",
            "startDate": "2024-01-01",
            "endDate": "2025-12-31"  # 365日を超える
        }

        with pytest.raises(ValueError, match="Date range cannot exceed 365 days"):
            get_activities_in_range(parameters)