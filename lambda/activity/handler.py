"""
ActivityLambda - 活動記録管理Lambda関数

HealthManagerMCP（Healthmateエコシステム）の活動記録管理を担当。
AgentCore Gateway（MCP）から呼び出され、DynamoDBで活動記録のCRUD操作を実行します。

機能:
- addActivities: 指定した日に新しい活動を追加（複数活動の追加）
- updateActivity: 指定した日の特定の時刻の活動だけを部分的に更新
- updateActivities: 指定した日の全ての活動を完全に置き換え
- deleteActivity: 指定した日の指定した行動を削除
- getActivities: 指定した日のユーザーの行動を取得
- getActivitiesInRange: 指定した期間のユーザーの行動履歴を取得（最大365日）

要件: 要件5-8（活動記録管理）、要件11（データ永続化）、要件12（エラーハンドリング）、要件13（ロギング）
"""

import json
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Literal
import boto3
from botocore.exceptions import ClientError

# ログ設定
log_level = os.environ.get("LOG_LEVEL", "INFO")
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, log_level.upper()))

# CloudWatch Logsハンドラーが自動的に設定されるため、追加設定は不要

# DynamoDBクライアント（指数バックオフ付き再試行設定）
from botocore.config import Config

config = Config(
    retries={
        "max_attempts": 3,
        "mode": "standard",  # 指数バックオフ
    }
)

dynamodb = boto3.resource("dynamodb", config=config)
table_name = os.environ.get("ACTIVITIES_TABLE_NAME", "healthmate-activities")
table = dynamodb.Table(table_name)

