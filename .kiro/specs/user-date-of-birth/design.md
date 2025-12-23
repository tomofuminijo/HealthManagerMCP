# 設計ドキュメント

## 概要

Healthmate-HealthManagerサービスの既存ユーザー管理MCPツール（AddUser、UpdateUser、GetUser）に生年月日（dateOfBirth）フィールドを追加します。この機能により、AIエージェントが年齢に基づいたパーソナライズされた健康アドバイスを提供できるようになります。

## アーキテクチャ

### 既存システムの概要

現在のユーザー管理システムは以下の構成になっています：

```
MCP Client (AI Agent)
    ↓ (HTTP Request)
AgentCore Gateway
    ↓ (Lambda Invoke)
UserLambda (lambda/user/handler.py)
    ↓ (DynamoDB Operations)
healthmate-users Table
```

### 変更対象コンポーネント

1. **MCPスキーマファイル**: `mcp-schema/user-management-mcp-schema.json`
2. **Lambda関数**: `lambda/user/handler.py`
3. **DynamoDBテーブル**: `healthmate-users` (スキーマ変更なし、新フィールド追加のみ)

## コンポーネントと インターフェース

### MCPスキーマの変更

#### AddUserツール
```json
{
  "name": "AddUser",
  "description": "新しいユーザー情報を作成する",
  "inputSchema": {
    "type": "object",
    "properties": {
      "userId": {"type": "string", "description": "ユーザーID（Cognito User ID）"},
      "username": {"type": "string", "description": "ユーザー名"},
      "email": {"type": "string", "description": "メールアドレス"},
      "dateOfBirth": {
        "type": "string",
        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
        "description": "生年月日（YYYY-MM-DD形式）"
      }
    },
    "required": ["userId", "username"]
  }
}
```

#### UpdateUserツール
```json
{
  "name": "UpdateUser",
  "description": "ユーザー情報を更新する",
  "inputSchema": {
    "type": "object",
    "properties": {
      "userId": {"type": "string", "description": "ユーザーID"},
      "username": {"type": "string", "description": "ユーザー名"},
      "email": {"type": "string", "description": "メールアドレス"},
      "dateOfBirth": {
        "type": "string",
        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
        "description": "生年月日（YYYY-MM-DD形式）"
      },
      "lastLoginAt": {"type": "string", "description": "最終ログイン日時"}
    },
    "required": ["userId"]
  }
}
```

### Lambda関数の変更

#### add_user関数の変更
```python
def add_user(parameters: Dict[str, Any]) -> Dict[str, Any]:
    user_id = parameters.get("userId")
    username = parameters.get("username")
    email = parameters.get("email", "")
    date_of_birth = parameters.get("dateOfBirth")  # 新規追加
    
    # バリデーション
    if not user_id or not username:
        raise ValueError("userId and username are required")
    
    # 生年月日のバリデーション（提供された場合のみ）
    if date_of_birth is not None:
        validate_date_of_birth(date_of_birth)
    
    # DynamoDBアイテム構築
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
```

#### update_user関数の変更
```python
def update_user(parameters: Dict[str, Any]) -> Dict[str, Any]:
    user_id = parameters.get("userId")
    username = parameters.get("username")
    email = parameters.get("email")
    date_of_birth = parameters.get("dateOfBirth")  # 新規追加
    last_login_at = parameters.get("lastLoginAt")
    
    # 更新式の構築
    update_expression_parts = []
    expression_attribute_values = {}
    
    if date_of_birth is not None:
        if date_of_birth == "":  # 空文字列の場合は削除
            update_expression_parts.append("REMOVE dateOfBirth")
        else:
            validate_date_of_birth(date_of_birth)
            update_expression_parts.append("dateOfBirth = :dateOfBirth")
            expression_attribute_values[":dateOfBirth"] = date_of_birth
```

#### get_user関数の変更
```python
def get_user(parameters: Dict[str, Any]) -> Dict[str, Any]:
    # 既存の処理...
    
    if "Item" in response:
        user = response["Item"]
        return {
            "success": True,
            "user": {
                "userId": user.get("userId"),
                "username": user.get("username"),
                "email": user.get("email", ""),
                "dateOfBirth": user.get("dateOfBirth"),  # 新規追加（存在しない場合はNone）
                "createdAt": user.get("createdAt"),
                "lastLoginAt": user.get("lastLoginAt"),
            }
        }
```

### データ検証関数

```python
def validate_date_of_birth(date_of_birth: str) -> None:
    """
    生年月日の検証を行う
    
    Args:
        date_of_birth: YYYY-MM-DD形式の日付文字列
        
    Raises:
        ValueError: 無効な日付形式または値の場合
    """
    import re
    from datetime import datetime, date
    
    # 形式チェック
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
        if "time data" in str(e):
            raise ValueError("無効な日付です。正しい日付を入力してください")
        raise
```

## データモデル

### DynamoDBテーブルスキーマ

既存の`healthmate-users`テーブルに新しいフィールドを追加：

