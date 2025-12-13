"""
HealthGoalLambda - 健康目標管理Lambda関数

HealthManagerMCP（Healthmateエコシステム）の健康目標管理を担当。
AgentCore Gateway（MCP）から呼び出され、DynamoDBで健康目標のCRUD操作を実行します。

機能:
- addGoal: 新しい健康目標を作成（UUIDでgoalId生成）
- updateGoal: 既存の健康目標を更新
- deleteGoal: 指定した健康目標を削除
- getGoals: ユーザーのすべての健康目標を取得

要件: 要件3（健康目標管理）、要件11（データ永続化）、要件12（エラーハンドリング）、要件13（ロギング）
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
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
table_name = os.environ.get("GOALS_TABLE_NAME", "healthmate-goals")
table = dynamodb.Table(table_name)

# 型定義
GoalType = Literal['longevity', 'fitness', 'weight', 'mental_health', 'other']
GoalStatus = Literal['active', 'achieved', 'paused', 'cancelled']


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数のエントリーポイント
    
    AgentCore Gateway（MCP）から呼び出され、健康目標のCRUD操作を実行します。
    クライアント側でJWTのsubクレームから抽出されたuserIdがパラメータとして渡されます。

    Args:
        event: AgentCore Gatewayからのイベント（MCPツール呼び出し）
        context: Lambda実行コンテキスト

    Returns:
        MCP形式のレスポンス
    """
    print(f"[HealthGoalLambda] Received event: {json.dumps(event, default=str)}")

    try:
        # AgentCore Gateway（MCP）形式のイベントを処理
        parameters = event.copy()
        
        # userIdの検証（必須）
        if "userId" not in parameters:
            raise ValueError("userId is required for all health goal operations")
        
        user_id = parameters["userId"]
        print(f"[HealthGoalLambda] Processing request for userId: {user_id}")
        
        # MCPツール名を推測（パラメータから判断）
        if "goalType" in parameters and "goalId" not in parameters:
            # 新しい目標を追加（goalTypeがあり、goalIdがない場合）
            tool_name = "AddGoal"
        elif "goalId" in parameters and any(key in parameters for key in ["title", "description", "targetValue", "targetDate", "priority", "status"]):
            # 既存の目標を更新
            tool_name = "UpdateGoal"
        elif "goalId" in parameters and len([k for k in parameters.keys() if k not in ["userId", "goalId"]]) == 0:
            # goalIdのみが指定されている場合は削除
            tool_name = "DeleteGoal"
        elif len(parameters) == 1 and "userId" in parameters:
            # userIdのみの場合は全目標取得
            tool_name = "GetGoals"
        else:
            raise ValueError(f"Cannot determine operation from parameters: {list(parameters.keys())}")
        
        print(f"[HealthGoalLambda] Inferred operation: {tool_name}")
        
        # ツールに基づいて関数を実行
        if tool_name == "AddGoal":
            result = add_goal(parameters)
        elif tool_name == "UpdateGoal":
            result = update_goal(parameters)
        elif tool_name == "DeleteGoal":
            result = delete_goal(parameters)
        elif tool_name == "GetGoals":
            result = get_goals(parameters)
        else:
            raise ValueError(f"Unknown operation: {tool_name}")
        
        print(f"[HealthGoalLambda] Operation completed successfully: {tool_name}")
        return result

    except ValueError as e:
        # バリデーションエラー
        error_msg = f"Validation error: {str(e)}"
        print(f"[HealthGoalLambda] {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "errorType": "ValidationError"
        }
    except ClientError as e:
        # DynamoDBエラー
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"Database error ({error_code}): {str(e)}"
        print(f"[HealthGoalLambda] {error_msg}")
        return {
            "success": False,
            "error": "データベースエラーが発生しました。しばらくしてから再度お試しください。",
            "errorType": "DatabaseError",
            "errorCode": error_code
        }
    except Exception as e:
        # その他のエラー
        error_msg = f"Unexpected error: {str(e)}"
        print(f"[HealthGoalLambda] {error_msg}")
        return {
            "success": False,
            "error": "予期しないエラーが発生しました。しばらくしてから再度お試しください。",
            "errorType": "InternalError"
        }


