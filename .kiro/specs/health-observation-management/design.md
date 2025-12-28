# デザイン文書

## 概要

Health Observation Management機能は、HealthManagerシステム内でCoachAIエージェントがMCPプロトコルを通じて利用する健康経過観察管理ツールです。ユーザーの健康症状に対する経過観察を管理し、AIとの会話セッションを超えて継続的な健康状態の追跡と記録を可能にします。

この機能により、CoachAIは「3日間腰痛の経過を観察しましょう」といった提案を行い、その後の会話セッションでも継続的に経過を追跡できるようになります。

## アーキテクチャ

### システム構成

```
CoachAI Agent
    ↓ (MCP Protocol)
AgentCore Gateway
    ↓ (Lambda Invocation)
HealthObservationLambda
    ↓ (DynamoDB Operations)
healthmate-observations テーブル
```

### 統合ポイント

- **CoachAI**: MCPクライアントとして経過観察ツールを利用
- **AgentCore Gateway**: MCPプロトコルのエンドポイント
- **Lambda Function**: 経過観察管理のビジネスロジック
- **DynamoDB**: 経過観察データの永続化
- **JWT Authentication**: ユーザー識別とアクセス制御

## コンポーネントとインターフェース

### Lambda Function: HealthObservationLambda

**場所**: `lambda/health_observation/handler.py`

**責任**:
- MCPツール呼び出しの処理
- 経過観察データのCRUD操作
- データ検証とエラーハンドリング
- DynamoDB操作の実行

**インターフェース**:
```python
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AgentCore Gateway（MCP）から呼び出される経過観察管理Lambda関数
    
    Args:
        event: MCPツール呼び出しパラメータ
        context: Lambda実行コンテキスト（ツール名を含む）
    
    Returns:
        MCP形式のレスポンス
    """
```

### MCP Tools

#### AddObservation
```python
def add_observation(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    新しい経過観察記録を作成
    
    Args:
        parameters: {
            "userId": str,
            "title": str,
            "description": str,
            "priority": int (1-5),
            "startDatetime": str (ISO 8601),
            "targetDatetime": str (ISO 8601),
            "frequency": str (ISO 8601 Duration),
            "checkItems": List[str]
        }
    
    Returns:
        作成された経過観察記録
    """
```

#### GetObservation
```python
def get_observation(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定された経過観察記録を取得
    
    Args:
        parameters: {
            "userId": str,
            "observationId": str
        }
    
    Returns:
        経過観察記録の詳細
    """
```

#### GetObservationsInRange
```python
def get_observations_in_range(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    指定期間内の経過観察記録を効率的に取得
    
    Args:
        parameters: {
            "userId": str,
            "startDate": str (YYYY-MM-DD),
            "endDate": str (YYYY-MM-DD)
        }
    
    Returns:
        期間内の経過観察記録リスト
        
    Note:
        日付範囲の各日に対して個別クエリを実行し、
        observationIdの日付部分を条件に含めることで効率的な取得を実現
    """
```

#### GetObservationsInProgress
```python
def get_observations_in_progress(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    進行中の経過観察記録を取得
    
    Args:
        parameters: {
            "userId": str
        }
    
    Returns:
        進行中の経過観察記録リスト
    """
```

#### UpdateObservation
```python
def update_observation(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    経過観察記録を差分更新
    
    Args:
        parameters: {
            "userId": str,
            "observationId": str,
            "title": str (optional),
            "description": str (optional),
            "priority": int (optional),
            "targetDatetime": str (optional),
            "frequency": str (optional),
            "checkItems": List[str] (optional)
        }
    
    Returns:
        更新された経過観察記録
    """
```

#### AddObservationProgress
```python
def add_observation_progress(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    経過観察の進捗ログを追加
    
    Args:
        parameters: {
            "userId": str,
            "observationId": str,
            "date": str (YYYY-MM-DD),
            "note": str
        }
    
    Returns:
        更新された経過観察記録
    """
```

#### CompleteObservation
```python
def complete_observation(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    経過観察を完了状態にする
    
    Args:
        parameters: {
            "userId": str,
            "observationId": str,
            "conclusion": str
        }
    
    Returns:
        完了した経過観察記録
    """
```

#### CancelObservation
```python
def cancel_observation(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    経過観察をキャンセル状態にする
    
    Args:
        parameters: {
            "userId": str,
            "observationId": str,
            "conclusion": str
        }
    
    Returns:
        キャンセルされた経過観察記録
    """
```

## データモデル

### DynamoDB テーブル: healthmate-observations

