"""
HealthConcernLambda - 健康悩み管理Lambda関数

HealthManagerMCP（Healthmateエコシステム）の健康悩み管理を担当。
AgentCore Gateway（MCP）から呼び出され、DynamoDBで健康悩みのCRUD操作を実行します。

機能:
- AddConcern: 新しい健康悩みを作成（UUIDでconcernId生成）
- UpdateConcern: 既存の健康悩みを更新
- DeleteConcern: 指定した健康悩みを削除
- GetConcerns: ユーザーのすべての健康悩みを取得

要件: 要件1-7（健康悩み管理、データ永続化、認証・認可、MCPプロトコル準拠）
"""

import json
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
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
table_name = os.environ.get("CONCERNS_TABLE_NAME", "healthmate-concerns")
table = dynamodb.Table(table_name)

# 型定義
ConcernCategory = Literal['PHYSICAL', 'MENTAL']
ConcernStatus = Literal['ACTIVE', 'IMPROVED', 'RESOLVED']


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数のエントリーポイント
    
    AgentCore Gateway（MCP）から呼び出され、健康悩みのCRUD操作を実行します。
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
            raise ValueError("userId is required for all health concern operations")
        
        user_id = parameters["userId"]
        logger.info(f"Processing request for userId: {user_id}")
        
        # contextからツール名を取得
        tool_name = context.client_context.custom['bedrockAgentCoreToolName'].split('___', 1)[-1]
        logger.debug(f"Tool name from context: {tool_name}")
        
        # ツールに基づいて関数を実行
        if tool_name == "AddConcern":
            result = add_concern(parameters)
        elif tool_name == "UpdateConcern":
            result = update_concern(parameters)
        elif tool_name == "DeleteConcern":
            result = delete_concern(parameters)
        elif tool_name == "GetConcerns":
            result = get_concerns(parameters)
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


