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
from datetime import datetime, timezone
from typing import Any, Dict
import boto3
from botocore.exceptions import ClientError

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
    print(f"[UserLambda] Received event: {json.dumps(event, default=str)}")

    try:
        # AgentCore Gateway（MCP）形式のイベントを処理
        # eventには直接パラメータが含まれる
        parameters = event.copy()
        
        # userIdの検証（必須）
        if "userId" not in parameters:
            raise ValueError("userId is required for all user operations")
        
        user_id = parameters["userId"]
        print(f"[UserLambda] Processing request for userId: {user_id}")
        
        # MCPツール名を推測（パラメータから判断）
        if "username" in parameters and len([k for k in parameters.keys() if k != "userId"]) >= 1:
            # usernameが含まれている場合はAddUserまたはUpdateUser
            # 既存ユーザーの確認は不要なので、常にupsert（AddUser）として扱う
            tool_name = "AddUser"
        elif any(key in parameters for key in ["username", "email", "lastLoginAt"]):
            # 更新用のフィールドが含まれている場合はUpdateUser
            tool_name = "UpdateUser"
        elif len(parameters) == 1 and "userId" in parameters:
            # userIdのみの場合はGetUser
            tool_name = "GetUser"
        else:
            raise ValueError(f"Cannot determine operation from parameters: {list(parameters.keys())}")
        
        print(f"[UserLambda] Inferred operation: {tool_name}")
        
        # ツールに基づいて関数を実行
        if tool_name == "AddUser":
            result = add_user(parameters)
        elif tool_name == "UpdateUser":
            result = update_user(parameters)
        elif tool_name == "GetUser":
            result = get_user(parameters)
        else:
            raise ValueError(f"Unknown operation: {tool_name}")
        
        print(f"[UserLambda] Operation completed successfully: {tool_name}")
        return result

    except ValueError as e:
        # バリデーションエラー
        error_msg = f"Validation error: {str(e)}"
        print(f"[UserLambda] {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "errorType": "ValidationError"
        }
    except ClientError as e:
        # DynamoDBエラー
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"Database error ({error_code}): {str(e)}"
        print(f"[UserLambda] {error_msg}")
        return {
            "success": False,
            "error": "データベースエラーが発生しました。しばらくしてから再度お試しください。",
            "errorType": "DatabaseError",
            "errorCode": error_code
        }
    except Exception as e:
        # その他のエラー
        error_msg = f"Unexpected error: {str(e)}"
        print(f"[UserLambda] {error_msg}")
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
        parameters: userId, username, email(optional)

    Returns:
        作成/更新されたユーザー情報

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    username = parameters.get("username")
    email = parameters.get("email", "")

    if not user_id:
        raise ValueError("userId is required")
    if not username:
        raise ValueError("username is required")

    print(f"[UserLambda] Adding/updating user: {user_id}, username: {username}")

    now = datetime.now(timezone.utc).isoformat()

    # DynamoDBにupsert（存在しない場合は作成、存在する場合は更新）
    item = {
        "userId": user_id,
        "username": username,
        "email": email,
        "createdAt": now,
        "lastLoginAt": now,
    }

    try:
        # 既存ユーザーの確認
        existing_response = table.get_item(Key={"userId": user_id})
        
        if "Item" in existing_response:
            # 既存ユーザーの場合は更新
            existing_item = existing_response["Item"]
            item["createdAt"] = existing_item.get("createdAt", now)  # 作成日時は保持
            print(f"[UserLambda] Updating existing user: {user_id}")
            operation = "updated"
        else:
            # 新規ユーザーの場合
            print(f"[UserLambda] Creating new user: {user_id}")
            operation = "created"

        # アイテムを保存
        table.put_item(Item=item)
        
        print(f"[UserLambda] User {operation} successfully: {user_id}")
        return {
            "success": True,
            "userId": user_id,
            "message": f"ユーザー情報を{operation}しました",
            "user": {
                "userId": user_id,
                "username": username,
                "email": email,
                "createdAt": item["createdAt"],
                "lastLoginAt": item["lastLoginAt"]
            }
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        print(f"[UserLambda] DynamoDB error in add_user: {error_code} - {str(e)}")
        raise


def update_user(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    既存のユーザー情報を部分的に更新

    Args:
        parameters: userId, username(optional), email(optional), lastLoginAt(optional)

    Returns:
        更新結果

    Raises:
        ValueError: 必須パラメータが不足している場合、または更新対象フィールドがない場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    username = parameters.get("username")
    email = parameters.get("email")
    last_login_at = parameters.get("lastLoginAt")

    if not user_id:
        raise ValueError("userId is required")

    print(f"[UserLambda] Updating user: {user_id}")

    # 更新式を構築
    update_expression_parts = []
    expression_attribute_values = {}

    if username is not None:
        update_expression_parts.append("username = :username")
        expression_attribute_values[":username"] = username
        print(f"[UserLambda] Updating username to: {username}")

    if email is not None:
        update_expression_parts.append("email = :email")
        expression_attribute_values[":email"] = email
        print(f"[UserLambda] Updating email to: {email}")

    if last_login_at is not None:
        update_expression_parts.append("lastLoginAt = :lastLoginAt")
        expression_attribute_values[":lastLoginAt"] = last_login_at
        print(f"[UserLambda] Updating lastLoginAt to: {last_login_at}")
    else:
        # lastLoginAtが指定されていない場合は現在時刻を設定
        now = datetime.now(timezone.utc).isoformat()
        update_expression_parts.append("lastLoginAt = :lastLoginAt")
        expression_attribute_values[":lastLoginAt"] = now
        print(f"[UserLambda] Setting lastLoginAt to current time: {now}")

    if not update_expression_parts:
        raise ValueError("At least one field to update is required (username, email, or lastLoginAt)")

    update_expression = "SET " + ", ".join(update_expression_parts)

    try:
        # ユーザーが存在することを確認しながら更新
        response = table.update_item(
            Key={"userId": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression="attribute_exists(userId)",  # ユーザーが存在することを確認
            ReturnValues="ALL_NEW",
        )
        
        updated_user = response["Attributes"]
        print(f"[UserLambda] User updated successfully: {user_id}")
        
        return {
            "success": True,
            "userId": user_id,
            "message": "ユーザー情報を更新しました",
            "user": {
                "userId": updated_user.get("userId"),
                "username": updated_user.get("username"),
                "email": updated_user.get("email", ""),
                "createdAt": updated_user.get("createdAt"),
                "lastLoginAt": updated_user.get("lastLoginAt")
            }
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ConditionalCheckFailedException":
            print(f"[UserLambda] User not found for update: {user_id}")
            raise ValueError(f"User not found: {user_id}")
        else:
            print(f"[UserLambda] DynamoDB error in update_user: {error_code} - {str(e)}")
            raise


def get_user(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    ユーザー情報を取得

    Args:
        parameters: userId

    Returns:
        ユーザー情報

    Raises:
        ValueError: userIdが指定されていない場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")

    if not user_id:
        raise ValueError("userId is required")

    print(f"[UserLambda] Retrieving user: {user_id}")

    try:
        response = table.get_item(Key={"userId": user_id})

        if "Item" in response:
            user = response["Item"]
            print(f"[UserLambda] User retrieved successfully: {user_id}")
            return {
                "success": True,
                "user": {
                    "userId": user.get("userId"),
                    "username": user.get("username"),
                    "email": user.get("email", ""),
                    "createdAt": user.get("createdAt"),
                    "lastLoginAt": user.get("lastLoginAt"),
                }
            }
        else:
            print(f"[UserLambda] User not found: {user_id}")
            return {
                "success": False,
                "message": "ユーザーが見つかりません",
                "userId": user_id
            }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        print(f"[UserLambda] DynamoDB error in get_user: {error_code} - {str(e)}")
        raise