**テーブル構造**:
```python
{
    "TableName": "healthmate-observations",
    "KeySchema": [
        {"AttributeName": "userId", "KeyType": "HASH"},      # Partition Key
        {"AttributeName": "observationId", "KeyType": "RANGE"}  # Sort Key
    ],
    "LocalSecondaryIndexes": [
        {
            "IndexName": "InProgressIndex",
            "KeySchema": [
                {"AttributeName": "userId", "KeyType": "HASH"},
                {"AttributeName": "in_progress", "KeyType": "RANGE"}
            ],
            "Projection": {"ProjectionType": "ALL"}
        }
    ]
}
```

**データ項目**:
```python
{
    "userId": "user123",                           # Partition Key
    "observationId": "OBS#2025-12-28-001",       # Sort Key (自動生成、開始日ベース)
    "title": "腰痛と背中ストレッチの相関チェック",
    "description": "毎日のストレッチで背中のストレッチをもう少し入念にやりましょう",
    "priority": 3,                                 # 1-5の範囲
    "status": "IN_PROGRESS",                       # IN_PROGRESS, COMPLETED, CANCELLED
    "in_progress": True,                           # LSI用（IN_PROGRESS時のみ存在）
    "startDatetime": "2025-12-28T00:00:00Z",
    "targetDatetime": "2025-12-30T00:00:00Z",
    "frequency": "P1D",                            # ISO 8601 Duration
    "checkItems": [
        "ストレッチの実施状況",
        "腰痛の状況"
    ],
    "progressLogs": [
        {
            "date": "2025-12-28",
            "note": "ストレッチ実施済み、ストレッチ直後に痛み緩和",
            "recordedAt": "2025-12-28T12:31:00Z"
        }
    ],
    "conclusion": null,                            # 完了時またはキャンセル時に設定
    "createdAt": "2025-12-28T00:00:00Z",
    "updatedAt": "2025-12-28T00:00:00Z"
}
```

### データアクセスパターン

1. **ユーザーの特定経過観察取得**: `userId` + `observationId`
2. **ユーザーの進行中経過観察取得**: LSI `InProgressIndex` を使用
3. **ユーザーの期間指定経過観察取得**: 日付範囲の各日に対して `userId` + `observationId` の日付部分でクエリ

### observationId生成ルール

```python
def generate_observation_id(start_datetime: str) -> str:
    """
    経過観察IDを生成
    
    Format: OBS#{YYYY-MM-DD}-{sequential_number}
    Example: OBS#2025-12-28-001
    
    Args:
        start_datetime: 経過観察開始日時 (ISO 8601形式)
    
    Returns:
        生成されたobservationId
    """
    from datetime import datetime
    import boto3
    
    # 開始日時から日付部分を抽出
    start_date = datetime.fromisoformat(start_datetime.replace('Z', '+00:00')).date()
    date_str = start_date.strftime("%Y-%m-%d")
    
    # 同じ日の既存記録数を確認して連番を決定
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('healthmate-observations')
    
    # 同じ日付で始まるobservationIdの数を取得
    response = table.query(
        KeyConditionExpression=Key('userId').eq(user_id) & 
                              Key('observationId').begins_with(f'OBS#{date_str}')
    )
    
    # 連番を決定（001から開始）
    sequence_number = len(response['Items']) + 1
    sequence_str = f"{sequence_number:03d}"
    
    return f"OBS#{date_str}-{sequence_str}"
```

### GetObservationsInRangeの効率的クエリ

```python
def get_observations_in_range(user_id: str, start_date: str, end_date: str) -> List[Dict]:
    """
    指定期間内の経過観察記録を効率的に取得
    
    Args:
        user_id: ユーザーID
        start_date: 開始日 (YYYY-MM-DD)
        end_date: 終了日 (YYYY-MM-DD)
    
    Returns:
        期間内の経過観察記録リスト
    """
    from datetime import datetime, timedelta
    
    observations = []
    current_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # 日付範囲の各日に対して個別クエリを実行
    while current_date <= end_date_obj:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # その日に開始された経過観察記録を取得
        response = table.query(
            KeyConditionExpression=Key('userId').eq(user_id) & 
                                  Key('observationId').begins_with(f'OBS#{date_str}')
        )
        
        observations.extend(response['Items'])
        current_date += timedelta(days=1)
    
    return observations
```

## 正確性プロパティ

*プロパティは、システムのすべての有効な実行において真であるべき特性や動作の形式的な記述です。プロパティは、人間が読める仕様と機械で検証可能な正確性保証の橋渡しとなります。*

### プロパティ分析の事前作業

<function_calls>
<invoke name="prework">
<parameter name="featureName">health-observation-management