def add_concern(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    新しい健康悩みを作成
    
    Args:
        parameters: userId, category, description, severity(optional), 
                   triggers(optional), history(optional)

    Returns:
        作成された健康悩み情報

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    category = parameters.get("category")
    description = parameters.get("description")
    severity = parameters.get("severity", 3)  # デフォルト深刻度: 3
    triggers = parameters.get("triggers", "")
    history = parameters.get("history", "")

    # 必須パラメータの検証
    if not user_id:
        raise ValueError("userId is required")
    if not category:
        raise ValueError("category is required")
    if not description:
        raise ValueError("description is required")
    
    # categoryの検証
    valid_categories = ['PHYSICAL', 'MENTAL']
    if not isinstance(category, list) or not category:
        raise ValueError("category must be a non-empty array")
    
    for cat in category:
        if cat not in valid_categories:
            raise ValueError(f"category must contain only: {', '.join(valid_categories)}")
    
    # 重複チェック
    if len(category) != len(set(category)):
        raise ValueError("category must not contain duplicates")
    
    # severityの検証
    if not isinstance(severity, int) or severity < 1 or severity > 5:
        raise ValueError("severity must be an integer between 1 and 5")

    # UUIDでconcernIdを生成
    concern_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    logger.debug(f"Creating concern: {concern_id} for user: {user_id}")

    # DynamoDBアイテムを構築
    item = {
        "userId": user_id,
        "concernId": concern_id,
        "category": category,
        "description": description,
        "severity": severity,
        "status": "ACTIVE",  # デフォルトステータス
        "triggers": triggers,
        "history": history,
        "createdAt": now,
        "updatedAt": now,
    }

    try:
        # DynamoDBに保存
        table.put_item(Item=item)
        
        logger.info(f"Concern created successfully: {concern_id}")
        return {
            "success": True,
            "concernId": concern_id,
            "message": "健康上の悩みを作成しました",
            "concern": item
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in add_concern: {error_code} - {str(e)}")
        raise


def update_concern(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    既存の健康悩みを更新

    Args:
        parameters: userId, concernId, category(optional), description(optional), 
                   severity(optional), status(optional), triggers(optional), history(optional)

    Returns:
        更新結果

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    concern_id = parameters.get("concernId")
    category = parameters.get("category")
    description = parameters.get("description")
    severity = parameters.get("severity")
    status = parameters.get("status")
    triggers = parameters.get("triggers")
    history = parameters.get("history")

    if not user_id:
        raise ValueError("userId is required")
    if not concern_id:
        raise ValueError("concernId is required")

    logger.debug(f"Updating concern: {concern_id} for user: {user_id}")

    # 更新式を構築
    update_expression_parts = []
    expression_attribute_values = {}

    if category is not None:
        # categoryの検証
        valid_categories = ['PHYSICAL', 'MENTAL']
        if not isinstance(category, list) or not category:
            raise ValueError("category must be a non-empty array")
        
        for cat in category:
            if cat not in valid_categories:
                raise ValueError(f"category must contain only: {', '.join(valid_categories)}")
        
        # 重複チェック
        if len(category) != len(set(category)):
            raise ValueError("category must not contain duplicates")
        
        update_expression_parts.append("category = :category")
        expression_attribute_values[":category"] = category

    if description is not None:
        if not description:
            raise ValueError("description cannot be empty")
        update_expression_parts.append("description = :description")
        expression_attribute_values[":description"] = description

    if severity is not None:
        if not isinstance(severity, int) or severity < 1 or severity > 5:
            raise ValueError("severity must be an integer between 1 and 5")
        update_expression_parts.append("severity = :severity")
        expression_attribute_values[":severity"] = severity

    if status is not None:
        valid_statuses = ['ACTIVE', 'IMPROVED', 'RESOLVED']
        if status not in valid_statuses:
            raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        update_expression_parts.append("#status = :status")
        expression_attribute_values[":status"] = status

    if triggers is not None:
        update_expression_parts.append("triggers = :triggers")
        expression_attribute_values[":triggers"] = triggers

    if history is not None:
        update_expression_parts.append("history = :history")
        expression_attribute_values[":history"] = history

    # updatedAtは常に更新
    now = datetime.now(timezone.utc).isoformat()
    update_expression_parts.append("updatedAt = :updatedAt")
    expression_attribute_values[":updatedAt"] = now

    if len(update_expression_parts) == 1:  # updatedAtのみの場合
        raise ValueError("At least one field to update is required")

    update_expression = "SET " + ", ".join(update_expression_parts)
    
    # statusは予約語なので、ExpressionAttributeNamesを使用
    expression_attribute_names = {}
    if status is not None:
        expression_attribute_names["#status"] = "status"

    try:
        # 悩みが存在することを確認しながら更新
        update_params = {
            "Key": {"userId": user_id, "concernId": concern_id},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expression_attribute_values,
            "ConditionExpression": "attribute_exists(userId) AND attribute_exists(concernId)",
            "ReturnValues": "ALL_NEW",
        }
        
        if expression_attribute_names:
            update_params["ExpressionAttributeNames"] = expression_attribute_names

        response = table.update_item(**update_params)
        
        updated_concern = response["Attributes"]
        logger.info(f"Concern updated successfully: {concern_id}")
        
        return {
            "success": True,
            "concernId": concern_id,
            "message": "健康上の悩みを更新しました",
            "concern": updated_concern
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ConditionalCheckFailedException":
            logger.warning(f"Concern not found for update: {concern_id}")
            raise ValueError(f"Concern not found: {concern_id}")
        else:
            logger.error(f"DynamoDB error in update_concern: {error_code} - {str(e)}")
            raise


def delete_concern(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定した健康悩みを削除

    Args:
        parameters: userId, concernId

    Returns:
        削除結果

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    concern_id = parameters.get("concernId")

    if not user_id:
        raise ValueError("userId is required")
    if not concern_id:
        raise ValueError("concernId is required")

    logger.debug(f"Deleting concern: {concern_id} for user: {user_id}")

    try:
        # 悩みが存在することを確認しながら削除
        response = table.delete_item(
            Key={"userId": user_id, "concernId": concern_id},
            ConditionExpression="attribute_exists(userId) AND attribute_exists(concernId)",
            ReturnValues="ALL_OLD"
        )
        
        deleted_concern = response.get("Attributes")
        logger.info(f"Concern deleted successfully: {concern_id}")
        
        return {
            "success": True,
            "concernId": concern_id,
            "message": "健康上の悩みを削除しました",
            "deletedConcern": deleted_concern
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ConditionalCheckFailedException":
            logger.warning(f"Concern not found for deletion: {concern_id}")
            raise ValueError(f"Concern not found: {concern_id}")
        else:
            logger.error(f"DynamoDB error in delete_concern: {error_code} - {str(e)}")
            raise


def get_concerns(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    ユーザーのすべての健康悩みを取得

    Args:
        parameters: userId, status(optional), category(optional)

    Returns:
        健康悩みのリスト（createdAtの降順でソート）

    Raises:
        ValueError: userIdが指定されていない場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    status_filter = parameters.get("status")
    category_filter = parameters.get("category")

    if not user_id:
        raise ValueError("userId is required")

    logger.debug(f"Retrieving concerns for user: {user_id}")

    try:
        # userIdでクエリしてすべての悩みを取得
        response = table.query(
            KeyConditionExpression="userId = :userId",
            ExpressionAttributeValues={":userId": user_id},
            ScanIndexForward=False  # createdAtの降順（新しい順）
        )
        
        concerns = response.get("Items", [])
        
        # フィルタリング処理
        if status_filter:
            valid_statuses = ['ACTIVE', 'IMPROVED', 'RESOLVED']
            if status_filter not in valid_statuses:
                raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
            concerns = [c for c in concerns if c.get("status") == status_filter]
        
        if category_filter:
            valid_categories = ['PHYSICAL', 'MENTAL']
            if category_filter not in valid_categories:
                raise ValueError(f"category must be one of: {', '.join(valid_categories)}")
            concerns = [c for c in concerns if category_filter in c.get("category", [])]
        
        # createdAtでソート（降順）
        concerns.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        
        logger.info(f"Retrieved {len(concerns)} concerns for user: {user_id}")
        
        return {
            "success": True,
            "userId": user_id,
            "concerns": concerns,
            "count": len(concerns)
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_concerns: {error_code} - {str(e)}")
        raise