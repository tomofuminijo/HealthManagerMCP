"""
HolisticUserDataLambda - 包括的健康データ取得Lambda関数

HealthManagerMCP（Healthmateエコシステム）の包括的健康データ取得を担当。
AgentCore Gateway（MCP）から呼び出され、8つのDynamoDBテーブルから
ユーザーの健康データを一括で取得します。

機能:
- GetUserHolisticData: ユーザーの包括的健康データを一括取得

取得データ:
- ユーザー情報（healthmate-users）
- 健康目標（healthmate-goals）- アクティブのみ
- 健康ポリシー（healthmate-policies）- アクティブのみ
- 健康コンサーン（healthmate-concerns）- アクティブのみ
- 身体測定（healthmate-body-measurements）- 最新・最古・直近3日
- 活動履歴（healthmate-activities）- 直近3日
- 経過観測（healthmate-observations）- InProgressのみ
- 日記（healthmate-journals）- 前日のみ

要件: 要件1（包括的データ取得）、要件2（構造化レスポンス）、要件4（エラーハンドリング）、要件7（インフラ統合）
"""

import json
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr

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

# 環境変数からテーブル名を取得
USERS_TABLE_NAME = os.environ.get("USERS_TABLE_NAME", "healthmate-users")
GOALS_TABLE_NAME = os.environ.get("GOALS_TABLE_NAME", "healthmate-goals")
POLICIES_TABLE_NAME = os.environ.get("POLICIES_TABLE_NAME", "healthmate-policies")
CONCERNS_TABLE_NAME = os.environ.get("CONCERNS_TABLE_NAME", "healthmate-concerns")
BODY_MEASUREMENTS_TABLE_NAME = os.environ.get("BODY_MEASUREMENTS_TABLE_NAME", "healthmate-body-measurements")
ACTIVITIES_TABLE_NAME = os.environ.get("ACTIVITIES_TABLE_NAME", "healthmate-activities")
OBSERVATIONS_TABLE_NAME = os.environ.get("OBSERVATIONS_TABLE_NAME", "healthmate-observations")
JOURNALS_TABLE_NAME = os.environ.get("JOURNALS_TABLE_NAME", "healthmate-journals")

