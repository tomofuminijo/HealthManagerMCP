"""
HealthObservationLambda - 健康経過観察管理Lambda関数

HealthManagerMCP（Healthmateエコシステム）の健康経過観察管理を担当。
AgentCore Gateway（MCP）から呼び出され、DynamoDBで経過観察データのCRUD操作を実行します。

機能:
- addObservation: 新しい経過観察記録を作成
- getObservation: 指定された経過観察記録を取得
- getObservationsInRange: 指定期間内の経過観察記録を取得
- getObservationsInProgress: 進行中の経過観察記録を取得
- updateObservation: 経過観察記録を差分更新
- addObservationProgress: 経過観察の進捗ログを追加
- completeObservation: 経過観察を完了状態にする
- cancelObservation: 経過観察をキャンセル状態にする

要件: Health Observation Management機能の全要件
"""

import json
import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

# ログ設定
log_level = os.environ.get("LOG_LEVEL", "INFO")
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, log_level.upper()))

# DynamoDBクライアント（指数バックオフ付き再試行設定）
from botocore.config import Config

config = Config(
    retries={
        "max_attempts": 3,
        "mode": "standard",  # 指数バックオフ
    }
)

dynamodb = boto3.resource("dynamodb", config=config)
table_name = os.environ.get("OBSERVATIONS_TABLE_NAME", "healthmate-observations")
table = dynamodb.Table(table_name)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数のエントリーポイント
    
    AgentCore Gateway（MCP）から呼び出され、健康経過観察のCRUD操作を実行します。
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
        # eventには直接パラメータが含まれる
        parameters = event.copy()
        
        # userIdの検証（必須）
        if "userId" not in parameters:
            raise ValueError("userId is required for all health observation operations")
        
        user_id = parameters["userId"]
        logger.info(f"Processing request for userId: {user_id}")
        
        # contextからツール名を取得
        tool_name = context.client_context.custom['bedrockAgentCoreToolName'].split('___', 1)[-1]
        logger.debug(f"Tool name from context: {tool_name}")
        
        # ツールに基づいて関数を実行
        if tool_name == "AddObservation":
            result = add_observation(parameters)
        elif tool_name == "GetObservation":
            result = get_observation(parameters)
        elif tool_name == "GetObservationsInRange":
            result = get_observations_in_range(parameters)
        elif tool_name == "GetObservationsInProgress":
            result = get_observations_in_progress(parameters)
        elif tool_name == "UpdateObservation":
            result = update_observation(parameters)
        elif tool_name == "AddObservationProgress":
            result = add_observation_progress(parameters)
        elif tool_name == "CompleteObservation":
            result = complete_observation(parameters)
        elif tool_name == "CancelObservation":
            result = cancel_observation(parameters)
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


