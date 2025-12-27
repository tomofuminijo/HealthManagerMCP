"""
JournalLambda - 日記管理Lambda関数

HealthManagerMCP（Healthmateエコシステム）の日記管理を担当。
AgentCore Gateway（MCP）から呼び出され、DynamoDBで日記データのCRUD操作を実行します。

機能:
- GetJournal: 特定日の日記エントリーを取得
- GetJournalsInRange: 日付範囲の日記エントリーを取得（最大365日間）
- AddJournal: 新しい日記エントリーを作成または既存エントリーに追記
- UpdateJournal: 既存の日記エントリーを完全置換
- DeleteJournal: 日記エントリーを削除

要件: 要件1（日記作成）、要件2（データ永続化）、要件3（日記取得）、要件4（日記更新）、要件5（日記削除）、要件6（MCPツール）、要件7（データ検証）
"""

import json
import os
import re
import logging
from datetime import datetime, timezone, date, timedelta
from typing import Any, Dict, List, Optional
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
table_name = os.environ.get("JOURNALS_TABLE_NAME", "healthmate-journals")
table = dynamodb.Table(table_name)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数のエントリーポイント
    
    AgentCore Gateway（MCP）から呼び出され、日記データのCRUD操作を実行します。
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
            raise ValueError("userId is required for all journal operations")
        
        user_id = parameters["userId"]
        logger.info(f"Processing request for userId: {user_id}")
        
        # contextからツール名を取得
        tool_name = context.client_context.custom['bedrockAgentCoreToolName'].split('___', 1)[-1]
        logger.debug(f"Tool name from context: {tool_name}")
        
        # ツールに基づいて関数を実行
        if tool_name == "GetJournal":
            result = get_journal(parameters)
        elif tool_name == "GetJournalsInRange":
            result = get_journals_in_range(parameters)
        elif tool_name == "AddJournal":
            result = add_journal(parameters)
        elif tool_name == "UpdateJournal":
            result = update_journal(parameters)
        elif tool_name == "DeleteJournal":
            result = delete_journal(parameters)
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


