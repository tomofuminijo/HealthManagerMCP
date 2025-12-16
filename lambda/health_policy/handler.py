"""
HealthPolicyLambda - 健康ポリシー管理Lambda関数

HealthManagerMCP（Healthmateエコシステム）の健康ポリシー管理を担当。
AgentCore Gateway（MCP）から呼び出され、DynamoDBで健康ポリシーのCRUD操作を実行します。

機能:
- addPolicy: 新しい健康ポリシーを作成（UUIDでpolicyId生成）
- updatePolicy: 既存の健康ポリシーを更新
- deletePolicy: 指定した健康ポリシーを削除
- getPolicies: ユーザーのすべての健康ポリシーを取得

要件: 要件4（健康ポリシー管理）、要件11（データ永続化）、要件12（エラーハンドリング）、要件13（ロギング）
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
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
table_name = os.environ.get("POLICIES_TABLE_NAME", "healthmate-policies")
table = dynamodb.Table(table_name)

# 型定義
PolicyType = Literal["diet", "exercise", "sleep", "fasting", "restriction", "other"]


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数のエントリーポイント
    
    AgentCore Gateway（MCP）から呼び出され、健康ポリシーのCRUD操作を実行します。
    クライアント側でJWTのsubクレームから抽出されたuserIdがパラメータとして渡されます。

    Args:
        event: AgentCore Gatewayからのイベント（MCPツール呼び出し）
        context: Lambda実行コンテキスト

    Returns:
        MCP形式のレスポンス
    """
    print(f"[HealthPolicyLambda] Received event: {json.dumps(event, default=str)}")

    try:
        # AgentCore Gateway（MCP）形式のイベントを処理
        parameters = event.copy()
        
        # userIdの検証（必須）
        if "userId" not in parameters:
            raise ValueError("userId is required for all health policy operations")
        
        user_id = parameters["userId"]
        print(f"[HealthPolicyLambda] Processing request for userId: {user_id}")
        
        # contextからツール名を取得
        tool_name = context.client_context.custom['bedrockAgentCoreToolName'].split('___', 1)[-1]
        print(f"[HealthPolicyLambda] Tool name from context: {tool_name}")
        
        # ツールに基づいて関数を実行
        if tool_name == "AddPolicy":
            result = add_policy(parameters)
        elif tool_name == "UpdatePolicy":
            result = update_policy(parameters)
        elif tool_name == "DeletePolicy":
            result = delete_policy(parameters)
        elif tool_name == "GetPolicies":
            result = get_policies(parameters)
        else:
            raise ValueError(f"Unknown operation: {tool_name}")
        
        print(f"[HealthPolicyLambda] Operation completed successfully: {tool_name}")
        return result

    except ValueError as e:
        # バリデーションエラー
        error_msg = f"Validation error: {str(e)}"
        print(f"[HealthPolicyLambda] {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "errorType": "ValidationError"
        }
    except ClientError as e:
        # DynamoDBエラー
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"Database error ({error_code}): {str(e)}"
        print(f"[HealthPolicyLambda] {error_msg}")
        return {
            "success": False,
            "error": "データベースエラーが発生しました。しばらくしてから再度お試しください。",
            "errorType": "DatabaseError",
            "errorCode": error_code
        }
    except Exception as e:
        # その他のエラー
        error_msg = f"Unexpected error: {str(e)}"
        print(f"[HealthPolicyLambda] {error_msg}")
        return {
            "success": False,
            "error": "予期しないエラーが発生しました。しばらくしてから再度お試しください。",
            "errorType": "InternalError"
        }


