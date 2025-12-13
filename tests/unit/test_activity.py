"""
ActivityLambda関数のユニットテスト
"""

import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock

# Lambda関数をインポート
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from activity.handler import (
    lambda_handler,
    add_activity,
    update_activity,
    delete_activity,
    get_activities,
    get_activities_in_range,
)


@pytest.fixture
def mock_dynamodb_table():
    """DynamoDBテーブルのモック"""
    with patch("activity.handler.table") as mock_table:
        yield mock_table


@pytest.fixture
def sample_event_add_activity():
    """addActivityイベントのサンプル"""
    return {
        "actionGroup": "ActivityManagement",
        "apiPath": "/addActivity",
        "httpMethod": "POST",
        "parameters": [
            {"name": "userId", "value": "user123"},
            {"name": "date", "value": "2024-12-07"},
            {"name": "time", "value": "08:00"},
            {"name": "activityType", "value": "wakeUp"},
            {"name": "description", "value": "起床"},
            {"name": "items", "value": []},
        ],
        "sessionAttributes": {},
    }


@pytest.fixture
def sample_event_get_activities():
    """getActivitiesイベントのサンプル"""
    return {
        "actionGroup": "ActivityManagement",
        "apiPath": "/getActivities",
        "httpMethod": "POST",
        "parameters": [
            {"name": "userId", "value": "user123"},
            {"name": "date", "value": "2024-12-07"},
        ],
        "sessionAttributes": {},
    }


class TestLambdaHandler:
    """lambda_handler関数のテスト"""

    def test_add_activity_success(
        self, mock_dynamodb_table, sample_event_add_activity
    ):
        """addActivity: 正常系"""
        mock_dynamodb_table.get_item.return_value = {}
        mock_dynamodb_table.put_item.return_value = {}

        result = lambda_handler(sample_event_add_activity, None)

        assert result["response"]["actionGroup"] == "ActivityManagement"
        assert result["response"]["apiPath"] == "/addActivity"
        assert result["response"]["httpStatusCode"] == 200
        response_body = json.loads(
            result["response"]["responseBody"]["application/json"]["body"]
        )
        assert response_body["success"] is True

    def test_get_activities_success(
        self, mock_dynamodb_table, sample_event_get_activities
    ):
        """getActivities: 正常系"""
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "userId": "user123",
                "date": "2024-12-07",
                "activities": [
                    {
                        "time": "08:00",
                        "activityType": "wakeUp",
                        "description": "起床",
                        "items": [],
                    }
                ],
            }
        }

        result = lambda_handler(sample_event_get_activities, None)

        assert result["response"]["httpStatusCode"] == 200
        response_body = json.loads(
            result["response"]["responseBody"]["application/json"]["body"]
        )
        assert response_body["success"] is True
        assert response_body["count"] == 1

    def test_unknown_api_path(self, mock_dynamodb_table):
        """未知のAPIパス: エラー"""
        event = {
            "actionGroup": "ActivityManagement",
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


class TestAddActivity:
    """add_activity関数のテスト"""

    def test_add_activity_new_record(self, mock_dynamodb_table):
        """新しい日付のレコードを作成"""
        mock_dynamodb_table.get_item.return_value = {}
        mock_dynamodb_table.put_item.return_value = {}

        parameters = {
            "userId": "user123",
            "date": "2024-12-07",
            "time": "08:00",
            "activityType": "wakeUp",
            "description": "起床",
            "items": [],
        }

        result = add_activity(parameters)

        assert result["success"] is True
        mock_dynamodb_table.put_item.assert_called_once()

    def test_add_activity_existing_record(self, mock_dynamodb_table):
        """既存の日付のレコードに追加"""
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "userId": "user123",
                "date": "2024-12-07",
                "activities": [
                    {
                        "time": "08:00",
                        "activityType": "wakeUp",
                        "description": "起床",
                        "items": [],
                    }
                ],
            }
        }
        mock_dynamodb_table.update_item.return_value = {}

        parameters = {
            "userId": "user123",
            "date": "2024-12-07",
            "time": "12:00",
            "activityType": "meal",
            "description": "昼食",
            "items": ["サラダ", "パン"],
        }

        result = add_activity(parameters)

        assert result["success"] is True
        mock_dynamodb_table.update_item.assert_called_once()

    def test_add_activity_missing_parameters(self, mock_dynamodb_table):
        """必須パラメータが欠落: エラー"""
        parameters = {"userId": "user123", "date": "2024-12-07"}

        with pytest.raises(
            ValueError, match="userId, date, time, and activityType are required"
        ):
            add_activity(parameters)


