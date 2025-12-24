"""
UserLambda - ユーザー情報管理Lambda関数

HealthManagerMCP（Healthmateエコシステム）のユーザー情報管理を担当。
AgentCore Gateway（MCP）から呼び出され、DynamoDBでユーザー情報のCRUD操作を実行します。

機能:
- addUser: 新しいユーザー情報を作成
- updateUser: 既存のユーザー情報を更新
- getUser: ユーザー情報を取得

要件: 要件2（ユーザー情報管理）、要件11（データ永続化）、要件12（エラーハンドリング）、要件13（ロギング）
"""

import json
import os
import re
import logging
from datetime import datetime, timezone, date
from typing import Any, Dict
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
table_name = os.environ.get("USERS_TABLE_NAME", "healthmate-users")
table = dynamodb.Table(table_name)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数のエントリーポイント
    
    AgentCore Gateway（MCP）から呼び出され、ユーザー情報のCRUD操作を実行します。
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
            raise ValueError("userId is required for all user operations")
        
        user_id = parameters["userId"]
        logger.info(f"Processing request for userId: {user_id}")
        
        # contextからツール名を取得
        tool_name = context.client_context.custom['bedrockAgentCoreToolName'].split('___', 1)[-1]
        logger.debug(f"Tool name from context: {tool_name}")
        
        # ツールに基づいて関数を実行
        if tool_name == "AddUser":
            result = add_user(parameters)
        elif tool_name == "UpdateUser":
            result = update_user(parameters)
        elif tool_name == "GetUser":
            result = get_user(parameters)
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


