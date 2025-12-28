# デザイン文書

## 概要

HolisticUserDataServiceは、ユーザーの包括的な健康データを一括で取得するMCPツールです。AI健康コーチが効果的なアドバイスを提供するために必要な、ユーザーの最新の健康状態を包括的に把握することを目的としています。

このサービスは、既存の8つのDynamoDBテーブルから必要なデータを効率的に取得し、構造化された形式で返します。

## アーキテクチャ

### システム構成

```
CoachAI Agent
    ↓ (JWT Token)
MCP Gateway
    ↓ (User ID extraction)
HolisticUserDataService Lambda
    ↓ (DynamoDB Queries)
8つのDynamoDBテーブル
    ↓ (Structured Response)
包括的健康データ
```

### データフロー

1. **認証**: MCP GatewayでJWT認証を実行し、ユーザーIDを抽出
2. **データ取得**: Lambda関数が8つのテーブルから並行してデータを取得
3. **データ統合**: 取得したデータを論理的なセクションに整理
4. **レスポンス**: 構造化されたJSON形式で包括的データを返却

## コンポーネントと インターフェース

### Lambda関数: HolisticUserDataLambda

**責任**:
- MCP Gatewayからのリクエスト処理
- 8つのDynamoDBテーブルからのデータ取得
- データの構造化と統合
- エラーハンドリングとログ出力

**インターフェース**:
```python
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    HolisticUserDataService のエントリーポイント
    
    Args:
        event: MCP Gatewayからのイベント（userIdを含む）
        context: Lambda実行コンテキスト
    
    Returns:
        包括的健康データのレスポンス
    """
```

### MCP Target: HolisticUserDataService

**設定**:
- Target名: `HolisticUserDataService`
- 説明: "ユーザーの包括的健康データを一括取得するサービス"
- Lambda ARN: `healthmanagermcp-holistic-user-data{環境サフィックス}`
- 認証: Gateway IAM Role

## データモデル

### 取得対象テーブルとデータ

#### 1. ユーザー情報 (healthmate-users)
```python
{
    "userId": str,
    "username": str,
    "email": str,
    "dateOfBirth": str,  # YYYY-MM-DD (optional)
    "createdAt": str,
    "lastLoginAt": str
}
```

#### 2. 健康目標 (healthmate-goals)
```python
{
    "userId": str,
    "goalId": str,
    "title": str,
    "goalType": str,
    "targetValue": str,
    "status": str,  # Active, Completed, Paused
    "createdAt": str,
    "updatedAt": str
}
```

#### 3. 健康ポリシー (healthmate-policies)
```python
{
    "userId": str,
    "policyId": str,
    "title": str,
    "policyType": str,
    "rules": List[str],
    "isActive": str,  # "true" or "false"
    "createdAt": str,
    "updatedAt": str
}
```

#### 4. 健康コンサーン (healthmate-concerns)
```python
{
    "userId": str,
    "concernId": str,
    "title": str,
    "description": str,
    "category": str,
    "severity": str,
    "status": str,  # Active, Resolved, Monitoring
    "createdAt": str,
    "updatedAt": str
}
```

#### 5. 身体測定 (healthmate-body-measurements)
```python
{
    "userId": str,
    "measurementId": str,
    "date": str,  # YYYY-MM-DD
    "time": str,  # HH:MM
    "measurements": {
        "weight": float,
        "height": float,
        "bodyFatPercentage": float
    },
    "record_type": str,  # "latest", "oldest", or None
    "createdAt": str
}
```

#### 6. 活動履歴 (healthmate-activities)
```python
{
    "userId": str,
    "date": str,  # YYYY-MM-DD
    "activities": List[{
        "activityId": str,
        "time": str,  # HH:MM
        "activityType": str,
        "description": str,
        "items": List[str]
    }],
    "createdAt": str,
    "updatedAt": str
}
```

#### 7. 経過観測 (healthmate-observations)
```python
{
    "userId": str,
    "observationId": str,  # OBS#YYYY-MM-DD-XXX
    "title": str,
    "description": str,
    "startDate": str,
    "endDate": str,
    "status": str,  # InProgress, Completed, Cancelled
    "in_progress": str,  # "TRUE" (スパースインデックス用)
    "createdAt": str,
    "updatedAt": str
}
```

#### 8. 日記 (healthmate-journals)
```python
{
    "userId": str,
    "date": str,  # YYYY-MM-DD
    "content": str,
    "mood": str,
    "tags": List[str],
    "createdAt": str,
    "updatedAt": str
}
```

### レスポンス構造

