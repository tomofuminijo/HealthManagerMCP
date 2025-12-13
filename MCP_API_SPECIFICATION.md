# HealthManagerMCP API仕様書

## 概要

HealthManagerMCPは、Model Context Protocol (MCP)を使用して健康情報管理機能を提供するサーバーです。本仕様書では、各MCPツールのAPI仕様、リクエスト/レスポンス形式、エラーハンドリングについて詳細に説明します。

## 認証

すべてのAPI呼び出しには、Cognito User Poolから取得したJWTトークンが必要です。

### 認証フロー

1. **OAuth 2.0 Authorization Code Grant**を使用
2. **Cognito User Pool**でユーザー認証
3. **JWTアクセストークン**を取得
4. **Authorization**ヘッダーでトークンを送信

```http
Authorization: Bearer <jwt-access-token>
```

### トークン有効期限

- **アクセストークン**: 1時間
- **リフレッシュトークン**: 30日
- **IDトークン**: 1時間

## 共通仕様

### ベースURL

```
https://<gateway-id>.agentcore.us-west-2.amazonaws.com
```

### リクエスト形式

- **Content-Type**: `application/json`
- **Method**: `POST`
- **Encoding**: UTF-8

### レスポンス形式

```json
{
  "success": true,
  "data": { ... },
  "message": "操作が正常に完了しました"
}
```

### エラーレスポンス

```json
{
  "success": false,
  "error": "エラーの種類",
  "message": "詳細なエラーメッセージ",
  "details": { ... }
}
```

### 共通エラーコード

| エラーコード | 説明 | HTTPステータス |
|-------------|------|---------------|
| `AUTHENTICATION_ERROR` | 認証エラー（無効なJWT） | 401 |
| `AUTHORIZATION_ERROR` | 認可エラー（権限不足） | 403 |
| `VALIDATION_ERROR` | 入力データの検証エラー | 400 |
| `NOT_FOUND` | リソースが見つからない | 404 |
| `INTERNAL_ERROR` | サーバー内部エラー | 500 |
| `RATE_LIMIT_EXCEEDED` | レート制限超過 | 429 |

## 1. User Management API

### 1.1 addUser - ユーザー追加

新しいユーザーを作成します。

**エンドポイント**: `/user-management`

**リクエスト**:
```json
{
  "tool": "addUser",
  "parameters": {
    "name": "田中太郎",
    "email": "tanaka@example.com",
    "dateOfBirth": "1990-05-15",
    "gender": "male",
    "height": 170.5,
    "preferences": {
      "language": "ja",
      "timezone": "Asia/Tokyo",
      "notifications": true
    }
  }
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "userId": "user123",
    "name": "田中太郎",
    "email": "tanaka@example.com",
    "dateOfBirth": "1990-05-15",
    "gender": "male",
    "height": 170.5,
    "preferences": {
      "language": "ja",
      "timezone": "Asia/Tokyo",
      "notifications": true
    },
    "createdAt": "2025-12-14T10:30:00Z",
    "updatedAt": "2025-12-14T10:30:00Z"
  },
  "message": "ユーザーが正常に作成されました"
}
```

### 1.2 updateUser - ユーザー更新

既存のユーザー情報を更新します。

**リクエスト**:
```json
{
  "tool": "updateUser",
  "parameters": {
    "name": "田中太郎",
    "height": 171.0,
    "preferences": {
      "notifications": false
    }
  }
}
```

### 1.3 getUser - ユーザー取得

ユーザー情報を取得します。

**リクエスト**:
```json
{
  "tool": "getUser",
  "parameters": {}
}
```

## 2. Health Goal Management API

### 2.1 addGoal - 健康目標追加

新しい健康目標を作成します。

**エンドポイント**: `/health-goal-management`

