# MCP Schema Definitions

このディレクトリには、Healthmate-HealthManagerが提供するすべてのMCPツールのスキーマ定義が含まれています。

## スキーマファイル

| ファイル | 説明 | 提供ツール |
|---------|------|-----------|
| [`user-management-mcp-schema.json`](user-management-mcp-schema.json) | ユーザー管理 | AddUser, UpdateUser, GetUser |
| [`health-goal-management-mcp-schema.json`](health-goal-management-mcp-schema.json) | 健康目標管理 | AddGoal, UpdateGoal, DeleteGoal, GetGoals |
| [`health-policy-management-mcp-schema.json`](health-policy-management-mcp-schema.json) | 健康ポリシー管理 | AddPolicy, UpdatePolicy, DeletePolicy, GetPolicies |
| [`activity-management-mcp-schema.json`](activity-management-mcp-schema.json) | 活動記録管理 | AddActivities, UpdateActivity, UpdateActivities, DeleteActivity, GetActivities, GetActivitiesInRange |

## スキーマ形式

各スキーマファイルは、[JSON Schema](https://json-schema.org/) 形式でMCPツールの入力パラメータを定義しています。

### 基本構造

```json
[
  {
    "name": "ツール名",
    "description": "ツールの説明",
    "inputSchema": {
      "type": "object",
      "properties": {
        "パラメータ名": {
          "type": "データ型",
          "description": "パラメータの説明"
        }
      },
      "required": ["必須パラメータ"]
    }
  }
]
```

## 使用方法

### AI クライアントでの利用

これらのスキーマファイルは、以下のAIクライアントで直接利用できます：

- **ChatGPT**: Custom Actions として設定
- **Claude**: MCP サーバーとして接続
- **HealthCoachAI**: MCP クライアントとして統合

### 開発者向け

スキーマファイルを使用してAPIクライアントを生成したり、入力検証を行うことができます：

```bash
# スキーマの検証
jq '.' user-management-mcp-schema.json

# 特定のツールのスキーマを抽出
jq '.[] | select(.name == "AddUser")' user-management-mcp-schema.json
```

## 認証

すべてのMCPツールは、Cognito User Poolから取得したJWTトークンによる認証が必要です。

### 認証フロー

1. Cognito User Pool でユーザー認証
2. JWTアクセストークンを取得
3. `Authorization: Bearer <token>` ヘッダーでAPIを呼び出し

## エラーハンドリング

すべてのツールは統一されたエラー形式を返します：

```json
{
  "success": false,
  "error": "エラーの種類",
  "message": "詳細なエラーメッセージ"
}
```

### 共通エラーコード

- `AUTHENTICATION_ERROR`: 認証エラー
- `VALIDATION_ERROR`: 入力データの検証エラー
- `NOT_FOUND`: リソースが見つからない
- `INTERNAL_ERROR`: サーバー内部エラー

## 更新履歴

スキーマファイルの変更は、実装と同時に自動的に反映されます。手動での同期は不要です。

---

**注意**: これらのスキーマファイルは実装の Single Source of Truth です。手動での編集は避け、実装変更時に自動更新されることを前提としてください。