```python
{
    "success": bool,
    "data": {
        "metadata": {
            "userId": str,
            "retrievedAt": str,  # ISO timestamp
            "dataFreshness": {
                "userProfile": str,
                "goals": str,
                "policies": str,
                "concerns": str,
                "bodyMeasurements": str,
                "activities": str,
                "observations": str,
                "reflection": str
            }
        },
        "userProfile": {
            "userId": str,
            "username": str,
            "email": str,
            "dateOfBirth": str | None,
            "createdAt": str,
            "lastLoginAt": str
        },
        "goals": List[Goal],
        "policies": List[Policy],
        "concerns": List[Concern],
        "bodyMeasurements": {
            "latest": Measurement | None,
            "oldest": Measurement | None,
            "recent3Days": List[Measurement]
        },
        "activities": {
            "recent3Days": List[{
                "date": str,
                "activities": List[Activity],
                "count": int
            }]
        },
        "observations": {
            "inProgress": List[Observation]
        },
        "reflection": {
            "previousDay": Journal | None
        }
    }
}
```

## データ取得戦略

### DynamoDBクエリパターン

#### 1. ユーザー情報取得
```python
# Primary Key Query
table.get_item(Key={"userId": user_id})
```

#### 2. 健康目標取得（アクティブのみ）
```python
# Query with Filter
table.query(
    KeyConditionExpression=Key('userId').eq(user_id),
    FilterExpression=Attr('status').eq('Active')
)
```

#### 3. 健康ポリシー取得（アクティブのみ）
```python
# Query with Filter
table.query(
    KeyConditionExpression=Key('userId').eq(user_id),
    FilterExpression=Attr('isActive').eq('true')
)
```

#### 4. 健康コンサーン取得（アクティブのみ）
```python
# Query with Filter
table.query(
    KeyConditionExpression=Key('userId').eq(user_id),
    FilterExpression=Attr('status').eq('Active')
)
```

#### 5. 身体測定取得
```python
# Latest record
table.query(
    KeyConditionExpression=Key('userId').eq(user_id),
    IndexName='RecordTypeIndex',
    KeyConditionExpression=Key('userId').eq(user_id) & Key('record_type').eq('latest')
)

# Oldest record
table.query(
    KeyConditionExpression=Key('userId').eq(user_id),
    IndexName='RecordTypeIndex', 
    KeyConditionExpression=Key('userId').eq(user_id) & Key('record_type').eq('oldest')
)

# Recent 3 days
table.query(
    KeyConditionExpression=Key('userId').eq(user_id),
    FilterExpression=Attr('date').between(start_date, end_date)
)
```

#### 6. 活動履歴取得（直近3日）
```python
# Date range query
table.query(
    KeyConditionExpression=Key('userId').eq(user_id) & Key('date').between(start_date, end_date)
)
```

#### 7. 経過観測取得（InProgressのみ）
```python
# LSI Query
table.query(
    KeyConditionExpression=Key('userId').eq(user_id),
    IndexName='InProgressIndex',
    KeyConditionExpression=Key('userId').eq(user_id) & Key('in_progress').eq('TRUE')
)
```

#### 8. 前日の日記取得
```python
# Primary Key Query
table.get_item(Key={"userId": user_id, "date": previous_date})
```

### 日付計算ロジック

```python
from datetime import datetime, timedelta, timezone

def get_date_ranges(timezone_str: str = "Asia/Tokyo"):
    """
    現在時刻基準で必要な日付範囲を計算
    
    Returns:
        today: 今日の日付 (YYYY-MM-DD)
        previous_day: 前日の日付 (YYYY-MM-DD)
        start_date: 3日前の日付 (YYYY-MM-DD)
        end_date: 今日の日付 (YYYY-MM-DD)
    """
    # ユーザーのタイムゾーンで現在時刻を取得
    tz = pytz.timezone(timezone_str)
    now = datetime.now(tz)
    today = now.date()
    
    # 日付範囲を計算
    previous_day = today - timedelta(days=1)
    start_date = today - timedelta(days=2)  # 今日含む3日間
    end_date = today
    
    return {
        "today": today.strftime("%Y-%m-%d"),
        "previous_day": previous_day.strftime("%Y-%m-%d"),
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d")
    }
```

## コレクトネスプロパティ

*プロパティとは、システムの全ての有効な実行において真であるべき特性や動作のことです。プロパティは、人間が読める仕様と機械で検証可能な正確性保証の橋渡しとなります。*

### プロパティ1: ユーザープロファイル取得の一貫性
*任意の* 有効なユーザーIDに対して、GetUserHolisticDataを呼び出すと、ユーザープロファイル情報が含まれたレスポンスが返される
**検証: 要件 1.1**

### プロパティ2: アクティブデータフィルタリング
*任意の* ユーザーに対して、返される健康目標、ポリシー、コンサーン、経過観測は全てアクティブ/現在の状態のもののみである
**検証: 要件 1.2, 1.3, 1.4, 1.7**

