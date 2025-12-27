"""
Body Measurement Lambda Handler

身体測定値（体重、身長、体脂肪率）の記録・管理を行うLambda関数

HealthManagerMCP（Healthmateエコシステム）の身体測定値管理を担当。
AgentCore Gateway（MCP）から呼び出され、DynamoDBで身体測定値のCRUD操作を実行します。

機能:
- addBodyMeasurement: 新しい身体測定値を記録
- updateBodyMeasurement: 既存の測定記録を更新
- deleteBodyMeasurement: 測定記録を削除
- getLatestMeasurements: 最新の測定値を取得
- getOldestMeasurements: 最古の測定値を取得
- getMeasurementHistory: 指定期間の測定履歴を取得

要件: 身体測定値記録機能の全要件
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from decimal import Decimal
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

dynamodb = boto3.resource('dynamodb', config=config)
table_name = os.environ.get('BODY_MEASUREMENTS_TABLE_NAME', 'healthmate-body-measurements')
table = dynamodb.Table(table_name)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数のエントリーポイント
    
    AgentCore Gateway（MCP）から呼び出され、身体測定値のCRUD操作を実行します。
    クライアント側でJWTのsubクレームから抽出されたuserIdがパラメータとして渡されます。

    Args:
        event: AgentCore Gatewayからのイベント（MCPツール呼び出し）
        context: Lambda実行コンテキスト

    Returns:
        MCP形式のレスポンス
    """
    logger.debug(f"Received event: {json.dumps(event, default=str)}")
    logger.debug(f"Context: {context}")

    try:
        # AgentCore Gateway（MCP）形式のイベントを処理
        parameters = event.copy()
        
        # userIdの検証（必須）
        if "userId" not in parameters:
            raise ValueError("userId is required for all body measurement operations")
        
        user_id = parameters["userId"]
        logger.info(f"Processing request for userId: {user_id}")
        
        # ツール名の取得方法を修正
        tool_name = None
        
        # 方法1: contextからツール名を取得（AgentCore Gateway）
        try:
            if hasattr(context, 'client_context') and context.client_context and hasattr(context.client_context, 'custom'):
                tool_name = context.client_context.custom.get('bedrockAgentCoreToolName', '').split('___', 1)[-1]
                logger.debug(f"Tool name from context: {tool_name}")
        except Exception as e:
            logger.debug(f"Could not get tool name from context: {e}")
        
        # 方法2: eventからツール名を取得（フォールバック）
        if not tool_name:
            tool_name = event.get('tool_name') or event.get('toolName')
            logger.debug(f"Tool name from event: {tool_name}")
        
        # 方法3: Lambda関数名から推測（最終フォールバック）
        if not tool_name:
            function_name = context.function_name if hasattr(context, 'function_name') else 'unknown'
            if 'body-measurement' in function_name.lower():
                # デフォルトでAddBodyMeasurementを使用（テスト用）
                tool_name = "AddBodyMeasurement"
                logger.debug(f"Using default tool name: {tool_name}")
        
        if not tool_name:
            raise ValueError("Could not determine tool name from context or event")
        
        # ツールに基づいて関数を実行
        if tool_name == "AddBodyMeasurement":
            result = add_body_measurement(parameters)
        elif tool_name == "UpdateBodyMeasurement":
            result = update_body_measurement(parameters)
        elif tool_name == "DeleteBodyMeasurement":
            result = delete_body_measurement(parameters)
        elif tool_name == "GetLatestMeasurements":
            result = get_latest_measurements(parameters)
        elif tool_name == "GetOldestMeasurements":
            result = get_oldest_measurements(parameters)
        elif tool_name == "GetMeasurementHistory":
            result = get_measurement_history(parameters)
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
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": "予期しないエラーが発生しました。しばらくしてから再度お試しください。",
            "errorType": "InternalError"
        }