def add_goal(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    新しい健康目標を作成
    
    Args:
        parameters: userId, goalType, title, description, targetValue(optional), 
                   targetDate(optional), priority(optional)

    Returns:
        作成された健康目標情報

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    goal_type = parameters.get("goalType")
    title = parameters.get("title")
    description = parameters.get("description", "")
    target_value = parameters.get("targetValue")
    target_date = parameters.get("targetDate")
    priority = parameters.get("priority", 3)  # デフォルト優先度: 3

    # 必須パラメータの検証
    if not user_id:
        raise ValueError("userId is required")
    if not goal_type:
        raise ValueError("goalType is required")
    
    # titleがない場合はデフォルト値を設定
    if not title:
        title = f"{goal_type.capitalize()} Goal"
    
    # goalTypeの検証
    valid_goal_types = ['longevity', 'fitness', 'weight', 'mental_health', 'other']
    if goal_type not in valid_goal_types:
        raise ValueError(f"goalType must be one of: {', '.join(valid_goal_types)}")
    
    # priorityの検証
    if not isinstance(priority, int) or priority < 1 or priority > 5:
        raise ValueError("priority must be an integer between 1 and 5")

    # UUIDでgoalIdを生成
    goal_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    print(f"[HealthGoalLambda] Creating goal: {goal_id} for user: {user_id}")

    # DynamoDBアイテムを構築
    item = {
        "userId": user_id,
        "goalId": goal_id,
        "goalType": goal_type,
        "title": title,
        "description": description,
        "priority": priority,
        "status": "active",  # デフォルトステータス
        "createdAt": now,
        "updatedAt": now,
    }

    # オプションフィールドを追加
    if target_value:
        item["targetValue"] = target_value
    if target_date:
        item["targetDate"] = target_date

    try:
        # DynamoDBに保存
        table.put_item(Item=item)
        
        print(f"[HealthGoalLambda] Goal created successfully: {goal_id}")
        return {
            "success": True,
            "goalId": goal_id,
            "message": "健康目標を作成しました",
            "goal": item
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        print(f"[HealthGoalLambda] DynamoDB error in add_goal: {error_code} - {str(e)}")
        raise


def update_goal(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    既存の健康目標を更新

    Args:
        parameters: userId, goalId, title(optional), description(optional), 
                   targetValue(optional), targetDate(optional), priority(optional), status(optional)

    Returns:
        更新結果

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    goal_id = parameters.get("goalId")
    title = parameters.get("title")
    description = parameters.get("description")
    target_value = parameters.get("targetValue")
    target_date = parameters.get("targetDate")
    priority = parameters.get("priority")
    status = parameters.get("status")

    if not user_id:
        raise ValueError("userId is required")
    if not goal_id:
        raise ValueError("goalId is required")

    print(f"[HealthGoalLambda] Updating goal: {goal_id} for user: {user_id}")

    # 更新式を構築
    update_expression_parts = []
    expression_attribute_values = {}

    if title is not None:
        update_expression_parts.append("title = :title")
        expression_attribute_values[":title"] = title

    if description is not None:
        update_expression_parts.append("description = :description")
        expression_attribute_values[":description"] = description

    if target_value is not None:
        update_expression_parts.append("targetValue = :targetValue")
        expression_attribute_values[":targetValue"] = target_value

    if target_date is not None:
        update_expression_parts.append("targetDate = :targetDate")
        expression_attribute_values[":targetDate"] = target_date

    if priority is not None:
        if not isinstance(priority, int) or priority < 1 or priority > 5:
            raise ValueError("priority must be an integer between 1 and 5")
        update_expression_parts.append("priority = :priority")
        expression_attribute_values[":priority"] = priority

    if status is not None:
        valid_statuses = ['active', 'achieved', 'paused', 'cancelled']
        if status not in valid_statuses:
            raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        update_expression_parts.append("#status = :status")
        expression_attribute_values[":status"] = status

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
        # 目標が存在することを確認しながら更新
        update_params = {
            "Key": {"userId": user_id, "goalId": goal_id},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expression_attribute_values,
            "ConditionExpression": "attribute_exists(userId) AND attribute_exists(goalId)",
            "ReturnValues": "ALL_NEW",
        }
        
        if expression_attribute_names:
            update_params["ExpressionAttributeNames"] = expression_attribute_names

        response = table.update_item(**update_params)
        
        updated_goal = response["Attributes"]
        print(f"[HealthGoalLambda] Goal updated successfully: {goal_id}")
        
        return {
            "success": True,
            "goalId": goal_id,
            "message": "健康目標を更新しました",
            "goal": updated_goal
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ConditionalCheckFailedException":
            print(f"[HealthGoalLambda] Goal not found for update: {goal_id}")
            raise ValueError(f"Goal not found: {goal_id}")
        else:
            print(f"[HealthGoalLambda] DynamoDB error in update_goal: {error_code} - {str(e)}")
            raise


def delete_goal(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定した健康目標を削除

    Args:
        parameters: userId, goalId

    Returns:
        削除結果

    Raises:
        ValueError: 必須パラメータが不足している場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    goal_id = parameters.get("goalId")

    if not user_id:
        raise ValueError("userId is required")
    if not goal_id:
        raise ValueError("goalId is required")

    print(f"[HealthGoalLambda] Deleting goal: {goal_id} for user: {user_id}")

    try:
        # 目標が存在することを確認しながら削除
        response = table.delete_item(
            Key={"userId": user_id, "goalId": goal_id},
            ConditionExpression="attribute_exists(userId) AND attribute_exists(goalId)",
            ReturnValues="ALL_OLD"
        )
        
        deleted_goal = response.get("Attributes")
        print(f"[HealthGoalLambda] Goal deleted successfully: {goal_id}")
        
        return {
            "success": True,
            "goalId": goal_id,
            "message": "健康目標を削除しました",
            "deletedGoal": deleted_goal
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ConditionalCheckFailedException":
            print(f"[HealthGoalLambda] Goal not found for deletion: {goal_id}")
            raise ValueError(f"Goal not found: {goal_id}")
        else:
            print(f"[HealthGoalLambda] DynamoDB error in delete_goal: {error_code} - {str(e)}")
            raise


def get_goals(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    ユーザーのすべての健康目標を取得

    Args:
        parameters: userId

    Returns:
        健康目標のリスト

    Raises:
        ValueError: userIdが指定されていない場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")

    if not user_id:
        raise ValueError("userId is required")

    print(f"[HealthGoalLambda] Retrieving goals for user: {user_id}")

    try:
        # userIdでクエリしてすべての目標を取得
        response = table.query(
            KeyConditionExpression="userId = :userId",
            ExpressionAttributeValues={":userId": user_id}
        )
        
        goals = response.get("Items", [])
        print(f"[HealthGoalLambda] Retrieved {len(goals)} goals for user: {user_id}")
        
        return {
            "success": True,
            "userId": user_id,
            "goals": goals,
            "count": len(goals)
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        print(f"[HealthGoalLambda] DynamoDB error in get_goals: {error_code} - {str(e)}")
        raise