class TestUpdateActivity:
    """update_activity関数のテスト"""

    def test_update_activity_success(self, mock_dynamodb_table):
        """活動の更新: 正常系"""
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "userId": "user123",
                "date": "2024-12-07",
                "activities": [
                    {
                        "time": "08:00",
                        "activityType": "wakeUp",
                        "description": "起床",
                        "items": [],
                    }
                ],
            }
        }
        mock_dynamodb_table.update_item.return_value = {}

        parameters = {
            "userId": "user123",
            "date": "2024-12-07",
            "time": "08:00",
            "description": "早起き",
        }

        result = update_activity(parameters)

        assert result["success"] is True
        mock_dynamodb_table.update_item.assert_called_once()

    def test_update_activity_not_found(self, mock_dynamodb_table):
        """活動が見つからない: エラー"""
        mock_dynamodb_table.get_item.return_value = {}

        parameters = {
            "userId": "user123",
            "date": "2024-12-07",
            "time": "08:00",
            "description": "更新",
        }

        with pytest.raises(ValueError, match="No activities found"):
            update_activity(parameters)

    def test_update_activity_time_not_found(self, mock_dynamodb_table):
        """指定時刻の活動が見つからない: エラー"""
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "userId": "user123",
                "date": "2024-12-07",
                "activities": [
                    {
                        "time": "08:00",
                        "activityType": "wakeUp",
                        "description": "起床",
                        "items": [],
                    }
                ],
            }
        }

        parameters = {
            "userId": "user123",
            "date": "2024-12-07",
            "time": "09:00",
            "description": "更新",
        }

        with pytest.raises(ValueError, match="No activity found at"):
            update_activity(parameters)


class TestDeleteActivity:
    """delete_activity関数のテスト"""

    def test_delete_activity_success(self, mock_dynamodb_table):
        """活動の削除: 正常系"""
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "userId": "user123",
                "date": "2024-12-07",
                "activities": [
                    {
                        "time": "08:00",
                        "activityType": "wakeUp",
                        "description": "起床",
                        "items": [],
                    },
                    {
                        "time": "12:00",
                        "activityType": "meal",
                        "description": "昼食",
                        "items": [],
                    },
                ],
            }
        }
        mock_dynamodb_table.update_item.return_value = {}

        parameters = {"userId": "user123", "date": "2024-12-07", "time": "08:00"}

        result = delete_activity(parameters)

        assert result["success"] is True
        mock_dynamodb_table.update_item.assert_called_once()

    def test_delete_activity_last_one(self, mock_dynamodb_table):
        """最後の活動を削除（レコード自体を削除）"""
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "userId": "user123",
                "date": "2024-12-07",
                "activities": [
                    {
                        "time": "08:00",
                        "activityType": "wakeUp",
                        "description": "起床",
                        "items": [],
                    }
                ],
            }
        }
        mock_dynamodb_table.delete_item.return_value = {}

        parameters = {"userId": "user123", "date": "2024-12-07", "time": "08:00"}

        result = delete_activity(parameters)

        assert result["success"] is True
        mock_dynamodb_table.delete_item.assert_called_once()

    def test_delete_activity_not_found(self, mock_dynamodb_table):
        """活動が見つからない: エラー"""
        mock_dynamodb_table.get_item.return_value = {}

        parameters = {"userId": "user123", "date": "2024-12-07", "time": "08:00"}

        with pytest.raises(ValueError, match="No activities found"):
            delete_activity(parameters)


class TestGetActivities:
    """get_activities関数のテスト"""

    def test_get_activities_with_results(self, mock_dynamodb_table):
        """活動が存在する場合"""
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "userId": "user123",
                "date": "2024-12-07",
                "activities": [
                    {
                        "time": "08:00",
                        "activityType": "wakeUp",
                        "description": "起床",
                        "items": [],
                    },
                    {
                        "time": "12:00",
                        "activityType": "meal",
                        "description": "昼食",
                        "items": ["サラダ"],
                    },
                ],
            }
        }

        parameters = {"userId": "user123", "date": "2024-12-07"}

        result = get_activities(parameters)

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["activities"]) == 2

    def test_get_activities_no_results(self, mock_dynamodb_table):
        """活動が存在しない場合"""
        mock_dynamodb_table.get_item.return_value = {}

        parameters = {"userId": "user123", "date": "2024-12-07"}

        result = get_activities(parameters)

        assert result["success"] is True
        assert result["count"] == 0
        assert len(result["activities"]) == 0

    def test_get_activities_missing_parameters(self, mock_dynamodb_table):
        """必須パラメータが欠落: エラー"""
        parameters = {"userId": "user123"}

        with pytest.raises(ValueError, match="userId and date are required"):
            get_activities(parameters)