# 型定義
ActivityType = Literal[
    "wakeUp",        # 起床
    "sleep",         # 就寝
    "exercise",      # 運動
    "meal",          # 食事
    "snack",         # 間食
    "mood",          # 気分記録
    "medication",    # 服薬
    "bowelMovement", # 排便
    "urination",     # 排尿
    "symptoms",      # 症状
    "other"          # その他
]


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数のエントリーポイント
    
    AgentCore Gateway（MCP）から呼び出され、活動記録のCRUD操作を実行します。
    クライアント側でJWTのsubクレームから抽出されたuserIdがパラメータとして渡されます。

    Args:
        event: AgentCore Gatewayからのイベント（MCPツール呼び出し）
        context: Lambda実行コンテキスト

    Returns:
        MCP形式のレスポンス
    """
    logger.debug(f"Received event: {json.dumps(event, default=str)}")

    try:
        # AgentCore Gateway（MCP）形式のイベントを処理
        parameters = event.copy()
        
        # userIdの検証（必須）
        if "userId" not in parameters:
            raise ValueError("userId is required for all activity operations")
        
        user_id = parameters["userId"]
        logger.info(f"Processing request for userId: {user_id}")
        
        # contextからツール名を取得
        tool_name = context.client_context.custom['bedrockAgentCoreToolName'].split('___', 1)[-1]
        logger.debug(f"Tool name from context: {tool_name}")
        
        # ツールに基づいて関数を実行
        if tool_name == "AddActivities":
            result = add_activities(parameters)
        elif tool_name == "UpdateActivity":
            result = update_activity(parameters)
        elif tool_name == "UpdateActivities":
            result = update_activities(parameters)
        elif tool_name == "DeleteActivity":
            result = delete_activity(parameters)
        elif tool_name == "GetActivities":
            result = get_activities(parameters)
        elif tool_name == "GetActivitiesInRange":
            result = get_activities_in_range(parameters)
        else:
            raise ValueError(f"Unknown operation: {tool_name}")
        
        logger.info(f"Operation completed successfully: {tool_name}")
        return result

    except ValueError as e:
        # バリデーションエラー
        error_msg = f"Validation error: {str(e)}"
        logger.warning(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "errorType": "ValidationError"
        }
    except ClientError as e:
        # DynamoDBエラー
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"Database error ({error_code}): {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": "データベースエラーが発生しました。しばらくしてから再度お試しください。",
            "errorType": "DatabaseError",
            "errorCode": error_code
        }
    except Exception as e:
        # その他のエラー
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": "予期しないエラーが発生しました。しばらくしてから再度お試しください。",
            "errorType": "InternalError"
        }


def add_activities(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定した日に新しい活動を追加する（既存の活動は保持される）

    Args:
        parameters: userId, date, activities (list of activity objects)

    Returns:
        追加結果（各活動にactivityIdが自動生成される）

    Raises:
        ValueError: 必須パラメータが不足している場合、または活動データが不正な場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    date = parameters.get("date")
    activities = parameters.get("activities", [])

    if not user_id:
        raise ValueError("userId is required")
    if not date:
        raise ValueError("date is required")
    if not activities or not isinstance(activities, list):
        raise ValueError("activities must be a non-empty list")

    logger.debug(f"Adding {len(activities)} activities for user: {user_id} on date: {date}")

    # 各活動の検証とactivityIdの自動生成
    for idx, activity in enumerate(activities):
        if not isinstance(activity, dict):
            raise ValueError(f"Activity at index {idx} must be an object")
        
        required_fields = ["time", "activityType", "description"]
        for field in required_fields:
            if field not in activity:
                raise ValueError(f"Activity at index {idx} must have {field}")
        
        # activityIdを自動生成
        activity["activityId"] = str(uuid.uuid4())
        
        # itemsが文字列の場合はリストに変換
        if "items" in activity and isinstance(activity["items"], str):
            activity["items"] = [activity["items"]] if activity["items"] else []
        elif "items" not in activity:
            activity["items"] = []

    now = datetime.now(timezone.utc).isoformat()

    try:
        # 既存のレコードを取得
        response = table.get_item(Key={"userId": user_id, "date": date})

        if "Item" in response:
            # 既存のレコードがある場合、活動リストに追加
            existing_activities = response["Item"].get("activities", [])
            existing_activities.extend(activities)

            table.update_item(
                Key={"userId": user_id, "date": date},
                UpdateExpression="SET activities = :activities, updatedAt = :updatedAt",
                ExpressionAttributeValues={
                    ":activities": existing_activities,
                    ":updatedAt": now,
                },
            )
            logger.debug(f"Added {len(activities)} activities to existing record")
        else:
            # 新しいレコードを作成
            table.put_item(
                Item={
                    "userId": user_id,
                    "date": date,
                    "activities": activities,
                    "createdAt": now,
                    "updatedAt": now,
                }
            )
            logger.debug(f"Created new record with {len(activities)} activities")

        # 生成されたactivityIdを含むレスポンス
        added_activity_ids = [activity["activityId"] for activity in activities]
        
        logger.info(f"Activities added successfully for user: {user_id} on date: {date}")
        return {
            "success": True,
            "message": f"{date}に{len(activities)}件の活動を追加しました",
            "date": date,
            "addedCount": len(activities),
            "addedActivityIds": added_activity_ids,
            "addedActivities": activities
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in add_activities: {error_code} - {str(e)}")
        raise


def update_activity(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定したactivityIdの活動を部分的に更新する

    Args:
        parameters: userId, activityId, time(optional), activityType(optional), description(optional), items(optional)

    Returns:
        更新結果

    Raises:
        ValueError: 必須パラメータが不足している場合、または活動が見つからない場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    activity_id = parameters.get("activityId")
    time = parameters.get("time")
    activity_type = parameters.get("activityType")
    description = parameters.get("description")
    items = parameters.get("items")

    if not user_id:
        raise ValueError("userId is required")
    if not activity_id:
        raise ValueError("activityId is required")

    logger.debug(f"Updating activity for user: {user_id} with activityId: {activity_id}")

    # itemsが文字列の場合はリストに変換
    if isinstance(items, str):
        items = [items] if items else []

    now = datetime.now(timezone.utc).isoformat()

    try:
        # 全ての日付のレコードを検索してactivityIdを探す
        # まず、最近の日付から検索（効率化のため）
        activity_found = False
        target_date = None
        updated_activity = None
        
        # 過去30日間を検索（通常はこの範囲内にあると想定）
        from datetime import date, timedelta
        today = date.today()
        
        for i in range(30):
            search_date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            
            response = table.get_item(Key={"userId": user_id, "date": search_date})
            
            if "Item" in response:
                activities = response["Item"].get("activities", [])
                
                for activity in activities:
                    if activity.get("activityId") == activity_id:
                        activity_found = True
                        target_date = search_date
                        
                        # 活動を更新
                        if time is not None:
                            activity["time"] = time
                        if activity_type is not None:
                            activity["activityType"] = activity_type
                        if description is not None:
                            activity["description"] = description
                        if items is not None:
                            activity["items"] = items
                        
                        updated_activity = activity.copy()
                        
                        # 更新されたリストを保存
                        table.update_item(
                            Key={"userId": user_id, "date": search_date},
                            UpdateExpression="SET activities = :activities, updatedAt = :updatedAt",
                            ExpressionAttributeValues={
                                ":activities": activities,
                                ":updatedAt": now,
                            },
                        )
                        break
                
                if activity_found:
                    break

        if not activity_found:
            raise ValueError(f"Activity with activityId: {activity_id} not found")

        logger.info(f"Activity updated successfully for user: {user_id} with activityId: {activity_id}")
        return {
            "success": True,
            "message": f"活動ID {activity_id} を更新しました",
            "activityId": activity_id,
            "date": target_date,
            "updatedActivity": updated_activity
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in update_activity: {error_code} - {str(e)}")
        raise


def update_activities(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定した日の全ての活動を完全に置き換える（既存の活動は全て削除され、新しいリストで上書きされる）

    Args:
        parameters: userId, date, activities (list of activity objects)

    Returns:
        更新結果（各活動にactivityIdが自動生成される）

    Raises:
        ValueError: 必須パラメータが不足している場合、または活動データが不正な場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    date = parameters.get("date")
    activities = parameters.get("activities", [])

    if not user_id:
        raise ValueError("userId is required")
    if not date:
        raise ValueError("date is required")
    if not isinstance(activities, list):
        raise ValueError("activities must be a list")

    logger.debug(f"Replacing all activities for user: {user_id} on date: {date} with {len(activities)} activities")

    # 各活動の検証とactivityIdの自動生成
    for idx, activity in enumerate(activities):
        if not isinstance(activity, dict):
            raise ValueError(f"Activity at index {idx} must be an object")
        
        required_fields = ["time", "activityType", "description"]
        for field in required_fields:
            if field not in activity:
                raise ValueError(f"Activity at index {idx} must have {field}")
        
        # activityIdを自動生成（既存のIDがある場合は保持）
        if "activityId" not in activity:
            activity["activityId"] = str(uuid.uuid4())
        
        # itemsが文字列の場合はリストに変換
        if "items" in activity and isinstance(activity["items"], str):
            activity["items"] = [activity["items"]] if activity["items"] else []
        elif "items" not in activity:
            activity["items"] = []

    now = datetime.now(timezone.utc).isoformat()

    try:
        # 既存のレコードを取得
        response = table.get_item(Key={"userId": user_id, "date": date})

        if "Item" in response:
            # 既存のレコードがある場合、活動リストを完全に置き換え
            table.update_item(
                Key={"userId": user_id, "date": date},
                UpdateExpression="SET activities = :activities, updatedAt = :updatedAt",
                ExpressionAttributeValues={
                    ":activities": activities,
                    ":updatedAt": now,
                },
            )
            logger.debug(f"Replaced existing activities")
        else:
            # 新しいレコードを作成
            table.put_item(
                Item={
                    "userId": user_id,
                    "date": date,
                    "activities": activities,
                    "createdAt": now,
                    "updatedAt": now,
                }
            )
            logger.debug(f"Created new record")

        # 生成されたactivityIdを含むレスポンス
        activity_ids = [activity["activityId"] for activity in activities]

        logger.info(f"Activities updated successfully for user: {user_id} on date: {date}")
        return {
            "success": True,
            "message": f"{date}の活動を{len(activities)}件に更新しました",
            "date": date,
            "updatedCount": len(activities),
            "activityIds": activity_ids,
            "activities": activities
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in update_activities: {error_code} - {str(e)}")
        raise


def delete_activity(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定したactivityIdの活動を削除する

    Args:
        parameters: userId, activityId

    Returns:
        削除結果

    Raises:
        ValueError: 必須パラメータが不足している場合、または活動が見つからない場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    activity_id = parameters.get("activityId")

    if not user_id:
        raise ValueError("userId is required")
    if not activity_id:
        raise ValueError("activityId is required")

    logger.debug(f"Deleting activity for user: {user_id} with activityId: {activity_id}")

    now = datetime.now(timezone.utc).isoformat()

    try:
        # 全ての日付のレコードを検索してactivityIdを探す
        # まず、最近の日付から検索（効率化のため）
        activity_found = False
        target_date = None
        deleted_activity = None
        
        # 過去30日間を検索（通常はこの範囲内にあると想定）
        from datetime import date, timedelta
        today = date.today()
        
        for i in range(30):
            search_date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            
            response = table.get_item(Key={"userId": user_id, "date": search_date})
            
            if "Item" in response:
                activities = response["Item"].get("activities", [])
                original_length = len(activities)
                
                # 削除対象の活動を保存してから削除
                for activity in activities:
                    if activity.get("activityId") == activity_id:
                        deleted_activity = activity.copy()
                        activity_found = True
                        target_date = search_date
                        break
                
                if activity_found:
                    # 指定されたactivityIdの活動を削除
                    activities = [a for a in activities if a.get("activityId") != activity_id]
                    
                    if len(activities) == 0:
                        # すべての活動が削除された場合、レコード自体を削除
                        table.delete_item(Key={"userId": user_id, "date": search_date})
                        logger.debug(f"Deleted entire record (last activity removed)")
                    else:
                        # 更新されたリストを保存
                        table.update_item(
                            Key={"userId": user_id, "date": search_date},
                            UpdateExpression="SET activities = :activities, updatedAt = :updatedAt",
                            ExpressionAttributeValues={
                                ":activities": activities,
                                ":updatedAt": now,
                            },
                        )
                        logger.debug(f"Updated record with remaining {len(activities)} activities")
                    break

        if not activity_found:
            raise ValueError(f"Activity with activityId: {activity_id} not found")

        logger.info(f"Activity deleted successfully for user: {user_id} with activityId: {activity_id}")
        return {
            "success": True,
            "message": f"活動ID {activity_id} を削除しました",
            "activityId": activity_id,
            "date": target_date,
            "deletedActivity": deleted_activity,
            "remainingCount": len(activities) if activity_found else 0
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in delete_activity: {error_code} - {str(e)}")
        raise


def get_activities(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定した日のユーザーの行動を取得する

    Args:
        parameters: userId, date

    Returns:
        活動のリスト（各活動にactivityIdが含まれる）

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    date = parameters.get("date")

    if not user_id:
        raise ValueError("userId is required")
    if not date:
        raise ValueError("date is required")

    logger.debug(f"Retrieving activities for user: {user_id} on date: {date}")

    try:
        response = table.get_item(Key={"userId": user_id, "date": date})

        if "Item" in response:
            activities = response["Item"].get("activities", [])
            logger.info(f"Retrieved {len(activities)} activities for user: {user_id} on date: {date}")
            return {
                "success": True,
                "date": date,
                "activities": activities,
                "count": len(activities),
            }
        else:
            logger.info(f"No activities found for user: {user_id} on date: {date}")
            return {
                "success": True,
                "date": date,
                "activities": [],
                "count": 0,
            }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_activities: {error_code} - {str(e)}")
        raise


def get_activities_in_range(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定した期間のユーザーの行動履歴を取得する（最大365日）

    Args:
        parameters: userId, startDate, endDate

    Returns:
        期間内の活動のリスト

    Raises:
        ValueError: 必須パラメータが不足している場合、または日付範囲が不正な場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    start_date = parameters.get("startDate")
    end_date = parameters.get("endDate")

    if not user_id:
        raise ValueError("userId is required")
    if not start_date:
        raise ValueError("startDate is required")
    if not end_date:
        raise ValueError("endDate is required")

    logger.debug(f"Retrieving activities for user: {user_id} from {start_date} to {end_date}")

    # 日付の妥当性チェック
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD")

    if start_dt > end_dt:
        raise ValueError("startDate must be before or equal to endDate")

    # 最大365日間（1年間）の制限
    date_range_days = (end_dt - start_dt).days
    if date_range_days > 365:
        raise ValueError("Date range cannot exceed 365 days")

    try:
        # DynamoDBのクエリで日付範囲を指定
        response = table.query(
            KeyConditionExpression="userId = :userId AND #date BETWEEN :startDate AND :endDate",
            ExpressionAttributeNames={
                "#date": "date"  # 'date'は予約語なのでエイリアスを使用
            },
            ExpressionAttributeValues={
                ":userId": user_id,
                ":startDate": start_date,
                ":endDate": end_date,
            }
        )

        daily_activities = []
        total_activities = 0
        for item in response.get("Items", []):
            activities = item.get("activities", [])
            daily_activities.append({
                "date": item["date"],
                "activities": activities,
                "count": len(activities)
            })
            total_activities += len(activities)

        # 日付順にソート
        daily_activities.sort(key=lambda x: x["date"])

        logger.info(f"Retrieved activities for user: {user_id} - {len(daily_activities)} days, {total_activities} total activities")
        return {
            "success": True,
            "userId": user_id,
            "startDate": start_date,
            "endDate": end_date,
            "dailyActivities": daily_activities,
            "totalDays": len(daily_activities),
            "totalActivities": total_activities,
            "dateRangeDays": date_range_days + 1  # 開始日と終了日を含む日数
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_activities_in_range: {error_code} - {str(e)}")
        raise