def add_policy(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    新しい健康ポリシーを作成
    
    Args:
        parameters: userId, policyType, title, description, rules, 
                   startDate(optional), endDate(optional)

    Returns:
        作成された健康ポリシー情報

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    policy_type = parameters.get("policyType")
    title = parameters.get("title")
    description = parameters.get("description", "")
    rules = parameters.get("rules", parameters.get("parameters", {}))  # rulesまたはparametersフィールドを使用
    start_date = parameters.get("startDate")
    end_date = parameters.get("endDate")

    # 必須パラメータの検証
    if not user_id:
        raise ValueError("userId is required")
    if not policy_type:
        raise ValueError("policyType is required")
    
    # titleがない場合はデフォルト値を設定
    if not title:
        title = f"{policy_type.capitalize()} Policy"
    
    # policyTypeの検証
    valid_policy_types = ['diet', 'exercise', 'sleep', 'fasting', 'restriction', 'other']
    if policy_type not in valid_policy_types:
        raise ValueError(f"policyType must be one of: {', '.join(valid_policy_types)}")

    # UUIDでpolicyIdを生成
    policy_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    print(f"[HealthPolicyLambda] Creating policy: {policy_id} for user: {user_id}")

    # DynamoDBアイテムを構築
    item = {
        "userId": user_id,
        "policyId": policy_id,
        "policyType": policy_type,
        "title": title,
        "description": description,
        "rules": rules,
        "isActive": "true",  # GSIのため文字列として保存
        "createdAt": now,
        "updatedAt": now,
    }

    # オプションフィールドを追加
    if start_date:
        item["startDate"] = start_date
    if end_date:
        item["endDate"] = end_date

    try:
        # DynamoDBに保存
        table.put_item(Item=item)
        
        print(f"[HealthPolicyLambda] Policy created successfully: {policy_id}")
        return {
            "success": True,
            "policyId": policy_id,
            "message": "健康ポリシーを作成しました",
            "policy": item
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        print(f"[HealthPolicyLambda] DynamoDB error in add_policy: {error_code} - {str(e)}")
        raise


def update_policy(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    既存の健康ポリシーを更新

    Args:
        parameters: userId, policyId, title(optional), description(optional), 
                   rules(optional), isActive(optional), startDate(optional), endDate(optional)

    Returns:
        更新結果

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    policy_id = parameters.get("policyId")
    title = parameters.get("title")
    description = parameters.get("description")
    rules = parameters.get("rules")
    is_active = parameters.get("isActive")
    start_date = parameters.get("startDate")
    end_date = parameters.get("endDate")

    if not user_id:
        raise ValueError("userId is required")
    if not policy_id:
        raise ValueError("policyId is required")

    print(f"[HealthPolicyLambda] Updating policy: {policy_id} for user: {user_id}")

    # 更新式を構築
    update_expression_parts = []
    expression_attribute_values = {}

    if title is not None:
        update_expression_parts.append("title = :title")
        expression_attribute_values[":title"] = title

    if description is not None:
        update_expression_parts.append("description = :description")
        expression_attribute_values[":description"] = description

    if rules is not None:
        update_expression_parts.append("rules = :rules")
        expression_attribute_values[":rules"] = rules

    if is_active is not None:
        update_expression_parts.append("isActive = :isActive")
        # ブール値を文字列に変換（GSI対応）
        expression_attribute_values[":isActive"] = "true" if is_active else "false"

    if start_date is not None:
        update_expression_parts.append("startDate = :startDate")
        expression_attribute_values[":startDate"] = start_date

    if end_date is not None:
        update_expression_parts.append("endDate = :endDate")
        expression_attribute_values[":endDate"] = end_date

    # updatedAtは常に更新
    now = datetime.now(timezone.utc).isoformat()
    update_expression_parts.append("updatedAt = :updatedAt")
    expression_attribute_values[":updatedAt"] = now

    if len(update_expression_parts) == 1:  # updatedAtのみの場合
        raise ValueError("At least one field to update is required")

    update_expression = "SET " + ", ".join(update_expression_parts)

    try:
        # ポリシーが存在することを確認しながら更新
        response = table.update_item(
            Key={"userId": user_id, "policyId": policy_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression="attribute_exists(userId) AND attribute_exists(policyId)",
            ReturnValues="ALL_NEW",
        )
        
        updated_policy = response["Attributes"]
        print(f"[HealthPolicyLambda] Policy updated successfully: {policy_id}")
        
        return {
            "success": True,
            "policyId": policy_id,
            "message": "健康ポリシーを更新しました",
            "policy": updated_policy
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ConditionalCheckFailedException":
            print(f"[HealthPolicyLambda] Policy not found for update: {policy_id}")
            raise ValueError(f"Policy not found: {policy_id}")
        else:
            print(f"[HealthPolicyLambda] DynamoDB error in update_policy: {error_code} - {str(e)}")
            raise


def delete_policy(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定した健康ポリシーを削除

    Args:
        parameters: userId, policyId

    Returns:
        削除結果

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    policy_id = parameters.get("policyId")

    if not user_id:
        raise ValueError("userId is required")
    if not policy_id:
        raise ValueError("policyId is required")

    print(f"[HealthPolicyLambda] Deleting policy: {policy_id} for user: {user_id}")

    try:
        # ポリシーが存在することを確認しながら削除
        response = table.delete_item(
            Key={"userId": user_id, "policyId": policy_id},
            ConditionExpression="attribute_exists(userId) AND attribute_exists(policyId)",
            ReturnValues="ALL_OLD"
        )
        
        deleted_policy = response.get("Attributes")
        print(f"[HealthPolicyLambda] Policy deleted successfully: {policy_id}")
        
        return {
            "success": True,
            "policyId": policy_id,
            "message": "健康ポリシーを削除しました",
            "deletedPolicy": deleted_policy
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ConditionalCheckFailedException":
            print(f"[HealthPolicyLambda] Policy not found for deletion: {policy_id}")
            raise ValueError(f"Policy not found: {policy_id}")
        else:
            print(f"[HealthPolicyLambda] DynamoDB error in delete_policy: {error_code} - {str(e)}")
            raise


def get_policies(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    ユーザーのすべての健康ポリシーを取得

    Args:
        parameters: userId

    Returns:
        健康ポリシーのリスト

    Raises:
        ValueError: userIdが指定されていない場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")

    if not user_id:
        raise ValueError("userId is required")

    print(f"[HealthPolicyLambda] Retrieving policies for user: {user_id}")

    try:
        # userIdでクエリしてすべてのポリシーを取得
        response = table.query(
            KeyConditionExpression="userId = :userId",
            ExpressionAttributeValues={":userId": user_id}
        )

        policies = response.get("Items", [])
        print(f"[HealthPolicyLambda] Retrieved {len(policies)} policies for user: {user_id}")

        return {
            "success": True,
            "userId": user_id,
            "policies": policies,
            "count": len(policies)
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        print(f"[HealthPolicyLambda] DynamoDB error in get_policies: {error_code} - {str(e)}")
        raise