**リクエスト**:
```json
{
  "tool": "addGoal",
  "parameters": {
    "title": "100歳まで健康寿命を延ばす",
    "description": "定期的な運動と健康的な食事により、100歳まで自立した生活を送る",
    "goalType": "longevity",
    "targetValue": 100,
    "unit": "years",
    "targetDate": "2090-12-31",
    "priority": "high",
    "status": "active"
  }
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "goalId": "goal-uuid-123",
    "userId": "user123",
    "title": "100歳まで健康寿命を延ばす",
    "description": "定期的な運動と健康的な食事により、100歳まで自立した生活を送る",
    "goalType": "longevity",
    "targetValue": 100,
    "unit": "years",
    "targetDate": "2090-12-31",
    "priority": "high",
    "status": "active",
    "createdAt": "2025-12-14T10:30:00Z",
    "updatedAt": "2025-12-14T10:30:00Z"
  },
  "message": "健康目標が正常に作成されました"
}
```

### 2.2 updateGoal - 健康目標更新

**リクエスト**:
```json
{
  "tool": "updateGoal",
  "parameters": {
    "goalId": "goal-uuid-123",
    "status": "completed",
    "progress": 85.5
  }
}
```

### 2.3 deleteGoal - 健康目標削除

**リクエスト**:
```json
{
  "tool": "deleteGoal",
  "parameters": {
    "goalId": "goal-uuid-123"
  }
}
```

### 2.4 getGoals - 健康目標一覧取得

**リクエスト**:
```json
{
  "tool": "getGoals",
  "parameters": {
    "goalType": "longevity",
    "status": "active",
    "limit": 10
  }
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "goals": [
      {
        "goalId": "goal-uuid-123",
        "title": "100歳まで健康寿命を延ばす",
        "goalType": "longevity",
        "status": "active",
        "progress": 75.0,
        "createdAt": "2025-12-14T10:30:00Z"
      }
    ],
    "count": 1
  },
  "message": "健康目標を取得しました"
}
```

## 3. Health Policy Management API

### 3.1 addPolicy - 健康ポリシー追加

新しい健康ポリシーを作成します。

**エンドポイント**: `/health-policy-management`

**リクエスト**:
```json
{
  "tool": "addPolicy",
  "parameters": {
    "title": "ローカーボダイエット",
    "description": "ローカーボ（低糖質）な食事を基本とする",
    "policyType": "diet",
    "rules": {
      "carb": "low",
      "maxCarbsPerDay": 50,
      "allowedFoods": ["肉", "魚", "野菜", "ナッツ"],
      "restrictedFoods": ["米", "パン", "麺類", "砂糖"]
    },
    "isActive": true,
    "priority": "high"
  }
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "policyId": "policy-uuid-456",
    "userId": "user123",
    "title": "ローカーボダイエット",
    "description": "ローカーボ（低糖質）な食事を基本とする",
    "policyType": "diet",
    "rules": {
      "carb": "low",
      "maxCarbsPerDay": 50,
      "allowedFoods": ["肉", "魚", "野菜", "ナッツ"],
      "restrictedFoods": ["米", "パン", "麺類", "砂糖"]
    },
    "isActive": true,
    "priority": "high",
    "createdAt": "2025-12-14T10:30:00Z",
    "updatedAt": "2025-12-14T10:30:00Z"
  },
  "message": "健康ポリシーが正常に作成されました"
}
```

### 3.2 updatePolicy - 健康ポリシー更新

**リクエスト**:
```json
{
  "tool": "updatePolicy",
  "parameters": {
    "policyId": "policy-uuid-456",
    "isActive": false,
    "rules": {
      "maxCarbsPerDay": 30
    }
  }
}
```

### 3.3 deletePolicy - 健康ポリシー削除

**リクエスト**:
```json
{
  "tool": "deletePolicy",
  "parameters": {
    "policyId": "policy-uuid-456"
  }
}
```

### 3.4 getPolicies - 健康ポリシー一覧取得

**リクエスト**:
```json
{
  "tool": "getPolicies",
  "parameters": {
    "policyType": "diet",
    "isActive": true,
    "limit": 10
  }
}
```

## 4. Activity Management API

### 4.1 addActivities - 活動記録追加

指定した日付に複数の活動を追加します。