def validate_measurement_values(**measurements) -> None:
    """
    測定値の妥当性を検証
    
    Args:
        **measurements: 測定値（weight, height, body_fat_percentage）
    
    Raises:
        ValueError: 無効な測定値の場合
    """
    errors = []
    
    weight = measurements.get('weight')
    if weight is not None:
        try:
            weight_val = float(weight)
            if weight_val <= 0 or weight_val > 1000:
                errors.append("体重は1-1000kgの範囲で入力してください")
        except (ValueError, TypeError):
            errors.append("体重は有効な数値で入力してください")
    
    height = measurements.get('height')
    if height is not None:
        try:
            height_val = float(height)
            if height_val < 50 or height_val > 300:
                errors.append("身長は50-300cmの範囲で入力してください")
        except (ValueError, TypeError):
            errors.append("身長は有効な数値で入力してください")
    
    body_fat_percentage = measurements.get('body_fat_percentage')
    if body_fat_percentage is not None:
        try:
            bfp_val = float(body_fat_percentage)
            if bfp_val < 0 or bfp_val > 100:
                errors.append("体脂肪率は0-100%の範囲で入力してください")
        except (ValueError, TypeError):
            errors.append("体脂肪率は有効な数値で入力してください")
    
    if errors:
        raise ValueError("; ".join(errors))





