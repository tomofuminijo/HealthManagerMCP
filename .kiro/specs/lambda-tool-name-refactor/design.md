# Lambda関数ツール名取得リファクタリング設計

## 概要

Healthmate-HealthManagerサービスの全Lambda関数において、現在の複雑なパラメータベースのツール名推測処理を、context.client_context.customから直接ツール名を取得する統一された仕組みに置き換えます。これにより、コードの保守性と可読性を向上させ、エラーの可能性を減らします。

## アーキテクチャ

### 現在のアーキテクチャ

```
Lambda Handler
    ↓
Parameter Analysis (複雑な推測ロジック)
    ↓
Tool Name Inference
    ↓
Function Dispatch
```

### 新しいアーキテクチャ

```
Lambda Handler
    ↓
Context Tool Name Extraction (シンプルな取得)
    ↓
Tool Name Normalization
    ↓
Function Dispatch
```

## コンポーネントとインターフェース

### 1. ツール名抽出コンポーネント

**責任**: contextからツール名を抽出し、正規化する

```python
def extract_tool_name(context: Any) -> str:
    """
    contextからツール名を抽出し、正規化する
    
    Args:
        context: Lambda実行コンテキスト
        
    Returns:
        正規化されたツール名
        
    Raises:
        ValueError: ツール名が取得できない場合
    """
```

### 2. 関数ディスパッチコンポーネント

**責任**: ツール名に基づいて適切な処理関数を呼び出す

```python
def dispatch_tool_function(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    ツール名に基づいて適切な関数を呼び出す
    
    Args:
        tool_name: 正規化されたツール名
        parameters: 処理パラメータ
        
    Returns:
        処理結果
        
    Raises:
        ValueError: 未知のツール名の場合
    """
```

## データモデル

### ツール名マッピング

各Lambda関数で以下のマッピングを使用：

#### UserLambda
```python
TOOL_FUNCTION_MAP = {
    "AddUser": add_user,
    "UpdateUser": update_user,
    "GetUser": get_user
}
```

#### HealthGoalLambda
```python
TOOL_FUNCTION_MAP = {
    "AddGoal": add_goal,
    "UpdateGoal": update_goal,
    "DeleteGoal": delete_goal,
    "GetGoals": get_goals
}
```

#### HealthPolicyLambda
```python
TOOL_FUNCTION_MAP = {
    "AddPolicy": add_policy,
    "UpdatePolicy": update_policy,
    "DeletePolicy": delete_policy,
    "GetPolicies": get_policies
}
```

#### ActivityLambda
```python
TOOL_FUNCTION_MAP = {
    "AddActivities": add_activities,
    "UpdateActivity": update_activity,
    "UpdateActivities": update_activities,
    "DeleteActivity": delete_activity,
    "GetActivities": get_activities,
    "GetActivitiesInRange": get_activities_in_range
}
```

## 正確性プロパティ

*プロパティは、システムのすべての有効な実行において真であるべき特性や動作です。プロパティは、人間が読める仕様と機械で検証可能な正確性保証の橋渡しとなります。*
### プロパティ反映

プロパティの冗長性を排除するため、以下の統合を行います：

- 要件2.2-2.4、3.2-3.5、4.2-4.5、5.2-5.7の個別の関数ディスパッチテストは、単一の包括的なプロパティに統合できます
- 要件1.2と1.3の文字列処理ルールは、単一のツール名正規化プロパティに統合できます

**プロパティ1: ツール名正規化の一貫性**
*任意の* 生のツール名文字列に対して、正規化処理は一貫したルールを適用し、'__'での分割と先頭'_'の除去を正しく行う
**検証対象: 要件1.2、1.3**

**プロパティ2: 関数ディスパッチの正確性**
*任意の* 有効なツール名に対して、対応する処理関数が正しく呼び出される
**検証対象: 要件2.2-2.4、3.2-3.5、4.2-4.5、5.2-5.7**

**プロパティ3: レスポンス形式の一貫性**
*任意の* Lambda関数とパラメータの組み合わせに対して、成功時と失敗時のレスポンス形式が一貫している
**検証対象: 要件6.2**

**プロパティ4: ログメッセージの正確性**
*任意の* ツール名とログレベルに対して、出力されるログメッセージに正しいツール名が含まれている
**検証対象: 要件6.4**

## エラーハンドリング

### エラー分類

1. **ツール名取得エラー**: context.client_context.customが存在しない、またはbedrockAgentCoreToolNameが見つからない
2. **ツール名検証エラー**: 取得したツール名が有効なツール名リストに含まれない
3. **関数実行エラー**: 既存のビジネスロジックエラー（DynamoDBエラー、バリデーションエラーなど）

### エラーレスポンス形式

```python
{
    "success": False,
    "error": "エラーメッセージ",
    "errorType": "ToolNameError|ValidationError|DatabaseError|InternalError",
    "errorCode": "オプション：具体的なエラーコード"
}
```

## テスト戦略

### 単体テスト

- ツール名抽出関数のテスト
- ツール名正規化関数のテスト
- 関数ディスパッチロジックのテスト
- エラーハンドリングのテスト

### プロパティベーステスト

プロパティベーステストには**pytest**と**hypothesis**ライブラリを使用します。各プロパティベーステストは最低**100回**の反復実行を行い、以下の形式でタグ付けします：

```python
# **Feature: lambda-tool-name-refactor, Property 1: ツール名正規化の一貫性**
@given(raw_tool_name=text())
def test_tool_name_normalization_consistency(raw_tool_name):
    # テスト実装
```

### 統合テスト

- 各Lambda関数の完全なリクエスト/レスポンスサイクルのテスト
- 既存機能の回帰テスト
- MCPプロトコル互換性テスト