**エンドポイント**: `/activity-management`

**リクエスト**:
```json
{
  "tool": "addActivities",
  "parameters": {
    "date": "2025-12-14",
    "operationType": "append",
    "activities": [
      {
        "time": "07:00",
        "activityType": "wakeUp",
        "description": "起床",
        "items": ["自然に目覚めた"]
      },
      {
        "time": "08:00",
        "activityType": "meal",
        "description": "朝食",
        "items": ["卵", "サラダ", "コーヒー"],
        "calories": 350,
        "carbs": 15
      },
      {
        "time": "13:00",
        "activityType": "bowelMovement",
        "description": "排便",
        "items": ["正常な排便"]
      }
    ]
  }
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "userId": "user123",
    "date": "2025-12-14",
    "activities": [
      {
        "time": "07:00",
        "activityType": "wakeUp",
        "description": "起床",
        "items": ["自然に目覚めた"]
      },
      {
        "time": "08:00",
        "activityType": "meal",
        "description": "朝食",
        "items": ["卵", "サラダ", "コーヒー"],
        "calories": 350,
        "carbs": 15
      },
      {
        "time": "13:00",
        "activityType": "bowelMovement",
        "description": "排便",
        "items": ["正常な排便"]
      }
    ],
    "updatedAt": "2025-12-14T10:30:00Z"
  },
  "message": "活動記録が正常に追加されました"
}
```

### 4.2 updateActivity - 特定活動更新

特定の時刻の活動を更新します。

**リクエスト**:
```json
{
  "tool": "updateActivity",
  "parameters": {
    "date": "2025-12-14",
    "time": "08:00",
    "activityType": "meal",
    "description": "朝食（修正）",
    "items": ["卵", "アボカド", "コーヒー"],
    "calories": 400,
    "carbs": 10
  }
}
```

### 4.3 updateActivities - 全活動更新

指定した日付の全活動を置き換えます。

**リクエスト**:
```json
{
  "tool": "updateActivities",
  "parameters": {
    "date": "2025-12-14",
    "activities": [
      {
        "time": "07:00",
        "activityType": "wakeUp",
        "description": "起床",
        "items": ["自然に目覚めた"]
      }
    ]
  }
}
```

### 4.4 deleteActivity - 活動削除

**リクエスト**:
```json
{
  "tool": "deleteActivity",
  "parameters": {
    "date": "2025-12-14",
    "time": "08:00"
  }
}
```

### 4.5 getActivities - 活動記録取得

**リクエスト**:
```json
{
  "tool": "getActivities",
  "parameters": {
    "date": "2025-12-14"
  }
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "userId": "user123",
    "date": "2025-12-14",
    "activities": [
      {
        "time": "07:00",
        "activityType": "wakeUp",
        "description": "起床",
        "items": ["自然に目覚めた"]
      },
      {
        "time": "08:00",
        "activityType": "meal",
        "description": "朝食",
        "items": ["卵", "サラダ", "コーヒー"],
        "calories": 350,
        "carbs": 15
      }
    ],
    "updatedAt": "2025-12-14T10:30:00Z"
  },
  "message": "活動記録を取得しました"
}
```

### 4.6 getActivitiesInRange - 期間内活動記録取得

**リクエスト**:
```json
{
  "tool": "getActivitiesInRange",
  "parameters": {
    "startDate": "2025-12-01",
    "endDate": "2025-12-14",
    "activityType": "meal"
  }
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "userId": "user123",
    "startDate": "2025-12-01",
    "endDate": "2025-12-14",
    "activities": [
      {
        "date": "2025-12-14",
        "activities": [
          {
            "time": "08:00",
            "activityType": "meal",
            "description": "朝食",
            "items": ["卵", "サラダ", "コーヒー"]
          }
        ]
      }
    ],
    "totalDays": 14,
    "daysWithData": 1
  },
  "message": "期間内の活動記録を取得しました"
}
```

## データ型定義

### ActivityType

活動の種類を表す列挙型：

