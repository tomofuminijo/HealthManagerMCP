# 設計書

## 概要

JournalManagement機能は、HealthManagerサービスに新しく追加される独立したMCPツールセットです。既存のコードベースに影響を与えることなく、新しいLambda関数、DynamoDBテーブル、MCPスキーマを追加して実装されます。ユーザーの毎日の振り返り（日記）を管理し、AIが自動生成するタグとともにメンタルヘルス分析をサポートします。

## アーキテクチャ

### システム構成

```mermaid
graph TB
    subgraph "外部クライアント"
        AI[AIエージェント<br/>CoachAI/ChatGPT/Claude]
    end
    
    subgraph "HealthManager MCP"
        Gateway[AgentCore Gateway]
        JournalLambda[Journal Lambda<br/>journal/handler.py]
    end
    
    subgraph "データストレージ"
        JournalTable[DynamoDB<br/>healthmate-journals]
    end
    
    subgraph "認証"
        Cognito[Cognito User Pool<br/>from Healthmate-Core]
    end
    
    AI -->|MCP Call with userId| Gateway
    Gateway -->|Invoke with userId| JournalLambda
    JournalLambda -->|Query/Put| JournalTable
    
    Note: JWT認証とユーザーID抽出はGatewayが処理
```

### 新規追加コンポーネント

1. **Lambda関数**: `lambda/journal/handler.py`
2. **DynamoDBテーブル**: `healthmate-journals`
3. **MCPスキーマ**: `mcp-schema/journal-management-mcp-schema.json`
4. **CDK構成**: 既存スタックに新しいリソースを追加

## コンポーネントとインターフェース

### Lambda関数設計

#### ファイル構造
```
lambda/
├── journal/
│   └── handler.py          # 新規作成
├── user/
│   └── handler.py          # 既存（変更なし）
├── health_goal/
│   └── handler.py          # 既存（変更なし）
├── health_policy/
│   └── handler.py          # 既存（変更なし）
└── activity/
    └── handler.py          # 既存（変更なし）
```

#### Lambda関数インターフェース

```python
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Journal Management Lambda Handler
    
    AgentCore Gateway（MCP）から呼び出され、日記データのCRUD操作を実行します。
    
    Args:
        event: AgentCore Gatewayからのイベント（MCPツール呼び出し）
               パラメータが直接含まれる（userIdを含む）
        context: Lambda実行コンテキスト
                context.client_context.custom['bedrockAgentCoreToolName']からツール名を取得
        
    Returns:
        {
            "success": bool,
            "data": dict,         # Tool response data
            "message": str        # Success/error message
        }
    """
    
    # ログ設定（既存パターンに準拠）
    logger.debug(f"Received event: {json.dumps(event, default=str)}")
    
    try:
        # AgentCore Gateway（MCP）形式のイベントを処理
        parameters = event.copy()
        
        # userIdの検証（必須）
        if "userId" not in parameters:
            raise ValueError("userId is required for all journal operations")
        
        user_id = parameters["userId"]
        logger.info(f"Processing request for userId: {user_id}")
        
        # contextからツール名を取得（既存パターンに準拠）
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
        # バリデーションエラー（既存パターンに準拠）
        error_msg = f"Validation error: {str(e)}"
        logger.warning(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "errorType": "ValidationError"
        }
    except ClientError as e:
        # DynamoDBエラー（既存パターンに準拠）
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
        # その他のエラー（既存パターンに準拠）
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": "予期しないエラーが発生しました。しばらくしてから再度お試しください。",
            "errorType": "InternalError"
        }
```

#### ログ設定（既存パターンに準拠）

```python
import logging
import os

# ログ設定
log_level = os.environ.get("LOG_LEVEL", "INFO")
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, log_level.upper()))

# CloudWatch Logsハンドラーが自動的に設定されるため、追加設定は不要
```

#### DynamoDB設定（既存パターンに準拠）

```python
import boto3
from botocore.config import Config

# DynamoDBクライアント（指数バックオフ付き再試行設定）
config = Config(
    retries={
        "max_attempts": 3,
        "mode": "standard",  # 指数バックオフ
    }
)

dynamodb = boto3.resource("dynamodb", config=config)
table_name = os.environ.get("JOURNALS_TABLE_NAME", "healthmate-journals")
table = dynamodb.Table(table_name)
```

#### サポートするMCPツール