def add_body_measurement(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    身体測定値を追加
    
    Args:
        parameters: userId, weight(optional), height(optional), body_fat_percentage(optional), measurement_time(optional)
    
    Returns:
        MCP レスポンス
    """
    try:
        user_id = parameters.get("userId")
        weight = parameters.get('weight')
        height = parameters.get('height')
        body_fat_percentage = parameters.get('body_fat_percentage')
        measurement_time = parameters.get('measurement_time')
        
        if not user_id:
            raise ValueError("userId is required")
        
        logger.debug(f"Adding measurement for user: {user_id}")
        
        # 少なくとも一つの測定値が必要
        measurement_data = {}
        if weight is not None:
            measurement_data['weight'] = Decimal(str(weight))
        if height is not None:
            measurement_data['height'] = Decimal(str(height))
        if body_fat_percentage is not None:
            measurement_data['body_fat_percentage'] = Decimal(str(body_fat_percentage))
        
        if not measurement_data:
            raise ValueError("少なくとも一つの測定値を提供してください")
        
        # 測定値の妥当性検証
        validate_measurement_values(**measurement_data)
        
        # タイムスタンプ処理
        if measurement_time:
            # 他のLambda関数と同様にシンプルに処理
            measurement_time = measurement_time
        else:
            measurement_time = datetime.now(timezone.utc).isoformat()
        
        # 通常の測定記録を保存
        measurement_id = measurement_time
        measurement_record = {
            'userId': user_id,
            'measurementId': f'MEASUREMENT#{measurement_id}',
            **measurement_data,
            'measurement_time': measurement_time,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        table.put_item(Item=measurement_record)
        logger.debug(f"Saved measurement record: {measurement_record}")
        
        # Latest/Oldest レコードの更新
        update_latest_oldest_records(user_id, measurement_data, measurement_time)
        
        logger.info(f"Measurement added successfully for user: {user_id}")
        return {
            "success": True,
            "message": "測定値が正常に記録されました",
            "measurementId": measurement_id,
            "measurementTime": measurement_time,
            "recordedValues": measurement_data
        }
        
    except ValueError as e:
        logger.warning(f"Validation error in add_body_measurement: {str(e)}")
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in add_body_measurement: {error_code} - {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in add_body_measurement: {str(e)}")
        raise


def update_latest_oldest_records(user_id: str, new_measurement: Dict[str, Any], measurement_time: str) -> None:
    """
    Latest/Oldest レコードを更新
    
    Args:
        user_id: ユーザーID
        new_measurement: 新しい測定値
        measurement_time: 測定時刻
    """
    try:
        # 既存の測定記録があるかチェック
        existing_measurements = get_all_user_measurements(user_id)
        regular_measurements = [
            r for r in existing_measurements 
            if not r['measurementId'].endswith('#latest') and not r['measurementId'].endswith('#oldest')
        ]
        
        is_first_measurement = len(regular_measurements) <= 1  # 今追加したレコードを含む
        
        if is_first_measurement:
            # 初回記録の場合、Latest と Oldest に同じデータを設定
            handle_first_measurement(user_id, new_measurement, measurement_time)
        else:
            # 通常の Latest/Oldest 更新処理
            update_latest_record(user_id, new_measurement, measurement_time)
            update_oldest_record(user_id, new_measurement, measurement_time)
            
    except Exception as e:
        logger.warning(f"Error updating latest/oldest records: {str(e)}")
        # Latest/Oldest更新エラーは警告レベルで記録（メイン処理は成功）


def handle_first_measurement(user_id: str, measurement: Dict[str, Any], measurement_time: str) -> None:
    """
    初回測定記録時の特別処理
    
    Args:
        user_id: ユーザーID
        measurement: 測定値
        measurement_time: 測定時刻
    """
    base_record_data = {
        **measurement,
        'measurement_time': measurement_time,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Latest レコード作成
    latest_record = {
        'userId': user_id,
        'measurementId': 'MEASUREMENT#latest',
        'record_type': 'latest',
        **base_record_data,
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Oldest レコード作成（同じデータ）
    oldest_record = {
        'userId': user_id,
        'measurementId': 'MEASUREMENT#oldest',
        'record_type': 'oldest',
        **base_record_data
    }
    
    # 各測定タイプの時刻情報を追加
    for measurement_type in ['weight', 'height', 'body_fat_percentage']:
        if measurement_type in measurement:
            # Latest レコード用
            latest_record[f'last_{measurement_type}_update'] = measurement_time
            # Oldest レコード用
            oldest_record[f'first_{measurement_type}_record'] = measurement_time
    
    # 両方のレコードを保存
    table.put_item(Item=latest_record)
    table.put_item(Item=oldest_record)
    
    logger.debug(f"Created initial latest/oldest records for user {user_id}")


def update_latest_record(user_id: str, new_measurement: Dict[str, Any], measurement_time: str) -> None:
    """
    Latest レコードを更新
    
    Args:
        user_id: ユーザーID
        new_measurement: 新しい測定値
        measurement_time: 測定時刻
    """
    try:
        # 現在のLatest レコードを取得
        response = table.query(
            IndexName='RecordTypeIndex',
            KeyConditionExpression='userId = :pk AND record_type = :rt',
            ExpressionAttributeValues={
                ':pk': f'{user_id}',
                ':rt': 'latest'
            }
        )
        
        current_latest = response['Items'][0] if response['Items'] else None
        
        if not current_latest:
            # Latest レコードが存在しない場合は新規作成
            latest_record = {
                'userId': f'{user_id}',
                'measurementId': 'MEASUREMENT#latest',
                'record_type': 'latest',
                **new_measurement,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # 各測定タイプの最終更新時刻を記録
            for measurement_type in ['weight', 'height', 'body_fat_percentage']:
                if measurement_type in new_measurement:
                    latest_record[f'last_{measurement_type}_update'] = measurement_time
            
            table.put_item(Item=latest_record)
            return
        
        # 既存のLatest レコードを更新
        updated_latest = current_latest.copy()
        
        for measurement_type, value in new_measurement.items():
            if measurement_type in ['weight', 'height', 'body_fat_percentage']:
                # 新しい測定値で更新
                updated_latest[measurement_type] = value
                updated_latest[f'last_{measurement_type}_update'] = measurement_time
        
        updated_latest['updated_at'] = datetime.now(timezone.utc).isoformat()
        table.put_item(Item=updated_latest)
        
        logger.debug(f"Updated latest record for user {user_id}")
        
    except Exception as e:
        logger.warning(f"Error updating latest record: {str(e)}")


def update_oldest_record(user_id: str, new_measurement: Dict[str, Any], measurement_time: str) -> None:
    """
    Oldest レコードを更新（新しい測定タイプの場合のみ）
    
    Args:
        user_id: ユーザーID
        new_measurement: 新しい測定値
        measurement_time: 測定時刻
    """
    try:
        # 現在のOldest レコードを取得
        response = table.query(
            IndexName='RecordTypeIndex',
            KeyConditionExpression='userId = :pk AND record_type = :rt',
            ExpressionAttributeValues={
                ':pk': f'{user_id}',
                ':rt': 'oldest'
            }
        )
        
        current_oldest = response['Items'][0] if response['Items'] else None
        
        if not current_oldest:
            # Oldest レコードが存在しない場合は新規作成
            oldest_record = {
                'userId': f'{user_id}',
                'measurementId': 'MEASUREMENT#oldest',
                'record_type': 'oldest',
                **new_measurement,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            # 各測定タイプの初回記録時刻を記録
            for measurement_type in ['weight', 'height', 'body_fat_percentage']:
                if measurement_type in new_measurement:
                    oldest_record[f'first_{measurement_type}_record'] = measurement_time
            
            table.put_item(Item=oldest_record)
            return
        
        # 既存のOldest レコードに新しい測定タイプを追加
        updated_oldest = current_oldest.copy()
        
        for measurement_type, value in new_measurement.items():
            if measurement_type in ['weight', 'height', 'body_fat_percentage']:
                # まだ記録されていない測定タイプの場合のみ追加
                if measurement_type not in updated_oldest:
                    updated_oldest[measurement_type] = value
                    updated_oldest[f'first_{measurement_type}_record'] = measurement_time
        
        table.put_item(Item=updated_oldest)
        
        logger.debug(f"Updated oldest record for user {user_id}")
        
    except Exception as e:
        logger.warning(f"Error updating oldest record: {str(e)}")


def get_all_user_measurements(user_id: str) -> list:
    """
    ユーザーの全測定記録を取得
    
    Args:
        user_id: ユーザーID
    
    Returns:
        測定記録のリスト
    """
    try:
        response = table.query(
            KeyConditionExpression='userId = :pk',
            ExpressionAttributeValues={
                ':pk': f'{user_id}'
            }
        )
        return response['Items']
        
    except Exception as e:
        logger.warning(f"Error getting user measurements: {str(e)}")
        return []


def get_latest_measurements(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    最新の測定値を取得
    
    Args:
        parameters: userId
    
    Returns:
        MCP レスポンス
    """
    try:
        user_id = parameters.get("userId")
        if not user_id:
            raise ValueError("userId is required")
        
        logger.debug(f"Getting latest measurements for user: {user_id}")
        
        response = table.query(
            IndexName='RecordTypeIndex',
            KeyConditionExpression='userId = :pk AND record_type = :rt',
            ExpressionAttributeValues={
                ':pk': f'{user_id}',
                ':rt': 'latest'
            }
        )
        
        if not response['Items']:
            logger.info(f"No measurements found for user: {user_id}")
            return {
                "success": True,
                "message": "測定記録が見つかりません",
                "measurements": {}
            }
        
        latest_record = response['Items'][0]
        
        # レスポンス用にクリーンアップ
        result = {}
        for key, value in latest_record.items():
            if key in ['weight', 'height', 'body_fat_percentage']:
                result[key] = float(value) if isinstance(value, Decimal) else value
            elif key.startswith('last_') and key.endswith('_update'):
                result[key] = value
        
        logger.info(f"Latest measurements retrieved for user: {user_id}")
        return {
            "success": True,
            "message": "最新の測定値を取得しました",
            "measurements": result
        }
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_latest_measurements: {error_code} - {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error in get_latest_measurements: {str(e)}")
        raise


def get_oldest_measurements(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    最古の測定値を取得
    
    Args:
        parameters: userId
    
    Returns:
        MCP レスポンス
    """
    try:
        user_id = parameters.get("userId")
        if not user_id:
            raise ValueError("userId is required")
        
        logger.debug(f"Getting oldest measurements for user: {user_id}")
        
        response = table.query(
            IndexName='RecordTypeIndex',
            KeyConditionExpression='userId = :pk AND record_type = :rt',
            ExpressionAttributeValues={
                ':pk': f'{user_id}',
                ':rt': 'oldest'
            }
        )
        
        if not response['Items']:
            logger.info(f"No measurements found for user: {user_id}")
            return {
                "success": True,
                "message": "測定記録が見つかりません",
                "measurements": {}
            }
        
        oldest_record = response['Items'][0]
        
        # レスポンス用にクリーンアップ
        result = {}
        for key, value in oldest_record.items():
            if key in ['weight', 'height', 'body_fat_percentage']:
                result[key] = float(value) if isinstance(value, Decimal) else value
            elif key.startswith('first_') and key.endswith('_record'):
                result[key] = value
        
        logger.info(f"Oldest measurements retrieved for user: {user_id}")
        return {
            "success": True,
            "message": "最古の測定値を取得しました",
            "measurements": result
        }
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_oldest_measurements: {error_code} - {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error in get_oldest_measurements: {str(e)}")
        raise


def get_measurement_history(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定期間の測定履歴を取得
    
    Args:
        parameters: userId, start_date, end_date, limit(optional)
    
    Returns:
        MCP レスポンス
    """
    try:
        user_id = parameters.get("userId")
        start_date = parameters.get('start_date')
        end_date = parameters.get('end_date')
        limit = parameters.get('limit', 50)
        
        if not user_id:
            raise ValueError("userId is required")
        if not start_date or not end_date:
            raise ValueError("start_date と end_date は必須です")
        
        logger.debug(f"Getting measurement history for user: {user_id} from {start_date} to {end_date}")
        
        # 日付範囲でのクエリ
        response = table.query(
            KeyConditionExpression='userId = :pk AND measurementId BETWEEN :start_sk AND :end_sk',
            ExpressionAttributeValues={
                ':pk': f'{user_id}',
                ':start_sk': f'MEASUREMENT#{start_date}',
                ':end_sk': f'MEASUREMENT#{end_date}Z'  # 終日を含むため
            },
            Limit=limit,
            ScanIndexForward=False  # 新しい順
        )
        
        # Latest/Oldest レコードを除外
        measurements = [
            item for item in response['Items']
            if not item['measurementId'].endswith('#latest') and not item['measurementId'].endswith('#oldest')
        ]
        
        # レスポンス用にクリーンアップ
        result = []
        for measurement in measurements:
            clean_measurement = {}
            for key, value in measurement.items():
                if key in ['weight', 'height', 'body_fat_percentage']:
                    clean_measurement[key] = float(value) if isinstance(value, Decimal) else value
                elif key in ['measurement_time', 'created_at']:
                    clean_measurement[key] = value
                elif key == 'measurementId':
                    # measurement_id として measurementId から抽出
                    clean_measurement['measurement_id'] = value.replace('MEASUREMENT#', '')
            result.append(clean_measurement)
        
        logger.info(f"Retrieved {len(result)} measurements for user: {user_id}")
        return {
            "success": True,
            "message": f"{len(result)}件の測定記録を取得しました",
            "measurements": result,
            "count": len(result),
            "period": {
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in get_measurement_history: {error_code} - {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error in get_measurement_history: {str(e)}")
        raise


def update_body_measurement(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    既存の測定記録を更新
    
    Args:
        parameters: userId, measurement_id, その他更新パラメータ
    
    Returns:
        MCP レスポンス
    """
    try:
        user_id = parameters.get("userId")
        measurement_id = parameters.get("measurement_id")
        
        if not user_id:
            raise ValueError("userId is required")
        if not measurement_id:
            raise ValueError("measurement_id is required")
        
        logger.debug(f"Updating measurement {measurement_id} for user: {user_id}")
        
        # 更新する測定値を抽出
        update_data = {}
        weight = parameters.get('weight')
        height = parameters.get('height')
        body_fat_percentage = parameters.get('body_fat_percentage')
        
        if weight is not None:
            update_data['weight'] = Decimal(str(weight))
        if height is not None:
            update_data['height'] = Decimal(str(height))
        if body_fat_percentage is not None:
            update_data['body_fat_percentage'] = Decimal(str(body_fat_percentage))
        
        if not update_data:
            raise ValueError("少なくとも一つの測定値を提供してください")
        
        # 測定値の妥当性検証
        validate_measurement_values(**update_data)
        
        # 既存レコードの存在確認と取得
        response = table.get_item(
            Key={
                'userId': f'{user_id}',
                'measurementId': f'MEASUREMENT#{measurement_id}'
            }
        )
        
        if 'Item' not in response:
            raise ValueError("指定された測定記録が見つかりません")
        
        existing_record = response['Item']
        
        # レコードの所有権確認
        if not existing_record['userId'] == f'{user_id}':
            raise ValueError("この測定記録を更新する権限がありません")
        
        # レコードを更新
        updated_record = existing_record.copy()
        updated_record.update(update_data)
        updated_record['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        # DynamoDBに保存
        table.put_item(Item=updated_record)
        
        logger.debug(f"Updated measurement record: {measurement_id}")
        
        # Latest レコードの再計算（更新されたレコードが最新の場合）
        recalculate_latest_record_after_update(user_id, measurement_id, update_data)
        
        logger.info(f"Measurement updated successfully for user: {user_id}")
        return {
            "success": True,
            "message": "測定記録が正常に更新されました",
            "measurementId": measurement_id,
            "updatedValues": update_data
        }
        
    except ValueError as e:
        logger.warning(f"Validation error in update_body_measurement: {str(e)}")
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in update_body_measurement: {error_code} - {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_body_measurement: {str(e)}")
        raise


def delete_body_measurement(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    測定記録を削除
    
    Args:
        parameters: userId, measurement_id
    
    Returns:
        MCP レスポンス
    """
    try:
        user_id = parameters.get("userId")
        measurement_id = parameters.get("measurement_id")
        
        if not user_id:
            raise ValueError("userId is required")
        if not measurement_id:
            raise ValueError("measurement_id is required")
        
        logger.debug(f"Deleting measurement {measurement_id} for user: {user_id}")
        
        # 削除対象レコードの存在確認と取得
        response = table.get_item(
            Key={
                'userId': f'{user_id}',
                'measurementId': f'MEASUREMENT#{measurement_id}'
            }
        )
        
        if 'Item' not in response:
            raise ValueError("指定された測定記録が見つかりません")
        
        target_record = response['Item']
        
        # レコードの所有権確認
        if not target_record['userId'] == f'{user_id}':
            raise ValueError("この測定記録を削除する権限がありません")
        
        # レコードを削除
        table.delete_item(
            Key={
                'userId': f'{user_id}',
                'measurementId': f'MEASUREMENT#{measurement_id}'
            }
        )
        
        logger.debug(f"Deleted measurement record: {measurement_id}")
        
        # Latest/Oldest レコードの再計算
        recalculate_latest_record_after_deletion(user_id, measurement_id)
        recalculate_oldest_record_after_deletion(user_id, measurement_id)
        
        logger.info(f"Measurement deleted successfully for user: {user_id}")
        return {
            "success": True,
            "message": "測定記録が正常に削除されました",
            "deletedMeasurementId": measurement_id
        }
        
    except ValueError as e:
        logger.warning(f"Validation error in delete_body_measurement: {str(e)}")
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"DynamoDB error in delete_body_measurement: {error_code} - {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in delete_body_measurement: {str(e)}")
        raise


def recalculate_latest_record_after_update(user_id: str, updated_measurement_id: str, updated_data: Dict[str, Any]) -> None:
    """
    測定記録更新後のLatest レコード再計算
    
    Args:
        user_id: ユーザーID
        updated_measurement_id: 更新された測定記録ID
        updated_data: 更新されたデータ
    """
    try:
        # 全測定記録を取得して最新値を再計算
        all_measurements = get_all_user_measurements(user_id)
        regular_measurements = [
            r for r in all_measurements 
            if not r['measurementId'].endswith('#latest') and not r['measurementId'].endswith('#oldest')
        ]
        
        if not regular_measurements:
            # 測定記録がない場合、Latest レコードを削除
            table.delete_item(
                Key={
                    'userId': f'{user_id}',
                    'measurementId': 'MEASUREMENT#latest'
                }
            )
            return
        
        # 各測定タイプの最新値を再計算
        latest_values = {}
        last_update_times = {}
        
        for measurement_type in ['weight', 'height', 'body_fat_percentage']:
            records_with_type = [
                r for r in regular_measurements 
                if measurement_type in r
            ]
            records_with_type.sort(key=lambda x: x['measurement_time'], reverse=True)
            
            if records_with_type:
                latest_values[measurement_type] = records_with_type[0][measurement_type]
                last_update_times[f'last_{measurement_type}_update'] = records_with_type[0]['measurement_time']
        
        # Latest レコードを更新
        if latest_values:
            latest_record = {
                'userId': f'{user_id}',
                'measurementId': 'MEASUREMENT#latest',
                'record_type': 'latest',
                **latest_values,
                **last_update_times,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            table.put_item(Item=latest_record)
            
            logger.debug(f"Recalculated latest record after update for user: {user_id}")
        
    except Exception as e:
        logger.warning(f"Error recalculating latest record after update: {str(e)}")


def recalculate_latest_record_after_deletion(user_id: str, deleted_measurement_id: str) -> None:
    """
    測定記録削除後のLatest レコード再計算
    
    Args:
        user_id: ユーザーID
        deleted_measurement_id: 削除された測定記録ID
    """
    try:
        # 残りの全測定記録を取得
        remaining_measurements = get_all_user_measurements(user_id)
        regular_measurements = [
            r for r in remaining_measurements 
            if not r['measurementId'].endswith('#latest') and not r['measurementId'].endswith('#oldest')
        ]
        
        if not regular_measurements:
            # 測定記録が全て削除された場合、Latest レコードも削除
            table.delete_item(
                Key={
                    'userId': f'{user_id}',
                    'measurementId': 'MEASUREMENT#latest'
                }
            )
            logger.debug(f"Deleted latest record (no measurements left) for user: {user_id}")
            return
        
        # 各測定タイプの最新値を再計算
        latest_values = {}
        last_update_times = {}
        
        for measurement_type in ['weight', 'height', 'body_fat_percentage']:
            records_with_type = [
                r for r in regular_measurements 
                if measurement_type in r
            ]
            records_with_type.sort(key=lambda x: x['measurement_time'], reverse=True)
            
            if records_with_type:
                latest_values[measurement_type] = records_with_type[0][measurement_type]
                last_update_times[f'last_{measurement_type}_update'] = records_with_type[0]['measurement_time']
        
        # Latest レコードを更新
        if latest_values:
            latest_record = {
                'userId': f'{user_id}',
                'measurementId': 'MEASUREMENT#latest',
                'record_type': 'latest',
                **latest_values,
                **last_update_times,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            table.put_item(Item=latest_record)
            
            logger.debug(f"Recalculated latest record after deletion for user: {user_id}")
        
    except Exception as e:
        logger.warning(f"Error recalculating latest record after deletion: {str(e)}")


def recalculate_oldest_record_after_deletion(user_id: str, deleted_measurement_id: str) -> None:
    """
    測定記録削除後のOldest レコード再計算
    
    Args:
        user_id: ユーザーID
        deleted_measurement_id: 削除された測定記録ID
    """
    try:
        # 残りの全測定記録を取得
        remaining_measurements = get_all_user_measurements(user_id)
        regular_measurements = [
            r for r in remaining_measurements 
            if not r['measurementId'].endswith('#latest') and not r['measurementId'].endswith('#oldest')
        ]
        
        if not regular_measurements:
            # 測定記録が全て削除された場合、Oldest レコードも削除
            table.delete_item(
                Key={
                    'userId': f'{user_id}',
                    'measurementId': 'MEASUREMENT#oldest'
                }
            )
            logger.debug(f"Deleted oldest record (no measurements left) for user: {user_id}")
            return
        
        # 各測定タイプの最古値を再計算
        oldest_values = {}
        first_record_times = {}
        
        for measurement_type in ['weight', 'height', 'body_fat_percentage']:
            records_with_type = [
                r for r in regular_measurements 
                if measurement_type in r
            ]
            records_with_type.sort(key=lambda x: x['measurement_time'])  # 昇順ソート
            
            if records_with_type:
                oldest_values[measurement_type] = records_with_type[0][measurement_type]
                first_record_times[f'first_{measurement_type}_record'] = records_with_type[0]['measurement_time']
        
        # Oldest レコードを更新
        if oldest_values:
            oldest_record = {
                'userId': f'{user_id}',
                'measurementId': 'MEASUREMENT#oldest',
                'record_type': 'oldest',
                **oldest_values,
                **first_record_times,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            table.put_item(Item=oldest_record)
            
            logger.debug(f"Recalculated oldest record after deletion for user: {user_id}")
        
    except Exception as e:
        logger.warning(f"Error recalculating oldest record after deletion: {str(e)}")