### プロパティ3: 身体測定データ構造の完全性
*任意の* ユーザーに対して、身体測定データのレスポンスには最新、最古、直近3日分の3つのセクションが全て含まれる
**検証: 要件 1.5**

### プロパティ4: 3日間の日付範囲制限
*任意の* ユーザーに対して、返される活動履歴は正確に今日を含む直近3日間の範囲内のデータのみである
**検証: 要件 1.6, 5.1**

### プロパティ5: 前日日記の日付正確性
*任意の* ユーザーに対して、返される振り返り日記は前日の日付のもの、または存在しない場合はnullである
**検証: 要件 1.8**

### プロパティ6: レスポンス構造の完全性
*任意の* レスポンスに対して、データが存在しない場合でも全ての必須セクション（プロファイル、目標、ポリシー、悩み、測定、活動、観測、振り返り）とメタデータが含まれる
**検証: 要件 2.1, 2.2, 2.4**

### プロパティ7: ユーザーデータアクセス制御
*任意の* ユーザーIDに対して、返される全てのデータは指定されたユーザーIDに属するもののみである
**検証: 要件 3.2**

### プロパティ8: システムエラー時の例外処理
*任意の* DynamoDBシステムエラー（接続エラー、予期しないデータ形式等）に対して、適切なエラーメッセージと共に例外がスローされる
**検証: 要件 4.1, 4.3, 4.4**

### プロパティ9: データ不存在時の継続処理
*任意の* データが存在しないユーザーに対して、空の構造が返され、他のセクションの処理が正常に継続される
**検証: 要件 4.2**

### プロパティ10: データ量制限の適用
*任意の* 大量のデータを持つユーザーに対して、返されるデータは適切な制限内（活動履歴は3日間、経過観測はInProgressのみ等）である
**検証: 要件 5.4**

## エラーハンドリング

### エラー分類と対応

#### 1. システムエラー（処理停止）
- **DynamoDB接続エラー**: ClientError例外をスロー
- **予期しないデータ形式**: ValueError例外をスロー
- **Lambda実行エラー**: Exception例外をスロー

#### 2. データ不存在（処理継続）
- **ユーザー情報なし**: 空のuserProfileオブジェクトを返す
- **目標なし**: 空のgoals配列を返す
- **ポリシーなし**: 空のpolicies配列を返す
- **その他データなし**: 各セクションで空の構造を返す

### エラーレスポンス形式

```python
# システムエラー時
{
    "success": False,
    "error": "データベースエラーが発生しました。しばらくしてから再度お試しください。",
    "errorType": "DatabaseError",
    "errorCode": "ConditionalCheckFailedException"
}

# データ不存在時（正常レスポンス）
{
    "success": True,
    "data": {
        "metadata": {...},
        "userProfile": {},
        "goals": [],
        "policies": [],
        # ... 他のセクションも空構造
    }
}
```

## テスト戦略

### 単体テスト

**対象**:
- 各データ取得関数の正常系・異常系
- 日付計算ロジック
- データ構造化ロジック
- エラーハンドリング

**テストケース例**:
```python
def test_get_user_profile_success():
    """ユーザー情報取得の正常系テスト"""
    
def test_get_user_profile_not_found():
    """ユーザー情報が存在しない場合のテスト"""
    
def test_get_activities_recent_3_days():
    """直近3日の活動履歴取得テスト"""
    
def test_date_range_calculation():
    """日付範囲計算のテスト"""
```

### 統合テスト

**対象**:
- 実際のDynamoDBテーブルとの連携
- MCP Gateway経由での呼び出し
- エンドツーエンドのデータフロー

**テストシナリオ**:
1. 完全なデータセットを持つユーザーでの取得
2. 部分的なデータのみを持つユーザーでの取得
3. データが全く存在しないユーザーでの取得
4. DynamoDBエラー発生時の動作確認

## 実装詳細

### Lambda関数構造

```python
# lambda/holistic_user_data/handler.py
import json
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import boto3
import pytz
from botocore.exceptions import ClientError

# 既存パターンに従った実装
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """メインハンドラー"""
    
def get_user_holistic_data(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """包括的データ取得のメイン関数"""
    
def get_user_profile(user_id: str) -> Dict[str, Any]:
    """ユーザー情報取得"""
    
def get_active_goals(user_id: str) -> List[Dict[str, Any]]:
    """アクティブな健康目標取得"""
    
def get_active_policies(user_id: str) -> List[Dict[str, Any]]:
    """アクティブな健康ポリシー取得"""
    
def get_active_concerns(user_id: str) -> List[Dict[str, Any]]:
    """アクティブな健康コンサーン取得"""
    
def get_body_measurements(user_id: str, date_ranges: Dict[str, str]) -> Dict[str, Any]:
    """身体測定データ取得（最新、最古、直近3日）"""
    
def get_recent_activities(user_id: str, date_ranges: Dict[str, str]) -> Dict[str, Any]:
    """直近3日の活動履歴取得"""
    
def get_in_progress_observations(user_id: str) -> List[Dict[str, Any]]:
    """進行中の経過観測取得"""
    
def get_previous_day_reflection(user_id: str, previous_date: str) -> Optional[Dict[str, Any]]:
    """前日の振り返り日記取得"""
    
def get_date_ranges(timezone_str: str = "Asia/Tokyo") -> Dict[str, str]:
    """日付範囲計算"""
```