# DynamoDBテーブルオブジェクト
users_table = dynamodb.Table(USERS_TABLE_NAME)
goals_table = dynamodb.Table(GOALS_TABLE_NAME)
policies_table = dynamodb.Table(POLICIES_TABLE_NAME)
concerns_table = dynamodb.Table(CONCERNS_TABLE_NAME)
body_measurements_table = dynamodb.Table(BODY_MEASUREMENTS_TABLE_NAME)
activities_table = dynamodb.Table(ACTIVITIES_TABLE_NAME)
observations_table = dynamodb.Table(OBSERVATIONS_TABLE_NAME)
journals_table = dynamodb.Table(JOURNALS_TABLE_NAME)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数のエントリーポイント
    
    AgentCore Gateway（MCP）から呼び出され、ユーザーの包括的健康データを取得します。
    クライアント側でJWTのsubクレームから抽出されたuserIdがパラメータとして渡されます。

    Args:
        event: AgentCore Gatewayからのイベント（MCPツール呼び出し）
        context: Lambda実行コンテキスト

    Returns:
        MCP形式のレスポンス（包括的健康データ）
    """
    logger.debug(f"Received event: {json.dumps(event, default=str)}")

    try:
        # AgentCore Gateway（MCP）形式のイベントを処理
        # eventには直接パラメータが含まれる
        parameters = event.copy()
        
        # userIdの検証（必須）
        if "userId" not in parameters:
            raise ValueError("userId is required for holistic data retrieval")
        
        user_id = parameters["userId"]
        timezone_str = parameters.get("timezone", "Asia/Tokyo")
        
        logger.info(f"Processing holistic data request for userId: {user_id}, timezone: {timezone_str}")
        
        # contextからツール名を取得（デバッグ用）
        tool_name = "GetUserHolisticData"
        if hasattr(context, 'client_context') and context.client_context and hasattr(context.client_context, 'custom'):
            tool_name = context.client_context.custom.get('bedrockAgentCoreToolName', 'GetUserHolisticData')
            if '___' in tool_name:
                tool_name = tool_name.split('___', 1)[-1]
        
        logger.debug(f"Tool name from context: {tool_name}")
        
        # 包括的データ取得を実行
        result = get_user_holistic_data(parameters)
        
        logger.info(f"Holistic data retrieval completed successfully for userId: {user_id}")
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


def get_user_holistic_data(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    包括的データ取得のメイン関数
    
    8つのDynamoDBテーブルからユーザーの健康データを取得し、
    構造化されたレスポンスを構築します。

    Args:
        parameters: userId, timezone(optional)

    Returns:
        包括的健康データのレスポンス

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    timezone_str = parameters.get("timezone", "Asia/Tokyo")
    
    if not user_id:
        raise ValueError("userId is required")
    
    logger.info(f"Starting holistic data retrieval for user: {user_id}")
    
    # 現在時刻とメタデータ
    retrieved_at = datetime.now(timezone.utc).isoformat()
    
    # 日付範囲を計算
    date_ranges = get_date_ranges(timezone_str)
    
    # 各データセクションを取得（データが存在しない場合は空構造を返す）
    user_profile = get_user_profile(user_id)
    goals = get_active_goals(user_id)
    policies = get_active_policies(user_id)
    concerns = get_active_concerns(user_id)
    body_measurements = get_body_measurements(user_id, date_ranges)
    activities = get_recent_activities(user_id, date_ranges)
    observations = get_in_progress_observations(user_id)
    reflection = get_previous_day_reflection(user_id, date_ranges["previous_day"])
    
    # データ新鮮度情報を構築
    data_freshness = {
        "userProfile": retrieved_at,
        "goals": retrieved_at,
        "policies": retrieved_at,
        "concerns": retrieved_at,
        "bodyMeasurements": retrieved_at,
        "activities": retrieved_at,
        "observations": retrieved_at,
        "reflection": retrieved_at
    }
    
    # レスポンス構造を構築
    response = {
        "success": True,
        "data": {
            "metadata": {
                "userId": user_id,
                "retrievedAt": retrieved_at,
                "dataFreshness": data_freshness
            },
            "userProfile": user_profile,
            "goals": goals,
            "policies": policies,
            "concerns": concerns,
            "bodyMeasurements": body_measurements,
            "activities": activities,
            "observations": observations,
            "reflection": reflection
        }
    }
    
    logger.info(f"Holistic data retrieval completed for user: {user_id}")
    return response


def get_date_ranges(timezone_str: str = "Asia/Tokyo") -> Dict[str, str]:
    """
    現在時刻基準で必要な日付範囲を計算
    
    Args:
        timezone_str: ユーザーのタイムゾーン
    
    Returns:
        today: 今日の日付 (YYYY-MM-DD)
        previous_day: 前日の日付 (YYYY-MM-DD)
        start_date: 3日前の日付 (YYYY-MM-DD)
        end_date: 今日の日付 (YYYY-MM-DD)
    """
    try:
        # Asia/Tokyoの場合はUTC+9時間のオフセットを使用
        if timezone_str == "Asia/Tokyo":
            tz_offset = timedelta(hours=9)
        else:
            # 他のタイムゾーンの場合はUTCを使用（簡略化）
            tz_offset = timedelta(hours=0)
            logger.warning(f"Timezone {timezone_str} not supported, using UTC")
        
        # UTCで現在時刻を取得し、タイムゾーンオフセットを適用
        utc_now = datetime.now(timezone.utc)
        local_now = utc_now + tz_offset
        today = local_now.date()
        
        # 日付範囲を計算
        previous_day = today - timedelta(days=1)
        start_date = today - timedelta(days=2)  # 今日含む3日間
        end_date = today
        
        date_ranges = {
            "today": today.strftime("%Y-%m-%d"),
            "previous_day": previous_day.strftime("%Y-%m-%d"),
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
        }
        
        logger.debug(f"Calculated date ranges for timezone {timezone_str}: {date_ranges}")
        return date_ranges
        
    except Exception as e:
        logger.warning(f"Error calculating date ranges for timezone {timezone_str}: {str(e)}")
        # フォールバック: UTCで計算
        utc_now = datetime.now(timezone.utc)
        today = utc_now.date()
        
        previous_day = today - timedelta(days=1)
        start_date = today - timedelta(days=2)
        end_date = today
        
        return {
            "today": today.strftime("%Y-%m-%d"),
            "previous_day": previous_day.strftime("%Y-%m-%d"),
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
        }


def get_user_profile(user_id: str) -> Dict[str, Any]:
    """
    ユーザー情報取得
    
    Args:
        user_id: ユーザーID
    
    Returns:
        ユーザー情報（データが存在しない場合は空構造）
    
    Raises:
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    try:
        logger.debug(f"Retrieving user profile for: {user_id}")
        
        response = users_table.get_item(Key={"userId": user_id})
        
        if "Item" in response:
            user = response["Item"]
            logger.debug(f"User profile found for: {user_id}")
            
            # レスポンス用のユーザー情報を構築
            user_profile = {
                "userId": user.get("userId"),
                "username": user.get("username"),
                "email": user.get("email", ""),
                "createdAt": user.get("createdAt"),
                "lastLoginAt": user.get("lastLoginAt"),
            }
            
            # 生年月日が存在する場合のみレスポンスに含める
            if "dateOfBirth" in user:
                user_profile["dateOfBirth"] = user["dateOfBirth"]
            else:
                user_profile["dateOfBirth"] = None
            
            return user_profile
        else:
            logger.info(f"User profile not found for: {user_id}")
            # データが存在しない場合は空構造を返す
            return {
                "userId": user_id,
                "username": None,
                "email": None,
                "dateOfBirth": None,
                "createdAt": None,
                "lastLoginAt": None
            }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_user_profile: {error_code} - {str(e)}")
        raise