```python
{
    "userId": "string",        # パーティションキー（既存）
    "username": "string",      # 既存
    "email": "string",         # 既存
    "dateOfBirth": "string",   # 新規追加（オプション、YYYY-MM-DD形式）
    "createdAt": "string",     # 既存
    "lastLoginAt": "string"    # 既存
}
```

### データ例

#### 生年月日ありのユーザー
```json
{
    "userId": "user123",
    "username": "田中太郎",
    "email": "tanaka@example.com",
    "dateOfBirth": "1985-03-15",
    "createdAt": "2024-01-01T00:00:00Z",
    "lastLoginAt": "2024-12-23T10:30:00Z"
}
```

#### 生年月日なしのユーザー（既存ユーザー）
```json
{
    "userId": "user456",
    "username": "佐藤花子",
    "email": "sato@example.com",
    "createdAt": "2023-06-15T00:00:00Z",
    "lastLoginAt": "2024-12-22T15:45:00Z"
}
```

## エラーハンドリング

### 検証エラーのパターン

1. **形式エラー**: `"生年月日はYYYY-MM-DD形式で入力してください"`
2. **無効な日付**: `"無効な日付です。正しい日付を入力してください"`
3. **未来の日付**: `"生年月日は過去の日付である必要があります"`
4. **非現実的な過去**: `"生年月日は1900年以降の日付を入力してください"`

### エラーレスポンス形式

```json
{
    "success": false,
    "error": "生年月日はYYYY-MM-DD形式で入力してください",
    "errorType": "ValidationError",
    "field": "dateOfBirth"
}
```

## テスト戦略

### 単体テスト

- **日付検証関数のテスト**: 有効/無効な日付パターンのテスト
- **Lambda関数のテスト**: 生年月日ありなしの両パターン
- **エラーハンドリングのテスト**: 各種検証エラーのテスト

### 統合テスト

- **MCP経由のE2Eテスト**: 実際のAIエージェントからの呼び出しテスト
- **後方互換性テスト**: 既存ユーザーデータでの動作確認
- **DynamoDB操作テスト**: 実際のAWS環境でのCRUD操作テスト

### プロパティベーステスト

プロパティベーステストでは、以下の正当性プロパティを検証します：

*プロパティとは、システムのすべての有効な実行において真であるべき特性や動作の形式的な記述です。プロパティは人間が読める仕様と機械で検証可能な正当性保証の橋渡しとなります。*

## 正当性プロパティ

### プロパティ1: 有効な生年月日の保存と取得
*任意の*有効な生年月日（YYYY-MM-DD形式の過去の日付）について、AddUserまたはUpdateUserで保存した後にGetUserで取得すると、同じ値が返される
**検証対象: 要件1.1、2.1、3.1、3.3**

### プロパティ2: 生年月日なしでのユーザー操作
*任意の*ユーザーについて、生年月日を提供せずにAddUserで作成し、その後GetUserで取得すると、生年月日フィールドはnullまたは省略される
**検証対象: 要件1.2、3.2**

### プロパティ3: 日付検証の一貫性
*任意の*無効な日付形式、未来の日付、または1900年以前の日付について、AddUserまたはUpdateUserで提供すると、適切な検証エラーが返される
**検証対象: 要件1.3、1.4、2.4、5.1、5.2、5.3、5.4**

### プロパティ4: 生年月日の更新と置き換え
*任意の*既存ユーザーについて、生年月日を更新すると、以前の値が新しい値に置き換えられる
**検証対象: 要件2.2**

### プロパティ5: 生年月日フィールドの削除
*任意の*生年月日を持つユーザーについて、空文字列またはnullで生年月日を更新すると、フィールドが削除される
**検証対象: 要件2.3**

### プロパティ6: 部分更新での他フィールド保持
*任意の*既存ユーザーについて、生年月日のみを更新すると、他のフィールド（username、email等）は変更されない
**検証対象: 要件6.3**

### プロパティ7: 後方互換性の維持
*任意の*生年月日のないユーザーについて、全ての操作（AddUser、UpdateUser、GetUser）が正常に動作し、エラーを返さない
**検証対象: 要件6.1、6.2、6.4**

## テスト戦略

### 単体テスト
- **日付検証関数のテスト**: 有効/無効な日付パターンのテスト
- **Lambda関数のテスト**: 生年月日ありなしの両パターン
- **エラーハンドリングのテスト**: 各種検証エラーのテスト

### プロパティベーステスト
- **テストフレームワーク**: pytest + hypothesis
- **実行回数**: 各プロパティあたり最低100回の反復実行
- **テストタグ**: **Feature: user-date-of-birth, Property {番号}: {プロパティテキスト}**
- **データ生成**: 有効/無効な日付、ユーザーID、ユーザー名の自動生成

### 統合テスト
- **MCP経由のE2Eテスト**: 実際のAIエージェントからの呼び出しテスト
- **後方互換性テスト**: 既存ユーザーデータでの動作確認
- **DynamoDB操作テスト**: 実際のAWS環境でのCRUD操作テスト