1. **getJournal**: 特定日の日記取得
2. **getJournalsInRange**: 日付範囲の日記取得
3. **addJournal**: 日記追加（既存エントリーへの追記含む）
4. **updateJournal**: 日記更新（完全置換）
5. **deleteJournal**: 日記削除

### DynamoDBテーブル設計

#### テーブル構造: `healthmate-journals`

```python
{
    "TableName": "healthmate-journals",
    "KeySchema": [
        {
            "AttributeName": "userId",
            "KeyType": "HASH"      # Partition Key
        },
        {
            "AttributeName": "date", 
            "KeyType": "RANGE"     # Sort Key (YYYY-MM-DD)
        }
    ],
    "AttributeDefinitions": [
        {
            "AttributeName": "userId",
            "AttributeType": "S"
        },
        {
            "AttributeName": "date",
            "AttributeType": "S"
        }
    ]
}
```

#### データモデル

```python
{
    "userId": "user123",                    # Partition Key
    "date": "2024-12-27",                  # Sort Key (YYYY-MM-DD)
    "content": "今日は...",                 # 振り返り本文
    "moodScore": 4,                        # 1-5の気分スコア
    "tags": [                              # AI自動生成タグ
        "Coding",
        "Happy", 
        "Productive",
        "Sunny"
    ],
    "createdAt": "2024-12-27T10:30:00Z",   # ISO 8601
    "updatedAt": "2024-12-27T10:30:00Z"    # ISO 8601
}
```

### タグ管理

#### タグ保存仕様

```python
def store_tags(provided_tags: List[str]) -> List[str]:
    """
    AIクライアントから提供されたタグをそのまま保存
    
    Args:
        provided_tags: AIクライアントが指定したタグリスト
        
    Returns:
        保存されたタグリスト（提供されたものをそのまま）
    """
```

#### タグ形式要件

- **提供元**: AIクライアント（CoachAI、ChatGPT、Claude等）
- **形式**: PascalCase英語（例: `WorkFromHome`, `MorningRun`）
- **数量**: 3-5個（AIクライアント側で制御）
- **カテゴリ**: Activities, Emotions, Health, Environment（AIクライアント側で分類）
- **検証**: 基本的な形式チェックのみ（文字列配列、空でない）

## データモデル

### Journal Entry Schema

```typescript
interface JournalEntry {
    userId: string;           // ユーザーID（パーティションキー）
    date: string;            // 日付 YYYY-MM-DD（ソートキー）
    content: string;         // 振り返り本文
    moodScore: number;       // 1-5の気分スコア
    tags: string[];          // AI自動生成タグ（3-5個）
    createdAt: string;       // 作成日時（ISO 8601）
    updatedAt: string;       // 更新日時（ISO 8601）
}
```

### MCP Tool Parameters

#### getJournal
```typescript
{
    userId: string;
    date: string;           // YYYY-MM-DD
}
```

#### getJournalsInRange
```typescript
{
    userId: string;
    startDate: string;      // YYYY-MM-DD
    endDate: string;        // YYYY-MM-DD
}
```

#### addJournal
```typescript
{
    userId: string;
    date?: string;          // YYYY-MM-DD（省略時は今日）
    content: string;
    moodScore?: number;     // 1-5（省略可能）
    tags?: string[];        // AIクライアントが指定（省略可能）
}
```

#### updateJournal
```typescript
{
    userId: string;
    date: string;           // YYYY-MM-DD
    content?: string;
    moodScore?: number;     // 1-5
    tags?: string[];        // AIクライアントが指定（省略可能）
}
```

#### deleteJournal
```typescript
{
    userId: string;
    date: string;           // YYYY-MM-DD
}
```

## 正確性プロパティ

*プロパティとは、システムのすべての有効な実行において真であるべき特性や動作です。プロパティは、人間が読める仕様と機械で検証可能な正確性保証の橋渡しとして機能します。*

### プロパティ 1: 日記エントリーの作成と取得
*任意の* ユーザーIDと日付の組み合わせに対して、日記エントリーを作成した後、同じユーザーIDと日付で取得すると、作成した内容が含まれている
**検証: 要件 1.1, 3.1**

### プロパティ 2: 日記追記の累積性
*任意の* 既存の日記エントリーに対してaddJournalを実行すると、既存のコンテンツに新しいコンテンツが追記され、両方の内容が保持される
**検証: 要件 1.4**

### プロパティ 3: タグ保存の一貫性
*任意の* AIクライアントから提供されたタグリストに対して、そのタグが文字列配列として正確に保存され、取得時に同じ順序で返される
**検証: 要件 1.3, 2.6, 6.8**