class TestGetActivitiesInRange:
    """get_activities_in_range関数のテスト"""

    def test_get_activities_in_range_success(self, mock_dynamodb_table):
        """期間指定での活動取得: 正常系"""
        mock_dynamodb_table.query.return_value = {
            "Items": [
                {
                    "userId": "user123",
                    "date": "2024-11-01",
                    "activities": [
                        {
                            "time": "08:00",
                            "activityType": "wakeUp",
                            "description": "起床",
                            "items": [],
                        }
                    ],
                },
                {
                    "userId": "user123",
                    "date": "2024-11-02",
                    "activities": [
                        {
                            "time": "08:30",
                            "activityType": "exercise",
                            "description": "運動",
                            "items": ["ジョギング1km"],
                        }
                    ],
                },
                {
                    "userId": "user123",
                    "date": "2024-11-03",
                    "activities": [
                        {
                            "time": "12:00",
                            "activityType": "meal",
                            "description": "昼食",
                            "items": ["サラダ", "パン"],
                        }
                    ],
                },
            ]
        }

        parameters = {
            "userId": "user123",
            "startDate": "2024-11-01",
            "endDate": "2024-11-03",
        }

        result = get_activities_in_range(parameters)

        assert result["success"] is True
        assert result["startDate"] == "2024-11-01"
        assert result["endDate"] == "2024-11-03"
        assert result["totalDays"] == 3
        assert len(result["dailyActivities"]) == 3
        # 日付順にソートされていることを確認
        assert result["dailyActivities"][0]["date"] == "2024-11-01"
        assert result["dailyActivities"][1]["date"] == "2024-11-02"
        assert result["dailyActivities"][2]["date"] == "2024-11-03"

    def test_get_activities_in_range_no_results(self, mock_dynamodb_table):
        """期間内に活動が存在しない場合"""
        mock_dynamodb_table.query.return_value = {"Items": []}

        parameters = {
            "userId": "user123",
            "startDate": "2024-11-01",
            "endDate": "2024-11-30",
        }

        result = get_activities_in_range(parameters)

        assert result["success"] is True
        assert result["totalDays"] == 0
        assert len(result["dailyActivities"]) == 0

    def test_get_activities_in_range_one_year(self, mock_dynamodb_table):
        """1年間（365日）の範囲: 正常系"""
        mock_dynamodb_table.query.return_value = {"Items": []}

        parameters = {
            "userId": "user123",
            "startDate": "2024-01-01",
            "endDate": "2024-12-31",
        }

        result = get_activities_in_range(parameters)

        assert result["success"] is True
        # エラーが発生しないことを確認

    def test_get_activities_in_range_exceeds_365_days(self, mock_dynamodb_table):
        """365日を超える範囲: エラー"""
        parameters = {
            "userId": "user123",
            "startDate": "2024-01-01",
            "endDate": "2025-01-02",  # 367日
        }

        with pytest.raises(ValueError, match="Date range cannot exceed 365 days"):
            get_activities_in_range(parameters)

    def test_get_activities_in_range_start_after_end(self, mock_dynamodb_table):
        """開始日が終了日より後: エラー"""
        parameters = {
            "userId": "user123",
            "startDate": "2024-12-31",
            "endDate": "2024-01-01",
        }

        with pytest.raises(
            ValueError, match="startDate must be before or equal to endDate"
        ):
            get_activities_in_range(parameters)

    def test_get_activities_in_range_invalid_date_format(self, mock_dynamodb_table):
        """不正な日付フォーマット: エラー"""
        parameters = {
            "userId": "user123",
            "startDate": "2024/11/01",  # 不正なフォーマット
            "endDate": "2024-11-30",
        }

        with pytest.raises(ValueError, match="Invalid date format"):
            get_activities_in_range(parameters)

    def test_get_activities_in_range_missing_parameters(self, mock_dynamodb_table):
        """必須パラメータが欠落: エラー"""
        parameters = {"userId": "user123", "startDate": "2024-11-01"}

        with pytest.raises(
            ValueError, match="userId, startDate, and endDate are required"
        ):
            get_activities_in_range(parameters)

    def test_get_activities_in_range_same_date(self, mock_dynamodb_table):
        """開始日と終了日が同じ: 正常系"""
        mock_dynamodb_table.query.return_value = {
            "Items": [
                {
                    "userId": "user123",
                    "date": "2024-11-01",
                    "activities": [
                        {
                            "time": "08:00",
                            "activityType": "wakeUp",
                            "description": "起床",
                            "items": [],
                        }
                    ],
                }
            ]
        }

        parameters = {
            "userId": "user123",
            "startDate": "2024-11-01",
            "endDate": "2024-11-01",
        }

        result = get_activities_in_range(parameters)

        assert result["success"] is True
        assert result["totalDays"] == 1