### MCPスキーマ

```json
[
  {
    "name": "GetUserHolisticData",
    "description": "ユーザーの包括的な健康データを一括で取得する。ユーザー情報、健康目標、ポリシー、悩み、身体測定（最新・最古・直近3日）、活動履歴（直近3日）、進行中の経過観測、前日の振り返り日記を含む。",
    "inputSchema": {
      "type": "object",
      "properties": {
        "userId": {
          "type": "string",
          "description": "ユーザーID"
        },
        "timezone": {
          "type": "string",
          "description": "ユーザーのタイムゾーン（デフォルト: Asia/Tokyo）",
          "default": "Asia/Tokyo"
        }
      },
      "required": ["userId"]
    }
  }
]
```

### CDK統合

```python
# HolisticUserDataLambda用のCloudWatch Logsロググループ
holistic_user_data_log_group = logs.LogGroup(
    self,
    "HolisticUserDataLambdaLogGroup",
    log_group_name=f"/aws/lambda/healthmanagermcp-holistic-user-data{self.config_provider.get_environment_suffix()}",
    retention=logs.RetentionDays.ONE_WEEK,
    removal_policy=RemovalPolicy.DESTROY,
)

# HolisticUserDataLambda関数
self.holistic_user_data_lambda = lambda_.Function(
    self,
    "HolisticUserDataLambda",
    function_name=f"healthmanagermcp-holistic-user-data{self.config_provider.get_environment_suffix()}",
    runtime=lambda_.Runtime.PYTHON_3_12,
    handler="holistic_user_data.handler.lambda_handler",
    code=lambda_.Code.from_asset(lambda_code_path),
    timeout=Duration.seconds(60),  # 複数テーブルアクセスのため長めに設定
    memory_size=512,  # データ処理のため多めに設定
    environment={
        "USERS_TABLE_NAME": self.users_table.table_name,
        "GOALS_TABLE_NAME": self.goals_table.table_name,
        "POLICIES_TABLE_NAME": self.policies_table.table_name,
        "CONCERNS_TABLE_NAME": self.concerns_table.table_name,
        "BODY_MEASUREMENTS_TABLE_NAME": self.body_measurements_table.table_name,
        "ACTIVITIES_TABLE_NAME": self.activities_table.table_name,
        "OBSERVATIONS_TABLE_NAME": self.observations_table.table_name,
        "JOURNALS_TABLE_NAME": self.journals_table.table_name,
        "HEALTHMATE_ENV": self.current_environment,
        "LOG_LEVEL": self.log_controller.get_log_level(),
    },
    log_group=holistic_user_data_log_group,
)

# 全テーブルへの読み取り権限を付与
self.users_table.grant_read_data(self.holistic_user_data_lambda)
self.goals_table.grant_read_data(self.holistic_user_data_lambda)
self.policies_table.grant_read_data(self.holistic_user_data_lambda)
self.concerns_table.grant_read_data(self.holistic_user_data_lambda)
self.body_measurements_table.grant_read_data(self.holistic_user_data_lambda)
self.activities_table.grant_read_data(self.holistic_user_data_lambda)
self.observations_table.grant_read_data(self.holistic_user_data_lambda)
self.journals_table.grant_read_data(self.holistic_user_data_lambda)

# HolisticUserDataService Target
holistic_user_data_mcp_schema = load_mcp_schema("holistic-user-data-service-mcp-schema.json")

self.holistic_user_data_target = bedrockagentcore.CfnGatewayTarget(
    self,
    "HolisticUserDataServiceTarget",
    gateway_identifier=self.agentcore_gateway.ref,
    name="HolisticUserDataService",
    description="ユーザーの包括的健康データを一括取得するサービス",
    credential_provider_configurations=[
        bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
            credential_provider_type="GATEWAY_IAM_ROLE"
        )
    ],
    target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
        mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
            lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                lambda_arn=self.holistic_user_data_lambda.function_arn,
                tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                    inline_payload=holistic_user_data_mcp_schema
                )
            )
        )
    )
)

# Lambda権限追加
self.holistic_user_data_lambda.add_permission(
    "AllowAgentCoreGatewayInvoke",
    principal=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
    action="lambda:InvokeFunction",
)
```