def add_observation(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    新しい経過観察記録を作成
    
    Args:
        parameters: userId, title, description, priority, startDatetime, 
                   targetDatetime, frequency, checkItems

    Returns:
        作成された経過観察記録

    Raises:
        ValueError: 必須パラメータが不足している場合、または検証に失敗した場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    title = parameters.get("title")
    description = parameters.get("description")
    priority = parameters.get("priority")
    start_datetime = parameters.get("startDatetime")
    target_datetime = parameters.get("targetDatetime")
    frequency = parameters.get("frequency")
    check_items = parameters.get("checkItems")

    # 必須パラメータの検証
    if not user_id:
        raise ValueError("userId is required")
    if not title:
        raise ValueError("title is required")
    if not description:
        raise ValueError("description is required")
    if priority is None:
        raise ValueError("priority is required")
    if not start_datetime:
        raise ValueError("startDatetime is required")
    if not target_datetime:
        raise ValueError("targetDatetime is required")
    if not frequency:
        raise ValueError("frequency is required")
    if not check_items or not isinstance(check_items, list) or len(check_items) == 0:
        raise ValueError("checkItems is required and must be a non-empty list")

    # 入力データの検証
    validate_priority(priority)
    validate_iso8601_datetime(start_datetime)
    validate_iso8601_datetime(target_datetime)
    validate_iso8601_duration(frequency)

    # 開始日時と目標日時の論理チェック
    start_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
    target_dt = datetime.fromisoformat(target_datetime.replace('Z', '+00:00'))
    
    if start_dt >= target_dt:
        raise ValueError("targetDatetime must be after startDatetime")

    logger.info(f"Creating new observation for user: {user_id}, title: {title}")

    try:
        # observationIdを生成
        observation_id = generate_observation_id(user_id, start_datetime)
        
        # 現在時刻
        now = datetime.now(timezone.utc).isoformat()

        # DynamoDBアイテムを構築
        item = {
            "userId": user_id,
            "observationId": observation_id,
            "title": title,
            "description": description,
            "priority": priority,
            "status": "IN_PROGRESS",
            "in_progress": "TRUE",  # LSI用（スパースインデックス）
            "startDatetime": start_datetime,
            "targetDatetime": target_datetime,
            "frequency": frequency,
            "checkItems": check_items,
            "progressLogs": [],  # 空のリストで初期化
            "createdAt": now,
            "updatedAt": now
        }

        # DynamoDBに保存
        table.put_item(Item=item)
        
        logger.info(f"Observation created successfully: {observation_id}")
        
        # レスポンス用のデータを構築（conclusionは含めない）
        observation_response = {
            "userId": user_id,
            "observationId": observation_id,
            "title": title,
            "description": description,
            "priority": priority,
            "status": "IN_PROGRESS",
            "startDatetime": start_datetime,
            "targetDatetime": target_datetime,
            "frequency": frequency,
            "checkItems": check_items,
            "progressLogs": [],
            "createdAt": now,
            "updatedAt": now
        }
        
        return {
            "success": True,
            "observationId": observation_id,
            "message": "経過観察記録を作成しました",
            "observation": observation_response
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in add_observation: {error_code} - {str(e)}")
        raise


def get_observation(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定された経過観察記録を取得
    
    Args:
        parameters: userId, observationId

    Returns:
        経過観察記録の詳細

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    observation_id = parameters.get("observationId")

    # 必須パラメータの検証
    if not user_id:
        raise ValueError("userId is required")
    if not observation_id:
        raise ValueError("observationId is required")

    logger.info(f"Retrieving observation: {observation_id} for user: {user_id}")

    try:
        # DynamoDBから記録を取得
        response = table.get_item(
            Key={
                "userId": user_id,
                "observationId": observation_id
            }
        )

        if "Item" in response:
            observation = response["Item"]
            logger.info(f"Observation retrieved successfully: {observation_id}")
            
            # レスポンス用のデータを構築
            observation_response = {
                "userId": observation.get("userId"),
                "observationId": observation.get("observationId"),
                "title": observation.get("title"),
                "description": observation.get("description"),
                "priority": observation.get("priority"),
                "status": observation.get("status"),
                "startDatetime": observation.get("startDatetime"),
                "targetDatetime": observation.get("targetDatetime"),
                "frequency": observation.get("frequency"),
                "checkItems": observation.get("checkItems", []),
                "progressLogs": observation.get("progressLogs", []),
                "createdAt": observation.get("createdAt"),
                "updatedAt": observation.get("updatedAt")
            }
            
            # conclusionが存在する場合のみ含める（完了・キャンセル時）
            if "conclusion" in observation:
                observation_response["conclusion"] = observation["conclusion"]
            
            return {
                "success": True,
                "observation": observation_response
            }
        else:
            logger.info(f"Observation not found: {observation_id} for user: {user_id}")
            return {
                "success": False,
                "message": "経過観察記録が見つかりません",
                "observationId": observation_id
            }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_observation: {error_code} - {str(e)}")
        raise


def get_observations_in_range(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定期間内の経過観察記録を効率的に取得
    
    Args:
        parameters: userId, startDate, endDate

    Returns:
        期間内の経過観察記録リスト

    Raises:
        ValueError: 必須パラメータが不足している場合、または日付検証に失敗した場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    start_date = parameters.get("startDate")
    end_date = parameters.get("endDate")

    # 必須パラメータの検証
    if not user_id:
        raise ValueError("userId is required")
    if not start_date:
        raise ValueError("startDate is required")
    if not end_date:
        raise ValueError("endDate is required")

    # 日付形式の検証
    validate_date_format(start_date)
    validate_date_format(end_date)

    # 日付範囲の論理チェック
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    if start_date_obj > end_date_obj:
        raise ValueError("startDate must be before or equal to endDate")

    logger.info(f"Retrieving observations in range: {start_date} to {end_date} for user: {user_id}")

    try:
        observations = []
        current_date = start_date_obj
        
        # 日付範囲の各日に対して個別クエリを実行
        while current_date <= end_date_obj:
            date_str = current_date.strftime('%Y-%m-%d')
            
            logger.debug(f"Querying observations for date: {date_str}")
            
            # その日に開始された経過観察記録を取得
            response = table.query(
                KeyConditionExpression=Key('userId').eq(user_id) & 
                                      Key('observationId').begins_with(f'OBS#{date_str}')
            )
            
            # 結果をリストに追加
            if response['Items']:
                observations.extend(response['Items'])
                logger.debug(f"Found {len(response['Items'])} observations for date: {date_str}")
            
            # 次の日に進む
            current_date += timedelta(days=1)
        
        logger.info(f"Retrieved {len(observations)} observations in total")
        
        # レスポンス用のデータを構築
        observations_response = []
        for observation in observations:
            observation_data = {
                "userId": observation.get("userId"),
                "observationId": observation.get("observationId"),
                "title": observation.get("title"),
                "description": observation.get("description"),
                "priority": observation.get("priority"),
                "status": observation.get("status"),
                "startDatetime": observation.get("startDatetime"),
                "targetDatetime": observation.get("targetDatetime"),
                "frequency": observation.get("frequency"),
                "checkItems": observation.get("checkItems", []),
                "progressLogs": observation.get("progressLogs", []),
                "createdAt": observation.get("createdAt"),
                "updatedAt": observation.get("updatedAt")
            }
            
            # conclusionが存在する場合のみ含める
            if "conclusion" in observation:
                observation_data["conclusion"] = observation["conclusion"]
            
            observations_response.append(observation_data)
        
        # 開始日時でソート（古い順）
        observations_response.sort(key=lambda x: x["startDatetime"])
        
        return {
            "success": True,
            "observations": observations_response,
            "count": len(observations_response),
            "dateRange": {
                "startDate": start_date,
                "endDate": end_date
            }
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_observations_in_range: {error_code} - {str(e)}")
        raise


def get_observations_in_progress(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    進行中の経過観察記録を取得
    
    LSI (InProgressIndex) を使用してIN_PROGRESSステータスの記録のみを効率的に取得します。
    
    Args:
        parameters: userId

    Returns:
        進行中の経過観察記録リスト

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")

    # 必須パラメータの検証
    if not user_id:
        raise ValueError("userId is required")

    logger.info(f"Retrieving in-progress observations for user: {user_id}")

    try:
        # LSI (InProgressIndex) を使用して進行中の記録を取得
        response = table.query(
            IndexName="InProgressIndex",
            KeyConditionExpression=Key('userId').eq(user_id) & 
                                  Key('in_progress').eq("TRUE")
        )

        observations = response.get('Items', [])
        logger.info(f"Retrieved {len(observations)} in-progress observations")
        
        # レスポンス用のデータを構築
        observations_response = []
        for observation in observations:
            observation_data = {
                "userId": observation.get("userId"),
                "observationId": observation.get("observationId"),
                "title": observation.get("title"),
                "description": observation.get("description"),
                "priority": observation.get("priority"),
                "status": observation.get("status"),
                "startDatetime": observation.get("startDatetime"),
                "targetDatetime": observation.get("targetDatetime"),
                "frequency": observation.get("frequency"),
                "checkItems": observation.get("checkItems", []),
                "progressLogs": observation.get("progressLogs", []),
                "createdAt": observation.get("createdAt"),
                "updatedAt": observation.get("updatedAt")
            }
            
            observations_response.append(observation_data)
        
        # 開始日時でソート（古い順）
        observations_response.sort(key=lambda x: x["startDatetime"])
        
        return {
            "success": True,
            "observations": observations_response,
            "count": len(observations_response)
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_observations_in_progress: {error_code} - {str(e)}")
        raise


def update_observation(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    経過観察記録を差分更新
    
    指定されたフィールドのみを更新し、全体置き換えは行いません。
    updatedAtは自動的に現在時刻に更新されます。
    
    Args:
        parameters: userId, observationId, その他の更新フィールド
                   (title, description, priority, targetDatetime, frequency, checkItems)

    Returns:
        更新された経過観察記録

    Raises:
        ValueError: 必須パラメータが不足している場合、または検証に失敗した場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    observation_id = parameters.get("observationId")

    # 必須パラメータの検証
    if not user_id:
        raise ValueError("userId is required")
    if not observation_id:
        raise ValueError("observationId is required")

    # 更新可能なフィールドを定義
    updatable_fields = {
        "title": str,
        "description": str,
        "priority": int,
        "targetDatetime": str,
        "frequency": str,
        "checkItems": list
    }

    # 更新するフィールドを抽出
    update_fields = {}
    for field, field_type in updatable_fields.items():
        if field in parameters:
            value = parameters[field]
            if value is not None:  # None値は無視
                # 型チェック
                if not isinstance(value, field_type):
                    raise ValueError(f"{field}は{field_type.__name__}型で入力してください")
                update_fields[field] = value

    # 更新フィールドが存在しない場合はエラー
    if not update_fields:
        raise ValueError("更新するフィールドが指定されていません")

    # 入力データの検証
    if "priority" in update_fields:
        validate_priority(update_fields["priority"])
    if "targetDatetime" in update_fields:
        validate_iso8601_datetime(update_fields["targetDatetime"])
    if "frequency" in update_fields:
        validate_iso8601_duration(update_fields["frequency"])
    if "checkItems" in update_fields:
        if not isinstance(update_fields["checkItems"], list) or len(update_fields["checkItems"]) == 0:
            raise ValueError("checkItemsは空でないリストで入力してください")

    logger.info(f"Updating observation: {observation_id} for user: {user_id}, fields: {list(update_fields.keys())}")

    try:
        # 現在時刻
        now = datetime.now(timezone.utc).isoformat()
        
        # DynamoDB UpdateExpressionを構築
        update_expression_parts = []
        expression_attribute_names = {}
        expression_attribute_values = {}
        
        # 各更新フィールドを処理
        for field, value in update_fields.items():
            attr_name = f"#{field}"
            attr_value = f":{field}"
            
            update_expression_parts.append(f"{attr_name} = {attr_value}")
            expression_attribute_names[attr_name] = field
            expression_attribute_values[attr_value] = value
        
        # updatedAtを追加
        update_expression_parts.append("#updatedAt = :updatedAt")
        expression_attribute_names["#updatedAt"] = "updatedAt"
        expression_attribute_values[":updatedAt"] = now
        
        update_expression = "SET " + ", ".join(update_expression_parts)
        
        # targetDatetimeが更新される場合の論理チェック
        if "targetDatetime" in update_fields:
            # 既存の記録を取得してstartDatetimeと比較
            existing_response = table.get_item(
                Key={
                    "userId": user_id,
                    "observationId": observation_id
                }
            )
            
            if "Item" not in existing_response:
                raise ValueError("指定された経過観察記録が見つかりません")
            
            existing_item = existing_response["Item"]
            start_datetime = existing_item.get("startDatetime")
            
            if start_datetime:
                start_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
                target_dt = datetime.fromisoformat(update_fields["targetDatetime"].replace('Z', '+00:00'))
                
                if start_dt >= target_dt:
                    raise ValueError("targetDatetimeはstartDatetimeより後の時刻である必要があります")

        # DynamoDBで差分更新を実行
        response = table.update_item(
            Key={
                "userId": user_id,
                "observationId": observation_id
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression="attribute_exists(userId) AND attribute_exists(observationId)",
            ReturnValues="ALL_NEW"
        )

        updated_item = response["Attributes"]
        logger.info(f"Observation updated successfully: {observation_id}")
        
        # レスポンス用のデータを構築
        observation_response = {
            "userId": updated_item.get("userId"),
            "observationId": updated_item.get("observationId"),
            "title": updated_item.get("title"),
            "description": updated_item.get("description"),
            "priority": updated_item.get("priority"),
            "status": updated_item.get("status"),
            "startDatetime": updated_item.get("startDatetime"),
            "targetDatetime": updated_item.get("targetDatetime"),
            "frequency": updated_item.get("frequency"),
            "checkItems": updated_item.get("checkItems", []),
            "progressLogs": updated_item.get("progressLogs", []),
            "createdAt": updated_item.get("createdAt"),
            "updatedAt": updated_item.get("updatedAt")
        }
        
        # conclusionが存在する場合のみ含める
        if "conclusion" in updated_item:
            observation_response["conclusion"] = updated_item["conclusion"]
        
        return {
            "success": True,
            "message": "経過観察記録を更新しました",
            "observation": observation_response
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        
        if error_code == "ConditionalCheckFailedException":
            logger.warning(f"Observation not found for update: {observation_id} for user: {user_id}")
            raise ValueError("指定された経過観察記録が見つかりません")
        
        logger.error(f"DynamoDB error in update_observation: {error_code} - {str(e)}")
        raise


def add_observation_progress(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    経過観察の進捗ログを追加
    
    既存のprogressLogsリストに新しい進捗ログを追加します。
    recordedAtは自動的に現在時刻に設定されます。
    
    Args:
        parameters: userId, observationId, date, note

    Returns:
        更新された経過観察記録

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    observation_id = parameters.get("observationId")
    date = parameters.get("date")
    note = parameters.get("note")

    # 必須パラメータの検証
    if not user_id:
        raise ValueError("userId is required")
    if not observation_id:
        raise ValueError("observationId is required")
    if not date:
        raise ValueError("date is required")
    if not note:
        raise ValueError("note is required")

    # 日付形式の検証
    validate_date_format(date)

    logger.info(f"Adding progress log to observation: {observation_id} for user: {user_id}, date: {date}")

    try:
        # 現在時刻（recordedAt用）
        now = datetime.now(timezone.utc).isoformat()
        
        # 新しい進捗ログエントリを作成
        new_progress_log = {
            "date": date,
            "note": note,
            "recordedAt": now
        }

        # DynamoDBでprogressLogsリストに新しいエントリを追加
        response = table.update_item(
            Key={
                "userId": user_id,
                "observationId": observation_id
            },
            UpdateExpression="SET progressLogs = list_append(if_not_exists(progressLogs, :empty_list), :new_log), updatedAt = :updatedAt",
            ExpressionAttributeValues={
                ":new_log": [new_progress_log],
                ":empty_list": [],
                ":updatedAt": now
            },
            ConditionExpression="attribute_exists(userId) AND attribute_exists(observationId)",
            ReturnValues="ALL_NEW"
        )

        updated_item = response["Attributes"]
        logger.info(f"Progress log added successfully to observation: {observation_id}")
        
        # レスポンス用のデータを構築
        observation_response = {
            "userId": updated_item.get("userId"),
            "observationId": updated_item.get("observationId"),
            "title": updated_item.get("title"),
            "description": updated_item.get("description"),
            "priority": updated_item.get("priority"),
            "status": updated_item.get("status"),
            "startDatetime": updated_item.get("startDatetime"),
            "targetDatetime": updated_item.get("targetDatetime"),
            "frequency": updated_item.get("frequency"),
            "checkItems": updated_item.get("checkItems", []),
            "progressLogs": updated_item.get("progressLogs", []),
            "createdAt": updated_item.get("createdAt"),
            "updatedAt": updated_item.get("updatedAt")
        }
        
        # conclusionが存在する場合のみ含める
        if "conclusion" in updated_item:
            observation_response["conclusion"] = updated_item["conclusion"]
        
        return {
            "success": True,
            "message": "進捗ログを追加しました",
            "observation": observation_response,
            "addedProgressLog": new_progress_log
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        
        if error_code == "ConditionalCheckFailedException":
            logger.warning(f"Observation not found for progress log addition: {observation_id} for user: {user_id}")
            raise ValueError("指定された経過観察記録が見つかりません")
        
        logger.error(f"DynamoDB error in add_observation_progress: {error_code} - {str(e)}")
        raise


def complete_observation(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    経過観察を完了状態にする
    
    ステータスをCOMPLETEDに変更し、conclusionを設定し、
    LSI用のin_progress属性を削除します。
    
    Args:
        parameters: userId, observationId, conclusion

    Returns:
        完了した経過観察記録

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    observation_id = parameters.get("observationId")
    conclusion = parameters.get("conclusion")

    # 必須パラメータの検証
    if not user_id:
        raise ValueError("userId is required")
    if not observation_id:
        raise ValueError("observationId is required")
    if not conclusion:
        raise ValueError("conclusion is required")

    logger.info(f"Completing observation: {observation_id} for user: {user_id}")

    try:
        # 現在時刻
        now = datetime.now(timezone.utc).isoformat()

        # DynamoDBで経過観察を完了状態に更新
        # ステータスをCOMPLETEDに変更、conclusionを設定、in_progress属性を削除
        response = table.update_item(
            Key={
                "userId": user_id,
                "observationId": observation_id
            },
            UpdateExpression="SET #status = :completed_status, conclusion = :conclusion, updatedAt = :updatedAt REMOVE in_progress",
            ExpressionAttributeNames={
                "#status": "status"  # statusは予約語のため#を使用
            },
            ExpressionAttributeValues={
                ":completed_status": "COMPLETED",
                ":conclusion": conclusion,
                ":updatedAt": now,
                ":in_progress_status": "IN_PROGRESS"
            },
            ConditionExpression="attribute_exists(userId) AND attribute_exists(observationId) AND #status = :in_progress_status",
            ReturnValues="ALL_NEW"
        )

        updated_item = response["Attributes"]
        logger.info(f"Observation completed successfully: {observation_id}")
        
        # レスポンス用のデータを構築
        observation_response = {
            "userId": updated_item.get("userId"),
            "observationId": updated_item.get("observationId"),
            "title": updated_item.get("title"),
            "description": updated_item.get("description"),
            "priority": updated_item.get("priority"),
            "status": updated_item.get("status"),
            "startDatetime": updated_item.get("startDatetime"),
            "targetDatetime": updated_item.get("targetDatetime"),
            "frequency": updated_item.get("frequency"),
            "checkItems": updated_item.get("checkItems", []),
            "progressLogs": updated_item.get("progressLogs", []),
            "conclusion": updated_item.get("conclusion"),
            "createdAt": updated_item.get("createdAt"),
            "updatedAt": updated_item.get("updatedAt")
        }
        
        return {
            "success": True,
            "message": "経過観察を完了しました",
            "observation": observation_response
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        
        if error_code == "ConditionalCheckFailedException":
            logger.warning(f"Observation not found or not in progress for completion: {observation_id} for user: {user_id}")
            raise ValueError("指定された経過観察記録が見つからないか、既に完了またはキャンセルされています")
        
        logger.error(f"DynamoDB error in complete_observation: {error_code} - {str(e)}")
        raise


def cancel_observation(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    経過観察をキャンセル状態にする
    
    ステータスをCANCELLEDに変更し、conclusionにキャンセル理由を設定し、
    LSI用のin_progress属性を削除します。
    
    Args:
        parameters: userId, observationId, conclusion

    Returns:
        キャンセルされた経過観察記録

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    observation_id = parameters.get("observationId")
    conclusion = parameters.get("conclusion")

    # 必須パラメータの検証
    if not user_id:
        raise ValueError("userId is required")
    if not observation_id:
        raise ValueError("observationId is required")
    if not conclusion:
        raise ValueError("conclusion is required")

    logger.info(f"Cancelling observation: {observation_id} for user: {user_id}")

    try:
        # 現在時刻
        now = datetime.now(timezone.utc).isoformat()

        # DynamoDBで経過観察をキャンセル状態に更新
        # ステータスをCANCELLEDに変更、conclusionにキャンセル理由を設定、in_progress属性を削除
        response = table.update_item(
            Key={
                "userId": user_id,
                "observationId": observation_id
            },
            UpdateExpression="SET #status = :cancelled_status, conclusion = :conclusion, updatedAt = :updatedAt REMOVE in_progress",
            ExpressionAttributeNames={
                "#status": "status"  # statusは予約語のため#を使用
            },
            ExpressionAttributeValues={
                ":cancelled_status": "CANCELLED",
                ":conclusion": conclusion,
                ":updatedAt": now,
                ":in_progress_status": "IN_PROGRESS"
            },
            ConditionExpression="attribute_exists(userId) AND attribute_exists(observationId) AND #status = :in_progress_status",
            ReturnValues="ALL_NEW"
        )

        updated_item = response["Attributes"]
        logger.info(f"Observation cancelled successfully: {observation_id}")
        
        # レスポンス用のデータを構築
        observation_response = {
            "userId": updated_item.get("userId"),
            "observationId": updated_item.get("observationId"),
            "title": updated_item.get("title"),
            "description": updated_item.get("description"),
            "priority": updated_item.get("priority"),
            "status": updated_item.get("status"),
            "startDatetime": updated_item.get("startDatetime"),
            "targetDatetime": updated_item.get("targetDatetime"),
            "frequency": updated_item.get("frequency"),
            "checkItems": updated_item.get("checkItems", []),
            "progressLogs": updated_item.get("progressLogs", []),
            "conclusion": updated_item.get("conclusion"),
            "createdAt": updated_item.get("createdAt"),
            "updatedAt": updated_item.get("updatedAt")
        }
        
        return {
            "success": True,
            "message": "経過観察をキャンセルしました",
            "observation": observation_response
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        
        if error_code == "ConditionalCheckFailedException":
            logger.warning(f"Observation not found or not in progress for cancellation: {observation_id} for user: {user_id}")
            raise ValueError("指定された経過観察記録が見つからないか、既に完了またはキャンセルされています")
        
        logger.error(f"DynamoDB error in cancel_observation: {error_code} - {str(e)}")
        raise


def validate_iso8601_datetime(datetime_str: str) -> None:
    """
    ISO 8601形式の日時文字列を検証する
    
    Args:
        datetime_str: ISO 8601形式の日時文字列
        
    Raises:
        ValueError: 無効な日時形式の場合
    """
    if not isinstance(datetime_str, str):
        raise ValueError("日時は文字列で入力してください")
    
    try:
        # ISO 8601形式の解析を試行
        datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError("日時はISO 8601形式（例: 2025-12-28T00:00:00Z）で入力してください")


def validate_iso8601_duration(duration_str: str) -> None:
    """
    ISO 8601 Duration形式の文字列を検証する
    
    Args:
        duration_str: ISO 8601 Duration形式の文字列
        
    Raises:
        ValueError: 無効なDuration形式の場合
    """
    if not isinstance(duration_str, str):
        raise ValueError("頻度は文字列で入力してください")
    
    # 基本的なISO 8601 Duration形式のパターンチェック
    if not re.match(r'^P(?:\d+Y)?(?:\d+M)?(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?(?:\d+S)?)?$', duration_str):
        raise ValueError("頻度はISO 8601 Duration形式（例: P1D, PT1H）で入力してください")


def validate_priority(priority: int) -> None:
    """
    優先度の値を検証する
    
    Args:
        priority: 優先度（1-5の範囲）
        
    Raises:
        ValueError: 無効な優先度の場合
    """
    if not isinstance(priority, int):
        raise ValueError("優先度は整数で入力してください")
    
    if priority < 1 or priority > 5:
        raise ValueError("優先度は1から5の範囲で入力してください")


def validate_status(status: str) -> None:
    """
    ステータスの値を検証する
    
    Args:
        status: ステータス値
        
    Raises:
        ValueError: 無効なステータスの場合
    """
    valid_statuses = ["IN_PROGRESS", "COMPLETED", "CANCELLED"]
    
    if not isinstance(status, str):
        raise ValueError("ステータスは文字列で入力してください")
    
    if status not in valid_statuses:
        raise ValueError(f"ステータスは{valid_statuses}のいずれかで入力してください")


def validate_date_format(date_str: str) -> None:
    """
    YYYY-MM-DD形式の日付文字列を検証する
    
    Args:
        date_str: YYYY-MM-DD形式の日付文字列
        
    Raises:
        ValueError: 無効な日付形式の場合
    """
    if not isinstance(date_str, str):
        raise ValueError("日付は文字列で入力してください")
    
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        raise ValueError("日付はYYYY-MM-DD形式で入力してください")
    
    try:
        # 日付の妥当性チェック
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        raise ValueError("無効な日付です。正しい日付を入力してください")


def generate_observation_id(user_id: str, start_datetime: str) -> str:
    """
    経過観察IDを生成
    
    Format: OBS#{YYYY-MM-DD}-{sequential_number}
    Example: OBS#2025-12-28-001
    
    Args:
        user_id: ユーザーID
        start_datetime: 経過観察開始日時 (ISO 8601形式)
    
    Returns:
        生成されたobservationId
        
    Raises:
        ValueError: 無効な日時形式の場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    logger.info(f"Generating observation ID for user: {user_id}, start_datetime: {start_datetime}")
    
    # 開始日時の検証
    validate_iso8601_datetime(start_datetime)
    
    try:
        # 開始日時から日付部分を抽出
        start_date = datetime.fromisoformat(start_datetime.replace('Z', '+00:00')).date()
        date_str = start_date.strftime("%Y-%m-%d")
        
        logger.debug(f"Extracted date: {date_str}")
        
        # 同じ日付で始まるobservationIdの数を確認して連番を決定
        response = table.query(
            KeyConditionExpression=Key('userId').eq(user_id) & 
                                  Key('observationId').begins_with(f'OBS#{date_str}')
        )
        
        # 連番を決定（001から開始）
        sequence_number = len(response['Items']) + 1
        sequence_str = f"{sequence_number:03d}"
        
        observation_id = f"OBS#{date_str}-{sequence_str}"
        
        logger.info(f"Generated observation ID: {observation_id}")
        return observation_id
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in generate_observation_id: {error_code} - {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in generate_observation_id: {str(e)}")
        raise ValueError(f"observationId生成中にエラーが発生しました: {str(e)}")