def get_active_goals(user_id: str) -> List[Dict[str, Any]]:
    """
    アクティブな健康目標取得
    
    Args:
        user_id: ユーザーID
    
    Returns:
        アクティブな健康目標のリスト（データが存在しない場合は空配列）
    
    Raises:
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    try:
        logger.debug(f"Retrieving active goals for: {user_id}")
        
        # userIdをパーティションキーとしてクエリし、statusでフィルタリング
        response = goals_table.query(
            KeyConditionExpression=Key('userId').eq(user_id),
            FilterExpression=Attr('status').eq('active')
        )
        
        goals = response.get('Items', [])
        logger.debug(f"Found {len(goals)} active goals for user: {user_id}")
        
        return goals

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_active_goals: {error_code} - {str(e)}")
        raise


def get_active_policies(user_id: str) -> List[Dict[str, Any]]:
    """
    アクティブな健康ポリシー取得
    
    Args:
        user_id: ユーザーID
    
    Returns:
        アクティブな健康ポリシーのリスト（データが存在しない場合は空配列）
    
    Raises:
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    try:
        logger.debug(f"Retrieving active policies for: {user_id}")
        
        response = policies_table.query(
            KeyConditionExpression=Key('userId').eq(user_id),
            FilterExpression=Attr('isActive').eq('true')
        )
        
        policies = response.get('Items', [])
        logger.debug(f"Found {len(policies)} active policies for user: {user_id}")
        
        return policies

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_active_policies: {error_code} - {str(e)}")
        raise