```typescript
type ActivityType = 
  | "wakeUp"        // 起床
  | "sleep"         // 就寝
  | "exercise"      // 運動
  | "meal"          // 食事
  | "snack"         // おやつ
  | "weight"        // 体重測定
  | "bodyFat"       // 体脂肪測定
  | "mood"          // 気分記録
  | "medication"    // 薬の服用
  | "bowelMovement" // 排便
  | "other";        // その他
```

### GoalType

健康目標の種類：

```typescript
type GoalType = 
  | "longevity"     // 長寿
  | "weight"        // 体重管理
  | "fitness"       // フィットネス
  | "nutrition"     // 栄養
  | "mental"        // メンタルヘルス
  | "sleep"         // 睡眠
  | "other";        // その他
```

### PolicyType

健康ポリシーの種類：

```typescript
type PolicyType = 
  | "diet"          // 食事
  | "exercise"      // 運動
  | "sleep"         // 睡眠
  | "medication"    // 薬物療法
  | "lifestyle"     // ライフスタイル
  | "other";        // その他
```

## 使用例

### HealthCoachAI向けの使用例

```python
# 1. ユーザーの健康目標を取得
goals_response = await mcp_client.call_tool(
    "health-goal-management",
    "getGoals",
    {"status": "active"}
)

# 2. 今日の活動記録を取得
activities_response = await mcp_client.call_tool(
    "activity-management", 
    "getActivities",
    {"date": "2025-12-14"}
)

# 3. 健康ポリシーに基づいてアドバイスを生成
policies_response = await mcp_client.call_tool(
    "health-policy-management",
    "getPolicies", 
    {"isActive": True}
)

# 4. AIがアドバイスに基づいて新しい活動を提案
advice_response = await mcp_client.call_tool(
    "activity-management",
    "addActivities",
    {
        "date": "2025-12-15",
        "operationType": "append",
        "activities": [
            {
                "time": "19:00",
                "activityType": "exercise",
                "description": "ウォーキング30分",
                "items": ["公園を歩く"]
            }
        ]
    }
)
```

### 外部AIクライアント（ChatGPT）向けの使用例

```javascript
// ChatGPT Actionとして設定された場合の使用例

// ユーザー: "今日の食事記録を教えて"
const todayMeals = await callHealthManagerMCP({
  tool: "getActivities",
  parameters: {
    date: "2025-12-14"
  }
});

// ユーザー: "ローカーボダイエットのポリシーを作成して"
const newPolicy = await callHealthManagerMCP({
  tool: "addPolicy", 
  parameters: {
    title: "ローカーボダイエット",
    description: "低糖質な食事を基本とする",
    policyType: "diet",
    rules: {
      carb: "low",
      maxCarbsPerDay: 50
    },
    isActive: true,
    priority: "high"
  }
});

// ユーザー: "100歳まで健康でいるという目標を設定して"
const longevityGoal = await callHealthManagerMCP({
  tool: "addGoal",
  parameters: {
    title: "100歳まで健康寿命を延ばす",
    description: "定期的な運動と健康的な食事により、100歳まで自立した生活を送る",
    goalType: "longevity", 
    targetValue: 100,
    unit: "years",
    targetDate: "2090-12-31",
    priority: "high",
    status: "active"
  }
});
```

## レート制限

各エンドポイントには以下のレート制限が適用されます：

- **読み取り操作** (get*): 100リクエスト/分
- **書き込み操作** (add*, update*, delete*): 50リクエスト/分

レート制限に達した場合、HTTP 429ステータスコードが返されます。

## セキュリティ考慮事項

1. **認証**: すべてのリクエストにJWTトークンが必要
2. **認可**: ユーザーは自分のデータのみアクセス可能
3. **データ検証**: すべての入力データは厳密に検証
4. **ログ記録**: すべてのAPI呼び出しがCloudWatch Logsに記録
5. **暗号化**: データは転送時・保存時ともに暗号化

---

この仕様書に従って、HealthManagerMCPの各APIを正しく使用できます。