### プロパティ 4: DynamoDBキー構造の一貫性
*任意の* 日記エントリーに対して、ユーザーIDがパーティションキーとして、日付（YYYY-MM-DD）がソートキーとしてそのまま使用される
**検証: 要件 2.1, 2.2, 2.3**

### プロパティ 5: 気分スコア検証
*任意の* 1-5以外の値を気分スコアとして提供した場合、バリデーションエラーが返され、1-5の整数の場合は正常に保存される
**検証: 要件 1.2, 2.5, 7.1, 7.2**

### プロパティ 6: タイムスタンプ管理
*任意の* 日記エントリーに対して、作成時にcreatedAtとupdatedAtがISO 8601形式で設定され、更新時にはupdatedAtのみが更新されcreatedAtは保持される
**検証: 要件 2.7, 2.8, 4.2, 4.3**

### プロパティ 7: 日付範囲クエリの完全性
*任意の* ユーザーと日付範囲に対して、範囲内のすべての日記エントリーが時系列順で返され、範囲外のエントリーは含まれない
**検証: 要件 3.2, 3.5**

### プロパティ 8: 日記更新の完全性
*任意の* 既存の日記エントリーに対して、更新操作を行うと、指定されたフィールド（コンテンツ、気分スコア、タグ）が新しい値で置換される
**検証: 要件 4.1, 4.4**

### プロパティ 9: 日記削除の確実性
*任意の* 既存の日記エントリーに対して、削除操作を行った後、その日記を取得しようとすると「見つかりません」エラーが返され、復旧はできない
**検証: 要件 5.1, 5.4, 5.5**

### プロパティ 10: 存在しないエントリーのエラー処理
*任意の* 存在しない日付に対して、取得・更新・削除操作を行うと、適切な「見つかりません」エラーメッセージが返される
**検証: 要件 3.3, 4.5, 5.3**

### プロパティ 11: ユーザー分離とアクセス制御
*任意の* ユーザーAの日記に対して、ユーザーBとしてアクセス・更新・削除しようとすると、適切なエラーが返される（Gateway側で認証処理済み）
**検証: 要件 5.2, 7.7**

### プロパティ 12: 日付検証
*任意の* 無効な日付形式または未来の日付を提供した場合、適切なバリデーションエラーが返される
**検証: 要件 7.3, 7.4**

### プロパティ 13: コンテンツ制限とサニタイゼーション
*任意の* 日記コンテンツに対して、長さ制限を超える場合は切り詰めまたは拒否され、セキュリティ脆弱性のあるコンテンツは適切にサニタイズされる
**検証: 要件 7.5, 7.6**

### プロパティ 14: 日付範囲制限
*任意の* 365日を超える日付範囲クエリに対して、適切な制限エラーが返される
**検証: 要件 3.4**

### プロパティ 15: MCPツール認証
*任意の* MCPツール呼び出しに対して、AgentCore Gatewayが認証を処理し、Lambda関数には認証済みのuserIdが提供される
**検証: 要件 6.6, 6.7**

## エラーハンドリング

### エラー分類と対応

```python
ERROR_PATTERNS = {
    "VALIDATION_ERROR": {
        "mood_score_invalid": "気分スコアは1から5の整数である必要があります",
        "date_format_invalid": "日付はYYYY-MM-DD形式である必要があります", 
        "date_future": "未来の日付は指定できません",
        "content_too_long": "日記の内容が長すぎます（最大10000文字）"
    },
    "RESOURCE_NOT_FOUND": {
        "journal_not_found": "指定された日付の日記が見つかりません"
    },
    "AUTHENTICATION_ERROR": {
        "user_mismatch": "他のユーザーの日記にはアクセスできません"
    },
    "INTERNAL_ERROR": {
        "dynamodb_error": "データベースエラーが発生しました"
    }
}
```

### エラーレスポンス形式

```python
{
    "success": False,
    "error": "VALIDATION_ERROR",
    "message": "気分スコアは1から5の整数である必要があります",
    "details": {
        "field": "moodScore",
        "provided": "6",
        "expected": "1-5"
    }
}
```

## テスト戦略

### 単体テスト

#### Lambda関数テスト
- 各MCPツールの正常系・異常系テスト
- DynamoDB操作のモックテスト
- タグ保存・検証ロジックテスト
- ユーザーID検証テスト（Gatewayから提供される）

#### データ検証テスト
- 日付形式検証
- 気分スコア範囲検証
- コンテンツ長制限テスト
- タグ形式検証