def add_user(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    新しいユーザー情報を作成（upsert操作）
    
    既存ユーザーが存在する場合は更新、存在しない場合は新規作成を行います。

    Args:
        parameters: userId, username, email(optional), dateOfBirth(optional)

    Returns:
        作成/更新されたユーザー情報

    Raises:
        ValueError: 必須パラメータが不足している場合、または生年月日の検証に失敗した場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    username = parameters.get("username")
    email = parameters.get("email", "")
    date_of_birth = parameters.get("dateOfBirth")

    if not user_id:
        raise ValueError("userId is required")
    if not username:
        raise ValueError("username is required")

    # 生年月日のバリデーション（提供された場合のみ）
    if date_of_birth is not None:
        validate_date_of_birth(date_of_birth)
        logger.debug(f"Date of birth validated: {date_of_birth}")

    logger.info(f"Adding/updating user: {user_id}, username: {username}")

    now = datetime.now(timezone.utc).isoformat()

    # DynamoDBにupsert（存在しない場合は作成、存在する場合は更新）
    item = {
        "userId": user_id,
        "username": username,
        "email": email,
        "createdAt": now,
        "lastLoginAt": now,
    }

    # 生年月日が提供された場合のみ追加
    if date_of_birth is not None:
        item["dateOfBirth"] = date_of_birth

    try:
        # 既存ユーザーの確認
        existing_response = table.get_item(Key={"userId": user_id})
        
        if "Item" in existing_response:
            # 既存ユーザーの場合は更新
            existing_item = existing_response["Item"]
            item["createdAt"] = existing_item.get("createdAt", now)  # 作成日時は保持
            logger.info(f"Updating existing user: {user_id}")
            operation = "updated"
        else:
            # 新規ユーザーの場合
            logger.info(f"Creating new user: {user_id}")
            operation = "created"

        # アイテムを保存
        table.put_item(Item=item)
        
        logger.info(f"User {operation} successfully: {user_id}")
        
        # レスポンス用のユーザー情報を構築
        user_response = {
            "userId": user_id,
            "username": username,
            "email": email,
            "createdAt": item["createdAt"],
            "lastLoginAt": item["lastLoginAt"]
        }
        
        # 生年月日が存在する場合のみレスポンスに含める
        if date_of_birth is not None:
            user_response["dateOfBirth"] = date_of_birth
        
        return {
            "success": True,
            "userId": user_id,
            "message": f"ユーザー情報を{operation}しました",
            "user": user_response
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in add_user: {error_code} - {str(e)}")
        raise


def update_user(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    既存のユーザー情報を部分的に更新

    Args:
        parameters: userId, username(optional), email(optional), dateOfBirth(optional), lastLoginAt(optional)

    Returns:
        更新結果

    Raises:
        ValueError: 必須パラメータが不足している場合、更新対象フィールドがない場合、または生年月日の検証に失敗した場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    username = parameters.get("username")
    email = parameters.get("email")
    date_of_birth = parameters.get("dateOfBirth")
    last_login_at = parameters.get("lastLoginAt")

    if not user_id:
        raise ValueError("userId is required")

    logger.info(f"Updating user: {user_id}")

    # 更新式を構築
    update_expression_parts = []
    remove_expression_parts = []
    expression_attribute_values = {}

    if username is not None:
        update_expression_parts.append("username = :username")
        expression_attribute_values[":username"] = username
        logger.debug(f"Updating username to: {username}")

    if email is not None:
        update_expression_parts.append("email = :email")
        expression_attribute_values[":email"] = email
        logger.debug(f"Updating email to: {email}")

    # 生年月日の処理
    if date_of_birth is not None:
        if date_of_birth == "":  # 空文字列の場合は削除
            remove_expression_parts.append("dateOfBirth")
            logger.debug("Removing dateOfBirth field")
        else:
            # 生年月日の検証
            validate_date_of_birth(date_of_birth)
            update_expression_parts.append("dateOfBirth = :dateOfBirth")
            expression_attribute_values[":dateOfBirth"] = date_of_birth
            logger.debug(f"Updating dateOfBirth to: {date_of_birth}")

    if last_login_at is not None:
        update_expression_parts.append("lastLoginAt = :lastLoginAt")
        expression_attribute_values[":lastLoginAt"] = last_login_at
        logger.debug(f"Updating lastLoginAt to: {last_login_at}")
    else:
        # lastLoginAtが指定されていない場合は現在時刻を設定
        now = datetime.now(timezone.utc).isoformat()
        update_expression_parts.append("lastLoginAt = :lastLoginAt")
        expression_attribute_values[":lastLoginAt"] = now
        logger.debug(f"Setting lastLoginAt to current time: {now}")

    # 更新対象フィールドがない場合はエラー
    if not update_expression_parts and not remove_expression_parts:
        raise ValueError("At least one field to update is required (username, email, dateOfBirth, or lastLoginAt)")

    # 更新式を構築
    update_expression = ""
    if update_expression_parts:
        update_expression += "SET " + ", ".join(update_expression_parts)
    if remove_expression_parts:
        if update_expression:
            update_expression += " "
        update_expression += "REMOVE " + ", ".join(remove_expression_parts)

    try:
        # ユーザーが存在することを確認しながら更新
        response = table.update_item(
            Key={"userId": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values if expression_attribute_values else None,
            ConditionExpression="attribute_exists(userId)",  # ユーザーが存在することを確認
            ReturnValues="ALL_NEW",
        )
        
        updated_user = response["Attributes"]
        logger.info(f"User updated successfully: {user_id}")
        
        # レスポンス用のユーザー情報を構築
        user_response = {
            "userId": updated_user.get("userId"),
            "username": updated_user.get("username"),
            "email": updated_user.get("email", ""),
            "createdAt": updated_user.get("createdAt"),
            "lastLoginAt": updated_user.get("lastLoginAt")
        }
        
        # 生年月日が存在する場合のみレスポンスに含める
        if "dateOfBirth" in updated_user:
            user_response["dateOfBirth"] = updated_user["dateOfBirth"]
        
        return {
            "success": True,
            "userId": user_id,
            "message": "ユーザー情報を更新しました",
            "user": user_response
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ConditionalCheckFailedException":
            logger.warning(f"User not found for update: {user_id}")
            raise ValueError(f"User not found: {user_id}")
        else:
            logger.error(f"DynamoDB error in update_user: {error_code} - {str(e)}")
            raise


def get_user(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    ユーザー情報を取得

    Args:
        parameters: userId

    Returns:
        ユーザー情報（生年月日が存在する場合は含める）

    Raises:
        ValueError: userIdが指定されていない場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")

    if not user_id:
        raise ValueError("userId is required")

    logger.info(f"Retrieving user: {user_id}")

    try:
        response = table.get_item(Key={"userId": user_id})

        if "Item" in response:
            user = response["Item"]
            logger.info(f"User retrieved successfully: {user_id}")
            
            # レスポンス用のユーザー情報を構築
            user_response = {
                "userId": user.get("userId"),
                "username": user.get("username"),
                "email": user.get("email", ""),
                "createdAt": user.get("createdAt"),
                "lastLoginAt": user.get("lastLoginAt"),
            }
            
            # 生年月日が存在する場合のみレスポンスに含める（後方互換性を維持）
            if "dateOfBirth" in user:
                user_response["dateOfBirth"] = user["dateOfBirth"]
                logger.debug(f"Including dateOfBirth in response: {user['dateOfBirth']}")
            else:
                logger.debug(f"No dateOfBirth found for user: {user_id}")
            
            return {
                "success": True,
                "user": user_response
            }
        else:
            logger.info(f"User not found: {user_id}")
            return {
                "success": False,
                "message": "ユーザーが見つかりません",
                "userId": user_id
            }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_user: {error_code} - {str(e)}")
        raise


def validate_date_of_birth(date_of_birth: str) -> None:
    """
    生年月日の検証を行う
    
    Args:
        date_of_birth: YYYY-MM-DD形式の日付文字列
        
    Raises:
        ValueError: 無効な日付形式または値の場合
    """
    if not isinstance(date_of_birth, str):
        raise ValueError("生年月日は文字列で入力してください")
    
    # 形式チェック（YYYY-MM-DD）
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_of_birth):
        raise ValueError("生年月日はYYYY-MM-DD形式で入力してください")
    
    try:
        # 日付の妥当性チェック
        birth_date = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
        
        # 未来の日付チェック
        if birth_date > date.today():
            raise ValueError("生年月日は過去の日付である必要があります")
        
        # 非現実的な過去の日付チェック（1900年以前）
        if birth_date.year < 1900:
            raise ValueError("生年月日は1900年以降の日付を入力してください")
            
    except ValueError as e:
        # datetime.strptimeでの解析エラーをキャッチ
        if "time data" in str(e) or "does not match format" in str(e):
            raise ValueError("無効な日付です。正しい日付を入力してください")
        # 既に適切なエラーメッセージの場合はそのまま再発生
        raise