def get_active_concerns(user_id: str) -> List[Dict[str, Any]]:
    """
    アクティブな健康コンサーン取得
    
    Args:
        user_id: ユーザーID
    
    Returns:
        アクティブな健康コンサーンのリスト（データが存在しない場合は空配列）
    
    Raises:
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    try:
        logger.debug(f"Retrieving active concerns for: {user_id}")
        
        # userIdをパーティションキーとしてクエリし、statusでフィルタリング
        response = concerns_table.query(
            KeyConditionExpression=Key('userId').eq(user_id),
            FilterExpression=Attr('status').is_in(['ACTIVE', 'IMPROVED'])
        )
        
        concerns = response.get('Items', [])
        logger.debug(f"Found {len(concerns)} active concerns for user: {user_id}")
        
        return concerns

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_active_concerns: {error_code} - {str(e)}")
        raise


def get_body_measurements(user_id: str, date_ranges: Dict[str, str]) -> Dict[str, Any]:
    """
    身体測定データ取得（最新、最古、直近3日）
    
    Args:
        user_id: ユーザーID
        date_ranges: 日付範囲情報
    
    Returns:
        身体測定データ（latest, oldest, recent3Days）
    
    Raises:
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    try:
        logger.debug(f"Retrieving body measurements for: {user_id}")
        
        # 最新レコード取得（LSIを使用）
        latest_measurement = None
        try:
            latest_response = body_measurements_table.query(
                IndexName='RecordTypeIndex',
                KeyConditionExpression=Key('userId').eq(user_id) & Key('record_type').eq('latest'),
                Limit=1
            )
            if latest_response.get('Items'):
                latest_measurement = latest_response['Items'][0]
                logger.debug(f"Found latest measurement for user: {user_id}")
        except ClientError as e:
            logger.warning(f"Error retrieving latest measurement: {str(e)}")
        
        # 最古レコード取得（LSIを使用）
        oldest_measurement = None
        try:
            oldest_response = body_measurements_table.query(
                IndexName='RecordTypeIndex',
                KeyConditionExpression=Key('userId').eq(user_id) & Key('record_type').eq('oldest'),
                Limit=1
            )
            if oldest_response.get('Items'):
                oldest_measurement = oldest_response['Items'][0]
                logger.debug(f"Found oldest measurement for user: {user_id}")
        except ClientError as e:
            logger.warning(f"Error retrieving oldest measurement: {str(e)}")
        
        # 直近3日分のデータ取得（通常のクエリ + フィルタ）
        recent_measurements = []
        try:
            # 直近3日間の開始日と終了日を計算
            start_date = date_ranges["start_date"]  # 3日前
            end_date = date_ranges["end_date"]      # 今日
            
            # ソートキーの範囲を指定
            start_sk = f"MEASUREMENT#{start_date}"
            end_sk = f"MEASUREMENT#{end_date}Z"  # Zを付けてその日の最後まで含める
            
            recent_response = body_measurements_table.query(
                KeyConditionExpression=Key('userId').eq(user_id) & 
                                     Key('measurementId').between(start_sk, end_sk)
            )
            recent_measurements = recent_response.get('Items', [])
            logger.debug(f"Found {len(recent_measurements)} recent measurements for user: {user_id}")
        except ClientError as e:
            logger.warning(f"Error retrieving recent measurements: {str(e)}")
        
        return {
            "latest": latest_measurement,
            "oldest": oldest_measurement,
            "recent3Days": recent_measurements
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_body_measurements: {error_code} - {str(e)}")
        raise


def get_recent_activities(user_id: str, date_ranges: Dict[str, str]) -> Dict[str, Any]:
    """
    直近3日の活動履歴取得
    
    Args:
        user_id: ユーザーID
        date_ranges: 日付範囲情報
    
    Returns:
        直近3日の活動履歴
    
    Raises:
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    try:
        logger.debug(f"Retrieving recent activities for: {user_id}")
        
        # userIdをパーティションキーとし、dateをソートキーとして範囲クエリ
        response = activities_table.query(
            KeyConditionExpression=Key('userId').eq(user_id) & Key('date').between(
                date_ranges["start_date"], 
                date_ranges["end_date"]
            )
        )
        
        activities_data = response.get('Items', [])
        logger.debug(f"Found {len(activities_data)} activity records for user: {user_id}")
        
        # 日付ごとに整理
        recent_activities = []
        for activity_record in activities_data:
            activities_list = activity_record.get('activities', [])
            recent_activities.append({
                "date": activity_record.get('date'),
                "activities": activities_list,
                "count": len(activities_list)
            })
        
        # 日付順でソート
        recent_activities.sort(key=lambda x: x['date'])
        
        return {
            "recent3Days": recent_activities
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_recent_activities: {error_code} - {str(e)}")
        raise


def get_in_progress_observations(user_id: str) -> Dict[str, Any]:
    """
    進行中の経過観測取得
    
    Args:
        user_id: ユーザーID
    
    Returns:
        進行中の経過観測データ
    
    Raises:
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    try:
        logger.debug(f"Retrieving in-progress observations for: {user_id}")
        
        # LSIを使用して進行中の観測を取得
        response = observations_table.query(
            IndexName='InProgressIndex',
            KeyConditionExpression=Key('userId').eq(user_id) & Key('in_progress').eq('TRUE')
        )
        
        observations = response.get('Items', [])
        logger.debug(f"Found {len(observations)} in-progress observations for user: {user_id}")
        
        return {
            "inProgress": observations
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_in_progress_observations: {error_code} - {str(e)}")
        raise


def get_previous_day_reflection(user_id: str, previous_date: str) -> Dict[str, Any]:
    """
    前日の振り返り日記取得
    
    Args:
        user_id: ユーザーID
        previous_date: 前日の日付 (YYYY-MM-DD)
    
    Returns:
        前日の振り返り日記データ
    
    Raises:
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    try:
        logger.debug(f"Retrieving previous day reflection for: {user_id}, date: {previous_date}")
        
        response = journals_table.get_item(
            Key={"userId": user_id, "date": previous_date}
        )
        
        if "Item" in response:
            journal = response["Item"]
            logger.debug(f"Found previous day reflection for user: {user_id}")
            
            return {
                "previousDay": journal
            }
        else:
            logger.debug(f"No previous day reflection found for user: {user_id}")
            return {
                "previousDay": None
            }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_previous_day_reflection: {error_code} - {str(e)}")
        raise