### 統合テスト

#### MCP統合テスト
- 実際のDynamoDBを使用したE2Eテスト
- 複数ツール間の連携テスト
- AgentCore Gateway経由の統合テスト

#### パフォーマンステスト
- 大量データでの範囲クエリテスト
- 同時アクセステスト
- レスポンス時間測定

### プロパティベーステスト

#### 正確性プロパティ

**Property 1: 日記追加の一意性**
*任意の* ユーザーIDと日付の組み合わせに対して、日記を追加した後、その日付で日記を取得すると、追加した内容が含まれている

**Property 2: 日記更新の完全性**
*任意の* 既存の日記エントリーに対して、更新操作を行った後、取得した日記は新しい内容を反映し、updatedAtが更新されている

**Property 3: 日記削除の確実性**
*任意の* 既存の日記エントリーに対して、削除操作を行った後、その日記を取得しようとすると「見つかりません」エラーが返される

**Property 4: 日付範囲クエリの完全性**
*任意の* ユーザーと日付範囲に対して、範囲内のすべての日記が返され、範囲外の日記は含まれない

**Property 5: タグ生成の一貫性**
*任意の* 日記内容に対して、タグ生成を複数回実行しても、同じカテゴリの概念には同じタグが生成される

**Property 6: 気分スコア検証**
*任意の* 1-5以外の気分スコアを提供した場合、バリデーションエラーが返される

**Property 7: ユーザー分離**
*任意の* ユーザーAの日記に対して、ユーザーBのJWTトークンでアクセスしようとすると、認証エラーが返される

**Property 8: 日記追記の累積性**
*任意の* 既存の日記に対してaddJournalを実行すると、既存の内容に新しい内容が追記される

### テスト実装パターン

#### 単体テスト例
```python
def test_add_journal_success():
    """日記追加の正常系テスト"""
    event = {
        "tool": "addJournal",
        "parameters": {
            "userId": "test-user",
            "date": "2024-12-27",
            "content": "今日は良い一日でした",
            "moodScore": 4
        }
    }
    
    result = lambda_handler(event, None)
    
    assert result["success"] is True
    assert "journalId" in result["data"]
    assert len(result["data"]["tags"]) >= 0  # タグはAIクライアントが提供
```

#### プロパティテスト例
```python
@given(
    user_id=st.text(min_size=1),
    date=st.dates().map(lambda d: d.strftime("%Y-%m-%d")),
    content=st.text(min_size=1, max_size=1000),
    mood_score=st.integers(min_value=1, max_value=5)
)
def test_journal_roundtrip_property(user_id, date, content, mood_score):
    """Property 1: 日記追加→取得のラウンドトリップ"""
    # 日記を追加
    add_result = add_journal(user_id, date, content, mood_score)
    assume(add_result["success"])
    
    # 同じ日記を取得
    get_result = get_journal(user_id, date)
    
    # 追加した内容が取得できることを確認
    assert get_result["success"]
    assert content in get_result["data"]["content"]
    assert get_result["data"]["moodScore"] == mood_score
```

## 統合ポイント

### 既存システムとの統合

#### 認証統合
- AgentCore Gatewayが JWT認証とユーザーID抽出を処理
- Lambda関数には認証済みのuserIdが提供される
- 既存の認証パターンとの一貫性を維持

#### インフラストラクチャ統合
- 既存のCDKスタックに新しいリソースを追加
- 既存のLambda関数と同じIAMロールパターンを使用
- 既存のDynamoDBテーブルと同じ命名規則を適用

#### MCP統合
- 既存のAgentCore Gatewayに新しいツールを追加
- 既存のMCPスキーマ形式に準拠
- 既存のエラーハンドリングパターンを踏襲

### 外部サービス連携

#### CoachAIサービス連携
- MCPクライアントとして日記データにアクセス
- ユーザーの振り返り内容を基にしたパーソナライズされたアドバイス
- メンタルヘルス傾向分析のためのデータ提供
- 振り返り内容に基づくタグの生成と提供

#### Frontendサービス連携
- Web UI経由での日記入力・表示機能
- 気分スコアの可視化
- タグベースの検索・フィルタリング機能

### データ分析連携

#### メンタルヘルス分析
- 気分スコアの時系列分析
- タグベースの活動パターン分析
- 他の健康データ（活動、目標）との相関分析

#### レポート生成
- 週次・月次の振り返りサマリー
- 気分の変化傾向レポート
- 改善提案の自動生成