def get_journal(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    特定日の日記エントリーを取得
    
    Args:
        parameters: userId, date

    Returns:
        日記エントリー情報または見つからない場合のメッセージ

    Raises:
        ValueError: 必須パラメータが不足している場合、または日付の検証に失敗した場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    date_str = parameters.get("date")

    if not user_id:
        raise ValueError("userId is required")
    if not date_str:
        raise ValueError("date is required")

    # 日付の検証
    validate_date(date_str)
    logger.info(f"Getting journal for user: {user_id}, date: {date_str}")

    try:
        response = table.get_item(
            Key={
                "userId": user_id,
                "date": date_str
            }
        )

        if "Item" in response:
            journal = response["Item"]
            logger.info(f"Journal retrieved successfully: {user_id}, {date_str}")
            
            return {
                "success": True,
                "journal": {
                    "userId": journal.get("userId"),
                    "date": journal.get("date"),
                    "content": journal.get("content"),
                    "moodScore": journal.get("moodScore"),
                    "tags": journal.get("tags", []),
                    "createdAt": journal.get("createdAt"),
                    "updatedAt": journal.get("updatedAt")
                }
            }
        else:
            logger.info(f"Journal not found: {user_id}, {date_str}")
            return {
                "success": False,
                "message": "指定された日付の日記が見つかりません",
                "userId": user_id,
                "date": date_str
            }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_journal: {error_code} - {str(e)}")
        raise


def get_journals_in_range(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    日付範囲の日記エントリーを取得（最大365日間）
    
    Args:
        parameters: userId, startDate, endDate

    Returns:
        日記エントリーのリスト（時系列順）

    Raises:
        ValueError: 必須パラメータが不足している場合、日付の検証に失敗した場合、または範囲が365日を超える場合
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

    # 日付の検証
    validate_date(start_date)
    validate_date(end_date)
    
    # 日付範囲の検証
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    if start_date_obj > end_date_obj:
        raise ValueError("startDate must be before or equal to endDate")
    
    # 365日制限の確認
    date_range = (end_date_obj - start_date_obj).days + 1
    if date_range > 365:
        raise ValueError("Date range cannot exceed 365 days")

    logger.info(f"Getting journals for user: {user_id}, range: {start_date} to {end_date} ({date_range} days)")

    try:
        # DynamoDBクエリ（日付範囲）
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('userId').eq(user_id) & 
                                 boto3.dynamodb.conditions.Key('date').between(start_date, end_date)
        )

        journals = response.get("Items", [])
        
        # 日付順でソート（時系列順）
        journals.sort(key=lambda x: x.get("date", ""))
        
        logger.info(f"Retrieved {len(journals)} journals for user: {user_id}")
        
        # レスポンス用のデータを構築
        journal_list = []
        for journal in journals:
            journal_list.append({
                "userId": journal.get("userId"),
                "date": journal.get("date"),
                "content": journal.get("content"),
                "moodScore": journal.get("moodScore"),
                "tags": journal.get("tags", []),
                "createdAt": journal.get("createdAt"),
                "updatedAt": journal.get("updatedAt")
            })
        
        return {
            "success": True,
            "journals": journal_list,
            "count": len(journal_list),
            "dateRange": {
                "startDate": start_date,
                "endDate": end_date,
                "days": date_range
            }
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_journals_in_range: {error_code} - {str(e)}")
        raise


def add_journal(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    新しい日記エントリーを作成または既存エントリーに追記
    
    Args:
        parameters: userId, content, date(optional), moodScore(optional), tags(optional)

    Returns:
        作成/更新された日記エントリー情報

    Raises:
        ValueError: 必須パラメータが不足している場合、または検証に失敗した場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    content = parameters.get("content")
    date_str = parameters.get("date")
    mood_score = parameters.get("moodScore")
    tags = parameters.get("tags", [])

    if not user_id:
        raise ValueError("userId is required")
    if not content:
        raise ValueError("content is required")

    # 日付が指定されていない場合は今日の日付を使用
    if not date_str:
        date_str = date.today().strftime('%Y-%m-%d')
        logger.debug(f"Using current date: {date_str}")
    else:
        validate_date(date_str)

    # コンテンツの検証
    validate_content(content)
    
    # 気分スコアの検証（提供された場合のみ）
    if mood_score is not None:
        validate_mood_score(mood_score)
    
    # タグの検証
    validate_tags(tags)

    logger.info(f"Adding journal for user: {user_id}, date: {date_str}")

    now = datetime.now(timezone.utc).isoformat()

    try:
        # 既存エントリーの確認
        existing_response = table.get_item(
            Key={
                "userId": user_id,
                "date": date_str
            }
        )
        
        if "Item" in existing_response:
            # 既存エントリーに追記
            existing_journal = existing_response["Item"]
            existing_content = existing_journal.get("content", "")
            
            # 既存コンテンツに新しいコンテンツを追記
            if existing_content:
                new_content = existing_content + "\n\n" + content
            else:
                new_content = content
            
            # 更新するアイテム
            item = {
                "userId": user_id,
                "date": date_str,
                "content": new_content,
                "createdAt": existing_journal.get("createdAt", now),  # 作成日時は保持
                "updatedAt": now
            }
            
            # 気分スコアが提供された場合は更新
            if mood_score is not None:
                item["moodScore"] = mood_score
            elif "moodScore" in existing_journal:
                item["moodScore"] = existing_journal["moodScore"]  # 既存の値を保持
            
            # タグが提供された場合は更新、そうでなければ既存のタグを保持
            if tags:
                item["tags"] = tags
            elif "tags" in existing_journal:
                item["tags"] = existing_journal["tags"]
            else:
                item["tags"] = []
            
            logger.info(f"Appending to existing journal: {user_id}, {date_str}")
            operation = "追記"
            
        else:
            # 新規エントリー作成
            item = {
                "userId": user_id,
                "date": date_str,
                "content": content,
                "createdAt": now,
                "updatedAt": now,
                "tags": tags
            }
            
            # 気分スコアが提供された場合のみ追加
            if mood_score is not None:
                item["moodScore"] = mood_score
            
            logger.info(f"Creating new journal: {user_id}, {date_str}")
            operation = "作成"

        # アイテムを保存
        table.put_item(Item=item)
        
        logger.info(f"Journal {operation} successfully: {user_id}, {date_str}")
        
        # レスポンス用のデータを構築
        journal_response = {
            "userId": item["userId"],
            "date": item["date"],
            "content": item["content"],
            "tags": item.get("tags", []),
            "createdAt": item["createdAt"],
            "updatedAt": item["updatedAt"]
        }
        
        # 気分スコアが存在する場合のみレスポンスに含める
        if "moodScore" in item:
            journal_response["moodScore"] = item["moodScore"]
        
        return {
            "success": True,
            "message": f"日記を{operation}しました",
            "journal": journal_response
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in add_journal: {error_code} - {str(e)}")
        raise


def update_journal(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    既存の日記エントリーを完全置換
    
    Args:
        parameters: userId, date, content(optional), moodScore(optional), tags(optional)

    Returns:
        更新された日記エントリー情報

    Raises:
        ValueError: 必須パラメータが不足している場合、更新対象フィールドがない場合、または検証に失敗した場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    date_str = parameters.get("date")
    content = parameters.get("content")
    mood_score = parameters.get("moodScore")
    tags = parameters.get("tags")

    if not user_id:
        raise ValueError("userId is required")
    if not date_str:
        raise ValueError("date is required")

    # 日付の検証
    validate_date(date_str)

    # 更新対象フィールドがない場合はエラー
    if content is None and mood_score is None and tags is None:
        raise ValueError("At least one field to update is required (content, moodScore, or tags)")

    # 各フィールドの検証
    if content is not None:
        validate_content(content)
    if mood_score is not None:
        validate_mood_score(mood_score)
    if tags is not None:
        validate_tags(tags)

    logger.info(f"Updating journal for user: {user_id}, date: {date_str}")

    # 更新式を構築
    update_expression_parts = []
    remove_expression_parts = []
    expression_attribute_values = {}

    if content is not None:
        update_expression_parts.append("content = :content")
        expression_attribute_values[":content"] = content
        logger.debug(f"Updating content")

    if mood_score is not None:
        update_expression_parts.append("moodScore = :moodScore")
        expression_attribute_values[":moodScore"] = mood_score
        logger.debug(f"Updating moodScore to: {mood_score}")

    if tags is not None:
        if tags == []:  # 空配列の場合は削除
            remove_expression_parts.append("tags")
            logger.debug("Removing tags field")
        else:
            update_expression_parts.append("tags = :tags")
            expression_attribute_values[":tags"] = tags
            logger.debug(f"Updating tags to: {tags}")

    # updatedAtは常に更新
    now = datetime.now(timezone.utc).isoformat()
    update_expression_parts.append("updatedAt = :updatedAt")
    expression_attribute_values[":updatedAt"] = now

    # 更新式を構築
    update_expression = ""
    if update_expression_parts:
        update_expression += "SET " + ", ".join(update_expression_parts)
    if remove_expression_parts:
        if update_expression:
            update_expression += " "
        update_expression += "REMOVE " + ", ".join(remove_expression_parts)

    try:
        # 日記エントリーが存在することを確認しながら更新
        response = table.update_item(
            Key={
                "userId": user_id,
                "date": date_str
            },
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values if expression_attribute_values else None,
            ConditionExpression="attribute_exists(userId) AND attribute_exists(#date)",
            ExpressionAttributeNames={"#date": "date"},  # dateは予約語のため
            ReturnValues="ALL_NEW",
        )
        
        updated_journal = response["Attributes"]
        logger.info(f"Journal updated successfully: {user_id}, {date_str}")
        
        # レスポンス用のデータを構築
        journal_response = {
            "userId": updated_journal.get("userId"),
            "date": updated_journal.get("date"),
            "content": updated_journal.get("content"),
            "tags": updated_journal.get("tags", []),
            "createdAt": updated_journal.get("createdAt"),
            "updatedAt": updated_journal.get("updatedAt")
        }
        
        # 気分スコアが存在する場合のみレスポンスに含める
        if "moodScore" in updated_journal:
            journal_response["moodScore"] = updated_journal["moodScore"]
        
        return {
            "success": True,
            "message": "日記を更新しました",
            "journal": journal_response
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ConditionalCheckFailedException":
            logger.warning(f"Journal not found for update: {user_id}, {date_str}")
            raise ValueError(f"Journal not found for date: {date_str}")
        else:
            logger.error(f"DynamoDB error in update_journal: {error_code} - {str(e)}")
            raise


def delete_journal(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    日記エントリーを削除
    
    Args:
        parameters: userId, date

    Returns:
        削除結果

    Raises:
        ValueError: 必須パラメータが不足している場合、または日付の検証に失敗した場合
        ClientError: DynamoDB操作でエラーが発生した場合
    """
    user_id = parameters.get("userId")
    date_str = parameters.get("date")

    if not user_id:
        raise ValueError("userId is required")
    if not date_str:
        raise ValueError("date is required")

    # 日付の検証
    validate_date(date_str)
    logger.info(f"Deleting journal for user: {user_id}, date: {date_str}")

    try:
        # 日記エントリーが存在することを確認しながら削除
        response = table.delete_item(
            Key={
                "userId": user_id,
                "date": date_str
            },
            ConditionExpression="attribute_exists(userId) AND attribute_exists(#date)",
            ExpressionAttributeNames={"#date": "date"},  # dateは予約語のため
            ReturnValues="ALL_OLD"
        )
        
        if "Attributes" in response:
            deleted_journal = response["Attributes"]
            logger.info(f"Journal deleted successfully: {user_id}, {date_str}")
            
            return {
                "success": True,
                "message": "日記を削除しました",
                "deletedJournal": {
                    "userId": deleted_journal.get("userId"),
                    "date": deleted_journal.get("date"),
                    "content": deleted_journal.get("content"),
                    "moodScore": deleted_journal.get("moodScore"),
                    "tags": deleted_journal.get("tags", []),
                    "createdAt": deleted_journal.get("createdAt"),
                    "updatedAt": deleted_journal.get("updatedAt")
                }
            }
        else:
            # この状況は通常発生しないが、安全のため
            logger.info(f"Journal deleted (no return data): {user_id}, {date_str}")
            return {
                "success": True,
                "message": "日記を削除しました",
                "userId": user_id,
                "date": date_str
            }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ConditionalCheckFailedException":
            logger.warning(f"Journal not found for deletion: {user_id}, {date_str}")
            raise ValueError(f"Journal not found for date: {date_str}")
        else:
            logger.error(f"DynamoDB error in delete_journal: {error_code} - {str(e)}")
            raise


def validate_date(date_str: str) -> None:
    """
    日付の検証を行う
    
    Args:
        date_str: YYYY-MM-DD形式の日付文字列
        
    Raises:
        ValueError: 無効な日付形式または値の場合
    """
    if not isinstance(date_str, str):
        raise ValueError("日付は文字列で入力してください")
    
    # 形式チェック（YYYY-MM-DD）
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        raise ValueError("日付はYYYY-MM-DD形式で入力してください")
    
    try:
        # 日付の妥当性チェック
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # 未来の日付チェック（1日の余裕を持たせてタイムゾーンの問題を回避）
        today_utc = date.today()
        tomorrow_utc = today_utc + timedelta(days=1)
        if date_obj > tomorrow_utc:
            raise ValueError("日付は過去または今日の日付である必要があります")
            
    except ValueError as e:
        # datetime.strptimeでの解析エラーをキャッチ
        if "time data" in str(e) or "does not match format" in str(e):
            raise ValueError("無効な日付です。正しい日付を入力してください")
        # 既に適切なエラーメッセージの場合はそのまま再発生
        raise


def validate_mood_score(mood_score: Any) -> None:
    """
    気分スコアの検証を行う
    
    Args:
        mood_score: 1-5の整数
        
    Raises:
        ValueError: 無効な気分スコアの場合
    """
    if not isinstance(mood_score, int):
        raise ValueError("気分スコアは整数で入力してください")
    
    if mood_score < 1 or mood_score > 5:
        raise ValueError("気分スコアは1から5までの整数である必要があります")


def validate_content(content: str) -> None:
    """
    日記コンテンツの検証を行う
    
    Args:
        content: 日記の内容
        
    Raises:
        ValueError: 無効なコンテンツの場合
    """
    if not isinstance(content, str):
        raise ValueError("日記の内容は文字列で入力してください")
    
    if not content.strip():
        raise ValueError("日記の内容は空にできません")
    
    # 長さ制限チェック（10000文字）
    if len(content) > 10000:
        raise ValueError("日記の内容は10000文字以内で入力してください")


def validate_tags(tags: List[str]) -> None:
    """
    タグの検証を行う
    
    Args:
        tags: タグのリスト
        
    Raises:
        ValueError: 無効なタグの場合
    """
    if not isinstance(tags, list):
        raise ValueError("タグはリスト形式で入力してください")
    
    if len(tags) > 10:
        raise ValueError("タグは最大10個まで設定できます")
    
    for tag in tags:
        if not isinstance(tag, str):
            raise ValueError("タグは文字列で入力してください")
        
        if not tag.strip():
            raise ValueError("空のタグは設定できません")
        
        # PascalCase形式の���ェック
        if not re.match(r'^[A-Z][a-zA-Z0-9]*$', tag):
            raise ValueError(f"タグ '{tag}' はPascalCase英語形式で入力してください（例: Coding, Happy）")