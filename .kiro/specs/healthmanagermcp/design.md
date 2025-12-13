# 設計書

## 概要

HealthManagerMCPは、Healthmateエコシステムの中核となる健康情報記録MCPサーバーです。本システムは、AWS上でサーバーレスアーキテクチャを採用し、Amazon Bedrock AgentCore Gateway（MCP対応）、Cognito（OAuth 2.0認証）、DynamoDB（データ永続化）、Lambda（ビジネスロジック）を統合して構築されます。

本システムは、MCPサーバーとしてのみ機能し、ユーザーの健康ポリシーと日々の活動記録を管理するAPIを提供します。Bedrock AgentCore GatewayをMCPエンドポイントとして公開することで、HealthCoachAIやその他のAIクライアント（ChatGPT、Claude、Geminiなど）からMCP（Model Context Protocol）経由でアクセス可能になります。AIクライアントは、MCPツールを通じてユーザーの健康情報を取得したり、新しい記録を追加したりできます。本システムはデータの記録と取得のみに専念し、UI/AIエージェントは提供しません。

## Healthmateエコシステムにおける位置づけ

HealthManagerMCPは、Healthmateエコシステムにおいて以下の役割を担います：

- **データ管理層**: ユーザーの健康データの永続化と管理
- **API提供層**: MCPプロトコルを通じた標準化されたデータアクセスインターフェース
- **認証・認可層**: OAuth 2.0によるセキュアなデータアクセス制御

他のコンポーネントとの関係：
- **HealthCoachAI**: 主要なクライアントとして、健康アドバイス生成のためにデータを取得・更新
- **HealthmateUI**: 将来的にMCP経由でデータにアクセスする可能性（現在は直接統合なし）

## アーキテクチャ

### システムアーキテクチャ図

```mermaid
graph TB
    subgraph "Healthmateエコシステム"
        HealthCoachAI[HealthCoachAI<br/>健康アドバイスエージェント]
        HealthmateUI[HealthmateUI<br/>フロントエンドUI]
    end
    
    subgraph "外部AIクライアント"
        ChatGPT[ChatGPT]
        Claude[Claude]
        Gemini[Gemini]
        Other[その他のAIクライアント]
    end
    
    subgraph "認証"
        Cognito[Cognito User Pool<br/>OAuth 2.0 IdP]
    end
    
    subgraph "MCP Gateway"
        Gateway[AgentCore Gateway<br/>HTTPSエンドポイント<br/>MCP対応]
        Identity[AgentCore Identity<br/>JWT自動検証]
        
        subgraph "Gateway Targets"
            GT1[UserManagement<br/>Gateway Target]
            GT2[HealthGoalManagement<br/>Gateway Target]
            GT3[HealthPolicyManagement<br/>Gateway Target]
            GT4[ActivityManagement<br/>Gateway Target]
        end
    end
    
    subgraph "ビジネスロジック Lambda"
        UserLambda[User Lambda<br/>ユーザー情報管理]
        GoalLambda[HealthGoal Lambda<br/>健康目標CRUD]
        PolicyLambda[HealthPolicy Lambda<br/>健康ポリシーCRUD]
        ActivityLambda[Activity Lambda<br/>活動記録CRUD]
    end
    
    subgraph "データストア"
        UserTable[(DynamoDB<br/>ユーザーテーブル)]
        GoalTable[(DynamoDB<br/>健康目標テーブル)]
        PolicyTable[(DynamoDB<br/>健康ポリシーテーブル)]
        ActivityTable[(DynamoDB<br/>活動記録テーブル)]
    end
    
    subgraph "インフラ管理"
        CDK[AWS CDK<br/>IaC]
    end
    
    HealthCoachAI -->|1. OAuth 2.0認証| Cognito
    HealthmateUI -->|1. OAuth 2.0認証| Cognito
    ChatGPT -->|1. OAuth 2.0認証| Cognito
    Claude -->|1. OAuth 2.0認証| Cognito
    Gemini -->|1. OAuth 2.0認証| Cognito
    Other -->|1. OAuth 2.0認証| Cognito
    
    Cognito -->|2. JWT（sub含む）| HealthCoachAI
    Cognito -->|2. JWT（sub含む）| HealthmateUI
    Cognito -->|2. JWT（sub含む）| ChatGPT
    Cognito -->|2. JWT（sub含む）| Claude
    Cognito -->|2. JWT（sub含む）| Gemini
    Cognito -->|2. JWT（sub含む）| Other
    
    HealthCoachAI -->|3. MCP + JWT| Gateway
    HealthmateUI -->|3. MCP + JWT| Gateway
    ChatGPT -->|3. MCP + JWT| Gateway
    Claude -->|3. MCP + JWT| Gateway
    Gemini -->|3. MCP + JWT| Gateway
    Other -->|3. MCP + JWT| Gateway
    
    Gateway -->|4. JWT検証| Identity
    Identity -->|5. sub抽出| Identity
    
    Gateway -->|6. MCPツール呼び出し| GT1
    Gateway -->|6. MCPツール呼び出し| GT2
    Gateway -->|6. MCPツール呼び出し| GT3
    Gateway -->|6. MCPツール呼び出し| GT4
    
    GT1 -->|呼び出し| UserLambda
    GT2 -->|呼び出し| GoalLambda
    GT3 -->|呼び出し| PolicyLambda
    GT4 -->|呼び出し| ActivityLambda
    
    UserLambda -->|読み書き| UserTable
    GoalLambda -->|読み書き| GoalTable
    PolicyLambda -->|読み書き| PolicyTable
    ActivityLambda -->|読み書き| ActivityTable
    
    CDK -.->|プロビジョニング| Cognito
    CDK -.->|プロビジョニング| Gateway
    CDK -.->|プロビジョニング| Identity
    CDK -.->|プロビジョニング| UserLambda
    CDK -.->|プロビジョニング| GoalLambda
    CDK -.->|プロビジョニング| PolicyLambda
    CDK -.->|プロビジョニング| ActivityLambda
    CDK -.->|プロビジョニング| UserTable
    CDK -.->|プロビジョニング| GoalTable
    CDK -.->|プロビジョニング| PolicyTable
    CDK -.->|プロビジョニング| ActivityTable
```

### アーキテクチャの特徴

1. **サーバーレスアーキテクチャ**: すべてのコンポーネントがマネージドサービスで構成され、スケーラビリティと運用コストの最適化を実現
2. **OAuth 2.0認証**: Cognito User PoolをIdPとして使用し、複数のAIクライアントをOAuthクライアントとして登録可能。JWTのsubをuserIdとして利用
3. **AgentCore Gateway**: Bedrock AgentCoreのネイティブ機能を使用してHTTPSエンドポイントを公開し、Custom JWT AuthorizerでCognitoのJWT検証を実施
4. **MCP統合**: AgentCore GatewayがMCPプロトコルに対応し、外部AIクライアント（ChatGPT、Claude、Geminiなど）からのアクセスを可能にする
5. **Gateway Targets**: AgentCore GatewayからLambda関数を直接呼び出す構造（UserManagement、HealthPolicyManagement、ActivityManagement）
6. **疎結合設計**: 各Lambda関数が単一責任を持ち、DynamoDBとの間でデータをやり取りする
7. **セキュリティ**: OAuth 2.0 + JWT認証、Custom JWT AuthorizerでのJWT検証、DynamoDBの暗号化
8. **MCPサーバー専用**: UIやAIエージェントは提供せず、MCPエンドポイントとしてのみ機能
9. **IaC**: CDKによるインフラストラクチャのコード管理で再現性と保守性を確保

## コンポーネントとインターフェース

### 0. 認証フロー（Cognito User Pool + OAuth 2.0）

**役割**: ChatGPTからのアクセスを認証し、ユーザーIDを管理する

**OAuth 2.0フロー**:

1. **ユーザー登録**:
   - ユーザーがCognito User Poolにアカウントを作成
   - Cognitoが一意のsub（Subject Identifier）を生成
   - このsubがシステム全体のuserIdとして使用される

2. **ChatGPT Connector設定**:
   - ChatGPTをOAuth 2.0クライアントとしてCognito User Poolに登録
   - クライアントID、クライアントシークレットを取得
   - 認可エンドポイント、トークンエンドポイントを設定

3. **認証フロー**:
   ```
   ChatGPT → Cognito認可エンドポイント → ユーザーログイン
   → Cognito → 認可コード → ChatGPT
   → Cognitoトークンエンドポイント → アクセストークン（JWT）
   ```

4. **JWT構造**:
   ```json
   {
     "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
     "cognito:username": "user@example.com",
     "email": "user@example.com",
     "iss": "https://cognito-idp.ap-northeast-1.amazonaws.com/ap-northeast-1_XXXXX",
     "exp": 1234567890,
     "iat": 1234567890
   }
   ```

5. **userIdの抽出**:
   - MCP Gateway LambdaがJWTを検証
   - JWTのsubクレームを抽出
   - このsubをuserIdとしてBedrock Agentに渡す

**Cognito User Pool設定**:
- **ユーザープール名**: healthmate-users
- **OAuth 2.0スコープ**: openid, profile, email
- **許可されるOAuthフロー**: Authorization code grant
- **許可されるOAuthスコープ**: openid, profile, email
- **コールバックURL**: ChatGPT Connectorが指定するURL
- **トークン有効期限**: アクセストークン 1時間、リフレッシュトークン 30日

**セキュリティ**:
- JWT署名検証（RS256）
- トークン有効期限チェック
- issuer検証（Cognito User PoolのURL）
- audience検証（クライアントID）

### 1. AgentCore Gateway

**役割**: Lambda関数をMCPサーバーとして公開し、外部AI（ChatGPTなど）からのアクセスを可能にする

**構成**:
- **AgentCore Gateway**: HTTPSエンドポイントを自動的に公開、MCPプロトコル対応
- **Custom JWT Authorizer**: CognitoのDiscovery URLを使用してJWT検証を実施
- **Gateway Targets**: 各Lambda関数（UserManagement、HealthPolicyManagement、ActivityManagement）をMCPツールとして公開

**処理フロー**:

1. **リクエスト受信**:
   - ChatGPTからMCPリクエスト + JWTを受信
   - HTTPヘッダー: `Authorization: Bearer <JWT>`

2. **JWT検証（Custom JWT Authorizerが実行）**:
   - Cognito User PoolのDiscovery URLを使用
   - JWT署名検証（RS256）
   - トークン有効期限チェック
   - issuer検証（Cognito User PoolのURL）
   - audience検証（クライアントID）
   - JWTのsubクレームを抽出してuserIdとして使用

3. **MCPリクエスト処理（AgentCore Gatewayが実行）**:
   - MCPプロトコルに従ってリクエストをパース
   - ツール名とパラメータを抽出

4. **Lambda関数呼び出し（Gateway Targetが実行）**:
   - userIdをパラメータに追加
   - 対応するLambda関数を呼び出し

5. **MCPレスポンス返却**:
   - Lambda関数の応答をMCPプロトコル形式に変換
   - ChatGPTに返却

**AgentCore Gateway設定**:
```python
# CDKでの設定例
self.agentcore_gateway = CfnResource(
    self,
    "AgentCoreGateway",
    type="AWS::BedrockAgentCore::Gateway",
    properties={
        "Name": "healthmate-gateway",
        "Description": "HealthManagerMCP Gateway for Healthmate ecosystem integration",
        "ProtocolType": "MCP",
        "RoleArn": gateway_role.role_arn,
        "AuthorizerType": "CUSTOM_JWT",
        "AuthorizerConfiguration": {
            "CustomJWTAuthorizer": {
                "DiscoveryUrl": discovery_url,
                "AllowedClients": [
                    self.user_pool_client.user_pool_client_id
                ],
            }
        },
    },
)
```

**MCPプロトコル**:
- **ツールリスト取得**: クライアントAIが利用可能なツール（Action Groups）のリストを取得
- **ツール呼び出し**: クライアントAIが特定のツールを呼び出し、結果を取得
- **セッション管理**: JWTのsubをuserIdとして自動的に管理

**公開されるMCPツール**:
1. **UserManagement**: ユーザー情報の管理（AddUser, UpdateUser, GetUser）
2. **HealthPolicyManagement**: 健康ポリシーの管理（AddPolicy, UpdatePolicy, DeletePolicy, GetPolicy）
3. **ActivityManagement**: 活動記録の管理（AddActivities, UpdateActivity, UpdateActivities, DeleteActivity, GetActivities, GetActivitiesInRange）

**MCPリクエスト例**（JWTヘッダー付き）:
```http
POST /mcp HTTP/1.1
Host: <agentcore-gateway-endpoint>.amazonaws.com
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "HealthPolicyManagement.getPolicy",
    "arguments": {}
  },
  "id": 1
}
```

**注**: userIdはJWTのsubから自動的に抽出されるため、MCPリクエストのargumentsに含める必要はありません。

**MCPレスポンス例**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"policies\": [{\"policyId\": \"...\", \"policyType\": \"exercise\", ...}]}"
      }
    ]
  },
  "id": 1
}
```

**エラーレスポンス例**（JWT検証失敗）:
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "認証に失敗しました。有効なアクセストークンを提供してください。"
  },
  "id": 1
}
```

### 2. Gateway Targets

Gateway Targetsは、AgentCore GatewayからLambda関数を直接呼び出すためのMCPツールです。各Gateway TargetはMCPプロトコルに従ってツールを公開し、AIクライアントからの呼び出しを対応するLambda関数にルーティングします。

#### Gateway Target 1: UserManagement

**説明**: ユーザー情報の管理（プロフィール、設定など）

**関連Lambda**: UserLambda

**MCPツール**:

1. **addUser**
   - 説明: 新しいユーザー情報を作成する
   - パラメータ:
     - userId (string): ユーザーID（Cognito User ID）
     - username (string): ユーザー名
     - email (string): メールアドレス

2. **updateUser**
   - 説明: ユーザー情報を更新する
   - パラメータ:
     - userId (string): ユーザーID
     - username (string, optional): ユーザー名
     - lastLoginAt (string, optional): 最終ログイン日時

3. **getUser**
   - 説明: ユーザー情報を取得する
   - パラメータ:
     - userId (string): ユーザーID

#### Gateway Target 2: HealthGoalManagement

**説明**: ユーザーの健康目標（長期的な理想状態）を管理する

**関連Lambda**: HealthGoalLambda

**MCPツール**:

1. **addGoal**
   - 説明: 新しい健康目標を追加する
   - パラメータ:
     - userId (string): ユーザーID
     - goalType (string): 目標タイプ（longevity|fitness|weight|mental_health|other）
     - title (string): 目標のタイトル
     - description (string): 目標の詳細説明
     - targetValue (string, optional): 目標値（例: "60kg", "体脂肪率15%"）
     - targetDate (string, optional): 目標達成日（YYYY-MM-DD）
     - priority (number, optional): 優先度（1-5）

2. **updateGoal**
   - 説明: 既存の健康目標を更新する
   - パラメータ:
     - userId (string): ユーザーID
     - goalId (string): 目標ID
     - title (string, optional): 目標のタイトル
     - description (string, optional): 目標の詳細説明
     - targetValue (string, optional): 目標値
     - targetDate (string, optional): 目標達成日
     - priority (number, optional): 優先度
     - status (string, optional): ステータス（active|achieved|paused|cancelled）

3. **deleteGoal**
   - 説明: 指定した健康目標を削除する
   - パラメータ:
     - userId (string): ユーザーID
     - goalId (string): 目標ID

4. **getGoals**
   - 説明: ユーザーのすべての健康目標を取得する
   - パラメータ:
     - userId (string): ユーザーID

#### Gateway Target 3: HealthPolicyManagement

**説明**: ユーザーの健康ポリシー（具体的な行動ルール）を管理する

**関連Lambda**: HealthPolicyLambda

**MCPツール**:

1. **addPolicy**
   - 説明: 新しい健康ポリシーを追加する
   - パラメータ:
     - userId (string): ユーザーID
     - policyType (string): ポリシータイプ（diet|exercise|sleep|fasting|restriction|other）
     - title (string): ポリシーのタイトル
     - description (string): ポリシーの詳細説明
     - rules (object): 具体的なルール（例: {"fastingHours": 16, "eatingWindow": "12:00-20:00"}）
     - startDate (string, optional): 開始日（YYYY-MM-DD）
     - endDate (string, optional): 終了日（YYYY-MM-DD）

2. **updatePolicy**
   - 説明: 既存の健康ポリシーを更新する
   - パラメータ:
     - userId (string): ユーザーID
     - policyId (string): ポリシーID
     - title (string, optional): ポリシーのタイトル
     - description (string, optional): ポリシーの詳細説明
     - rules (object, optional): 具体的なルール
     - isActive (boolean, optional): アクティブ状態
     - startDate (string, optional): 開始日
     - endDate (string, optional): 終了日

3. **deletePolicy**
   - 説明: 指定した健康ポリシーを削除する
   - パラメータ:
     - userId (string): ユーザーID
     - policyId (string): ポリシーID

4. **getPolicies**
   - 説明: ユーザーのすべての健康ポリシーを取得する
   - パラメータ:
     - userId (string): ユーザーID

#### Gateway Target 4: ActivityManagement

**説明**: ユーザーの日々の健康活動を記録・取得する

**関連Lambda**: ActivityLambda

**MCPツール**:

1. **addActivities**
   - 説明: 指定した日に新しい活動を追加する（既存の活動は保持される）
   - パラメータ:
     - userId (string): ユーザーID
     - date (string): 日付（YYYY-MM-DD）
     - activities (array): 追加する活動のリスト
       - time (string): 時刻（HH:MM）
       - activityType (string): 活動タイプ（wakeUp|sleep|exercise|meal|snack|weight|bodyFat|mood|medication|other）
       - description (string): 活動の説明
       - items (array of strings): 活動の詳細項目

2. **updateActivity**
   - 説明: 指定した日の特定の時刻の活動だけを部分的に更新する（他の時刻の活動は変更されない）
   - パラメータ:
     - userId (string): ユーザーID
     - date (string): 日付（YYYY-MM-DD）
     - time (string): 更新対象の時刻（HH:MM）
     - activityType (string, optional): 活動タイプ
     - description (string, optional): 活動の説明
     - items (array of strings, optional): 活動の詳細項目

3. **updateActivities**
   - 説明: 指定した日の全ての活動を完全に置き換える（既存の活動は全て削除され、新しいリストで上書きされる）
   - パラメータ:
     - userId (string): ユーザーID
     - date (string): 日付（YYYY-MM-DD）
     - activities (array): 新しい活動のリスト
       - time (string): 時刻（HH:MM）
       - activityType (string): 活動タイプ
       - description (string): 活動の説明
       - items (array of strings): 活動の詳細項目

4. **deleteActivity**
   - 説明: 指定した日の指定した行動を削除する
   - パラメータ:
     - userId (string): ユーザーID
     - date (string): 日付（YYYY-MM-DD）
     - time (string): 時刻（HH:MM）

5. **getActivities**
   - 説明: 指定した日のユーザーの行動を取得する
   - パラメータ:
     - userId (string): ユーザーID
     - date (string): 日付（YYYY-MM-DD）

6. **getActivitiesInRange**
   - 説明: 指定した期間のユーザーの行動履歴を取得する
   - パラメータ:
     - userId (string): ユーザーID
     - startDate (string): 開始日（YYYY-MM-DD）
     - endDate (string): 終了日（YYYY-MM-DD）
   - 注: 最大365日間（1年間）の範囲を指定可能

### 3. Lambda関数

#### UserLambda

**責務**: ユーザー情報の管理（Gateway TargetのUserManagementから呼び出される）

**処理フロー**:
- addUser: 新しいユーザー情報をDynamoDBに保存
- updateUser: 既存のユーザー情報をDynamoDBで更新
- getUser: ユーザー情報をDynamoDBから取得

**インターフェース**:
```python
from typing import TypedDict, Optional, Any

# Lambda入力イベント（MCP Gateway Targetから）
class UserLambdaEvent(TypedDict):
    function: str     # "addUser" | "updateUser" | "getUser"
    parameters: dict[str, Any]

# Lambda出力レスポンス（MCP Gateway Targetへ）
class UserLambdaResponse(TypedDict):
    response: dict[str, Any]

# データモデル
class User(TypedDict):
    userId: str
    username: str
    email: str
    createdAt: str
    lastLoginAt: str
```

#### HealthGoalLambda

**責務**: 健康目標のCRUD操作（Gateway TargetのHealthGoalManagementから呼び出される）

**処理フロー**:
- addGoal: 新しい目標をDynamoDBに保存
- updateGoal: 既存の目標をDynamoDBで更新
- deleteGoal: 指定した目標をDynamoDBから削除
- getGoals: ユーザーIDでDynamoDBをクエリし、すべての目標を取得

**インターフェース**:
```python
from typing import TypedDict, Optional, Literal, Any

# Lambda入力イベント（MCP Gateway Targetから）
class HealthGoalLambdaEvent(TypedDict):
    function: str     # "addGoal" | "updateGoal" | "deleteGoal" | "getGoals"
    parameters: dict[str, Any]

# Lambda出力レスポンス（MCP Gateway Targetへ）
class HealthGoalLambdaResponse(TypedDict):
    response: dict[str, Any]

# データモデル
GoalType = Literal['longevity', 'fitness', 'weight', 'mental_health', 'other']
GoalStatus = Literal['active', 'achieved', 'paused', 'cancelled']

class HealthGoal(TypedDict):
    goalId: str
    userId: str
    goalType: GoalType
    title: str
    description: str
    targetValue: Optional[str]
    targetDate: Optional[str]
    priority: int
    status: GoalStatus
    createdAt: str
    updatedAt: str
```

#### HealthPolicyLambda

**責務**: 健康ポリシーのCRUD操作（Gateway TargetのHealthPolicyManagementから呼び出される）

**処理フロー**:
- addPolicy: 新しいポリシーをDynamoDBに保存
- updatePolicy: 既存のポリシーをDynamoDBで更新
- deletePolicy: 指定したポリシーをDynamoDBから削除
- getPolicies: ユーザーIDでDynamoDBをクエリし、すべてのポリシーを取得

**インターフェース**:
```python
from typing import TypedDict, Optional, Literal, Any

# Lambda入力イベント（MCP Gateway Targetから）
class HealthPolicyLambdaEvent(TypedDict):
    function: str     # "addPolicy" | "updatePolicy" | "deletePolicy" | "getPolicies"
    parameters: dict[str, Any]

# Lambda出力レスポンス（MCP Gateway Targetへ）
class HealthPolicyLambdaResponse(TypedDict):
    response: dict[str, Any]

# データモデル
PolicyType = Literal['diet', 'exercise', 'sleep', 'fasting', 'restriction', 'other']

class HealthPolicy(TypedDict):
    policyId: str
    userId: str
    policyType: PolicyType
    title: str
    description: str
    rules: dict[str, Any]
    isActive: bool
    startDate: Optional[str]
    endDate: Optional[str]
    createdAt: str
    updatedAt: str
```

#### ActivityLambda

**責務**: 活動記録のCRUD操作（Gateway TargetのActivityManagementから呼び出される）

**処理フロー**:
- addActivities: 指定された日付のDailyActivityレコードに新しい活動エントリーを追加（日付のレコードが存在しない場合は新規作成）
- updateActivity: 特定の日付・時刻の活動エントリーを更新
- updateActivities: 特定の日付の全活動を置き換え
- deleteActivity: 特定の日付・時刻の活動エントリーを削除
- getActivities: 特定の日付の全活動を取得
- getActivitiesInRange: 指定された期間（開始日〜終了日）の全活動を取得（DynamoDBのクエリで日付範囲を指定）

**インターフェース**:
```python
from typing import TypedDict, Optional, Any

# Lambda入力イベント（MCP Gateway Targetから）
class ActivityLambdaEvent(TypedDict):
    function: str     # "addActivities" | "updateActivity" | "updateActivities" | "deleteActivity" | "getActivities" | "getActivitiesInRange"
    parameters: dict[str, Any]

# Lambda出力レスポンス（MCP Gateway Targetへ）
class ActivityLambdaResponse(TypedDict):
    response: dict[str, Any]
```

### 4. DynamoDB テーブル設計

#### ユーザーテーブル

```
テーブル名: healthmate-users
パーティションキー: userId (String)
属性:
  - username (String)
  - email (String)
  - createdAt (String)
  - lastLoginAt (String)
```

#### 健康目標テーブル

```
テーブル名: healthmate-goals
パーティションキー: userId (String)
ソートキー: goalId (String)
属性:
  - goalType (String) // longevity, fitness, weight, mental_health, other
  - title (String) // "100歳まで健康寿命"
  - description (String) // 詳細説明
  - targetValue (String, optional) // "60kg", "体脂肪率15%"
  - targetDate (String, optional) // 目標達成日 YYYY-MM-DD
  - priority (Number) // 1-5の優先度
  - status (String) // active, achieved, paused, cancelled
  - createdAt (String) // ISO 8601
  - updatedAt (String) // ISO 8601
GSI: goalType-index (goalTypeでクエリ可能)
GSI: status-index (statusでクエリ可能)
```

#### 健康ポリシーテーブル

```
テーブル名: healthmate-policies
パーティションキー: userId (String)
ソートキー: policyId (String)
属性:
  - policyType (String) // diet, exercise, sleep, fasting, restriction, other
  - title (String) // "16時間ファスティング"
  - description (String) // 詳細説明
  - rules (Map) // 具体的なルール {"fastingHours": 16, "eatingWindow": "12:00-20:00"}
  - isActive (Boolean) // アクティブかどうか
  - startDate (String, optional) // 開始日 YYYY-MM-DD
  - endDate (String, optional) // 終了日 YYYY-MM-DD（期間限定の場合）
  - createdAt (String) // ISO 8601
  - updatedAt (String) // ISO 8601
GSI: policyType-index (policyTypeでクエリ可能)
GSI: isActive-index (isActiveでクエリ可能)
```

#### 活動記録テーブル

```
テーブル名: healthmate-activities
パーティションキー: userId (String)
ソートキー: date (String) // YYYY-MM-DD
属性:
  - activities (List<Map>) // その日の活動リスト
    - time (String) // HH:MM形式
    - activityType (String) // wakeUp, exercise, meal, etc.
    - description (String) // 活動の説明
    - items (List<String>) // 活動の詳細項目（例: ["ジョギング1km", "ウォーキング1km", "お茶1杯"]）
  - createdAt (String) // ISO 8601
  - updatedAt (String) // ISO 8601
GSI: date-index (日付範囲クエリ用)
```

**データ構造の例**:
```json
{
  "userId": "user123",
  "date": "2024-12-07",
  "activities": [
    {
      "time": "08:00",
      "activityType": "wakeUp",
      "description": "起床",
      "items": []
    },
    {
      "time": "08:30",
      "activityType": "exercise",
      "description": "運動",
      "items": ["ジョギング1km", "ウォーキング1km", "お茶1杯"]
    },
    {
      "time": "12:00",
      "activityType": "meal",
      "description": "昼食",
      "items": ["プロテイン飲料", "コンビニサラダ", "コーヒー1杯"]
    }
  ],
  "createdAt": "2024-12-07T08:00:00Z",
  "updatedAt": "2024-12-07T12:05:00Z"
}
```

**注**: 会話履歴はBedrock Agentsのネイティブ機能で管理されるため、DynamoDBテーブルは不要です。

## データモデル

### HealthGoal（健康目標）

```python
from typing import TypedDict, Literal, Optional
from datetime import datetime

GoalType = Literal['longevity', 'fitness', 'weight', 'mental_health', 'other']
GoalStatus = Literal['active', 'achieved', 'paused', 'cancelled']

class HealthGoal(TypedDict):
    goalId: str            # UUID
    userId: str            # Cognito User ID
    goalType: GoalType     # 目標の種類
    title: str             # 目標のタイトル
    description: str       # 目標の詳細説明
    targetValue: Optional[str]  # 目標値（例: "60kg", "体脂肪率15%"）
    targetDate: Optional[str]   # 目標達成日（YYYY-MM-DD）
    priority: int          # 優先度（1-5）
    status: GoalStatus     # ステータス
    createdAt: str         # ISO 8601
    updatedAt: str         # ISO 8601

# 目標タイプの説明:
# - 'longevity': 長寿・健康寿命（例: 100歳まで健康寿命）
# - 'fitness': フィットネス・体型（例: アスリート体型）
# - 'weight': 体重管理（例: 理想体重60kg）
# - 'mental_health': メンタルヘルス（例: ストレス軽減）
# - 'other': その他
```

### HealthPolicy（健康ポリシー）

```python
from typing import TypedDict, Literal, Optional
from datetime import datetime

PolicyType = Literal['diet', 'exercise', 'sleep', 'fasting', 'restriction', 'other']

class HealthPolicy(TypedDict):
    policyId: str          # UUID
    userId: str            # Cognito User ID
    policyType: PolicyType # ポリシーの種類
    title: str             # ポリシーのタイトル
    description: str       # ポリシーの詳細説明
    rules: dict            # 具体的なルール
    isActive: bool         # アクティブかどうか
    startDate: Optional[str]    # 開始日（YYYY-MM-DD）
    endDate: Optional[str]      # 終了日（YYYY-MM-DD）
    createdAt: str         # ISO 8601
    updatedAt: str         # ISO 8601

# ポリシータイプの説明:
# - 'diet': 食事制限（例: ローカーボダイエット）
# - 'exercise': 運動習慣（例: 週3回のジム）
# - 'sleep': 睡眠パターン（例: 22時就寝6時起床）
# - 'fasting': ファスティング（例: 16時間ファスティング）
# - 'restriction': 制限事項（例: お酒は禁止）
# - 'other': その他
```

### DailyActivity（1日の活動記録）

```python
from typing import TypedDict, Literal

ActivityType = Literal[
    'wakeUp',      # 起床
    'sleep',       # 就寝
    'exercise',    # 運動
    'meal',        # 食事
    'snack',       # 間食
    'weight',      # 体重測定
    'bodyFat',     # 体脂肪率測定
    'mood',        # 気分記録
    'medication',  # 服薬
    'other'        # その他
]

class ActivityEntry(TypedDict):
    time: str              # HH:MM形式（例: "08:00", "12:30"）
    activityType: ActivityType
    description: str       # 活動の説明（例: "起床", "運動", "昼食"）
    items: list[str]       # 活動の詳細項目リスト

class DailyActivity(TypedDict):
    userId: str            # Cognito User ID
    date: str              # YYYY-MM-DD（ソートキー）
    activities: list[ActivityEntry]  # その日の活動リスト
    createdAt: str         # ISO 8601
    updatedAt: str         # ISO 8601
```

**使用例**:
```python
daily_activity: DailyActivity = {
    "userId": "user123",
    "date": "2024-12-07",
    "activities": [
        {
            "time": "08:00",
            "activityType": "wakeUp",
            "description": "起床",
            "items": []
        },
        {
            "time": "08:30",
            "activityType": "exercise",
            "description": "運動",
            "items": ["ジョギング1km", "ウォーキング1km", "お茶1杯"]
        },
        {
            "time": "12:00",
            "activityType": "meal",
            "description": "昼食",
            "items": ["プロテイン飲料", "コンビニサラダ", "コーヒー1杯"]
        }
    ],
    "createdAt": "2024-12-07T08:00:00Z",
    "updatedAt": "2024-12-07T12:05:00Z"
}
```

## 正確性プロパティ

*プロパティとは、システムのすべての有効な実行において真であるべき特性や動作のことです。プロパティは、人間が読める仕様と機械で検証可能な正確性保証の橋渡しとなります。*


### プロパティ1: MCPツールリストの完全性

*任意の*MCPツールリスト要求に対して、システムはすべての利用可能なツール（UserManagement、HealthPolicyManagement、ActivityManagement）を返すべきである
**検証対象: 要件1.2**

### プロパティ2: MCPツール呼び出しの正確性

*任意の*有効なMCPツール呼び出しに対して、システムは対応するAction Groupを実行し、結果をMCPプロトコルに準拠した形式で返すべきである
**検証対象: 要件1.3**

### プロパティ3: MCPセッションコンテキストの維持

*任意の*MCPセッションに対して、複数のツール呼び出しを行っても、ユーザーIDが一貫して維持されるべきである
**検証対象: 要件1.4**

### プロパティ4: MCPエラーレスポンスの準拠性

*任意の*エラー発生時に対して、システムはMCPプロトコルに準拠したエラーレスポンスを返すべきである
**検証対象: 要件1.5**

### プロパティ5: 健康ポリシーのラウンドトリップ

*任意の*健康ポリシーに対して、保存してから取得すると、同じ内容が返されるべきである
**検証対象: 要件2.2**

### プロパティ6: すべてのポリシーの取得

*任意の*ユーザーに対して、保存したすべての健康ポリシーが取得時に返されるべきである
**検証対象: 要件2.3**

### プロパティ7: ポリシー更新の反映

*任意の*健康ポリシーに対して、更新後に取得すると、変更が反映されているべきである
**検証対象: 要件2.4**

### プロパティ8: 活動記録の保存と関連付け

*任意の*活動データに対して、保存されたレコードは正しい日付キーと認証されたユーザーIDを持つべきである
**検証対象: 要件3.2, 3.3**

### プロパティ9: 複数活動の個別記録

*任意の*N個の活動報告に対して、システムは1つのDailyActivityレコード内にN個の個別ActivityEntryを保存すべきである
**検証対象: 要件3.4**

### プロパティ10: 既存レコードの更新

*任意の*既存の活動記録に対して、同じ日付の新しい活動を報告すると、既存レコードが上書きされずに追加されるべきである
**検証対象: 要件3.5**

### プロパティ11: MCPツール呼び出しの完全性

*任意の*MCPツール呼び出しに対して、クライアントAIからの要求はBedrock Agentに到達し、結果がクライアントAIに返されるべきである
**検証対象: 要件5.2, 5.3**

### プロパティ12: ユーザー固有データの取得

*任意の*ユーザーに対して、データ取得時に返されるすべてのレコードは、そのユーザーのIDを持つべきである
**検証対象: 要件7.2**

### プロパティ13: 日付範囲クエリの正確性

*任意の*日付範囲に対して、クエリ結果に含まれるすべての活動記録は、指定された範囲内の日付を持つべきである
**検証対象: 要件7.3**



## エラーハンドリング

### 1. 認証エラー

**シナリオ**:
- JWTトークンの欠落
- JWT署名検証失敗
- トークン有効期限切れ
- 不正なissuerまたはaudience

**処理**:
- AgentCore Identityが自動的にエラーを検出
- MCPエラーレスポンスを返す（jsonrpc 2.0形式）
- エラーコード: -32001（Authentication failed）
- エラーメッセージ: "認証に失敗しました。有効なアクセストークンを提供してください。"
- HTTPステータスコード: 401 Unauthorized
- CloudWatch Logsに認証失敗を記録

### 2. MCPプロトコルエラー

**シナリオ**:
- 無効なツール名
- 不正なパラメータ
- セッション属性の欠落

**処理**:
- MCPエラーレスポンスを返す（jsonrpc 2.0形式）
- エラーコード: -32602（Invalid params）または -32601（Method not found）
- エラーメッセージ: 具体的なエラー内容

### 3. データベースエラー

**シナリオ**:
- DynamoDB接続失敗
- スロットリング
- データ整合性エラー

**処理**:
- 指数バックオフで最大3回再試行（初回: 100ms、2回目: 200ms、3回目: 400ms）
- 再試行後も失敗した場合、MCPエラーレスポンスを返す
- エラーコード: -32603（Internal error）
- エラーメッセージ: "データの保存/取得に失敗しました。しばらくしてから再度お試しください。"
- CloudWatch Logsにエラー詳細を記録

### 4. Bedrockエラー

**シナリオ**:
- API呼び出し失敗
- レート制限
- モデル応答タイムアウト

**処理**:
- タイムアウト: 30秒
- レート制限時は指数バックオフで再試行
- 失敗時、MCPエラーレスポンスを返す
- エラーコード: -32603（Internal error）
- エラーメッセージ: "パーソナルトレーナーAIエージェントが一時的に利用できません。しばらくしてから再度お試しください。"

### 5. バリデーションエラー

**シナリオ**:
- 不正なリクエスト形式
- 必須フィールドの欠落
- データ型の不一致

**処理**:
- MCPエラーレスポンスを返す
- エラーコード: -32602（Invalid params）
- エラーメッセージ: 具体的なバリデーションエラー内容（例: "日付形式が不正です。YYYY-MM-DD形式で入力してください。"）

### 6. リソース不足エラー

**シナリオ**:
- Lambda同時実行数制限
- DynamoDBキャパシティ不足

**処理**:
- MCPエラーレスポンスを返す
- エラーコード: -32603（Internal error）
- エラーメッセージ: "現在、リクエストが集中しています。しばらくしてから再度お試しください。"
- CloudWatch Alarmsでアラート

## テスト戦略

### 1. ユニットテスト

**対象**: 個別のLambda関数、ユーティリティ関数、データ変換ロジック

**フレームワーク**: Jest（TypeScript/Node.js）

**テストケース例**:
- Lambda関数の入力バリデーション
- DynamoDBクエリビルダーの正確性
- エラーハンドリングロジック
- システムプロンプト生成ロジック

**カバレッジ目標**: 80%以上

### 2. プロパティベーステスト

**対象**: 正確性プロパティの検証

**フレームワーク**: fast-check（TypeScript/JavaScript用プロパティベーステストライブラリ）

**設定**:
- 各プロパティテストは最低100回の反復実行
- ランダムデータ生成器を使用して多様な入力をテスト

**テストケース**:
各正確性プロパティ（プロパティ1〜16）に対して、対応するプロパティベーステストを実装します。

例: プロパティ5（健康ポリシーのラウンドトリップ）
```python
from hypothesis import given, strategies as st
import pytest

# Feature: healthspan100, Property 5: 健康ポリシーのラウンドトリップ
@given(
    policy_type=st.sampled_from(['diet', 'exercise', 'sleep', 'fasting', 'other']),
    description=st.text(),
    parameters=st.dictionaries(st.text(), st.text())
)
@pytest.mark.property
def test_health_policy_round_trip(policy_type, description, parameters):
    """任意の健康ポリシーに対して、保存してから取得すると同じ内容が返される"""
    user_id = 'test-user-id'
    policy = {
        'policyType': policy_type,
        'description': description,
        'parameters': parameters
    }
    
    # MCPツール経由でポリシーを保存
    saved_policy = call_mcp_tool('HealthPolicyManagement.addPolicy', {
        'userId': user_id,
        **policy
    })
    
    # MCPツール経由でポリシーを取得
    retrieved_policies = call_mcp_tool('HealthPolicyManagement.getPolicy', {
        'userId': user_id
    })
    
    # 保存したポリシーが取得結果に含まれることを確認
    assert any(
        p['policyType'] == policy_type and 
        p['details']['description'] == description
        for p in retrieved_policies['policies']
    )
```

### 3. 統合テスト

**対象**: MCP Gateway → Bedrock Agent → Lambda → DynamoDBの統合フロー

**フレームワーク**: pytest + AWS SDK Mocks

**テストケース例**:
- MCPツールリスト取得フロー
- MCPツール呼び出しから結果受信までのフロー
- 健康ポリシーのCRUD操作（MCP経由）
- 活動記録の保存と取得（MCP経由）

### 4. E2Eテスト

**対象**: クライアントAI（ChatGPT）からMCP経由でのアクセス

**フレームワーク**: pytest + MCP Client Library

**テストケース例**:
- ChatGPTからMCP接続してツールリストを取得
- ChatGPTからMCP経由で健康ポリシーを取得
- ChatGPTからMCP経由で活動記録を追加
- ChatGPTからMCP経由で複数のツールを連続して呼び出し



## デプロイメント戦略

### 1. 環境構成

**環境**:
- Development: 開発用環境
- Staging: 本番前検証環境
- Production: 本番環境

**環境ごとの設定**:
- 異なるAWSアカウントまたはリージョン
- 環境変数による設定管理（Bedrock モデルID、DynamoDBテーブル名など）

### 2. デプロイ方法

**ツール**: AWS CDK（Python）

**デプロイコマンド**:
```bash
# 初回のみ
cdk bootstrap

# デプロイ
cdk deploy
```

## モニタリングとロギング

### 1. CloudWatch Logs

**ログ出力**:
- すべてのLambda関数の実行ログ
- エラースタックトレース
- リクエスト/レスポンスのペイロード（機密情報はマスク）

**ログレベル**:
- ERROR: エラー発生時
- WARN: 警告（再試行、予期しない状態）
- INFO: 通常の処理フロー
- DEBUG: 詳細なデバッグ情報（Development環境のみ）

### 2. CloudWatch Metrics

**カスタムメトリクス**:
- API呼び出し回数（エンドポイント別）
- Bedrock呼び出し回数とレイテンシ
- DynamoDB読み書き回数
- エラー率（エラータイプ別）

### 3. CloudWatch Alarms

**アラート設定**:
- Lambda関数のエラー率 > 5%
- API Gateway 5xxエラー率 > 1%
- DynamoDB スロットリング発生
- Lambda同時実行数が制限に近づく（> 80%）

**通知先**: SNS → Email/Slack



## セキュリティ考慮事項

### 1. 認証・認可

- **OAuth 2.0認証**: Cognito User PoolをIdPとして使用
- **JWT検証**: AgentCore IdentityでJWT署名、有効期限、issuer、audienceを自動検証
- **ユーザーID管理**: JWTのsubクレームをuserIdとして使用（Cognitoが管理）
- **セッション管理**: AgentCore GatewayがuserIdをBedrock AgentのsessionAttributesに自動設定
- **Lambda関数内での検証**: セッション属性のuserIdの確認

### 2. データ暗号化

- DynamoDB: 保存時の暗号化（AWS KMS）
- MCP通信: HTTPS/TLS 1.2以上
- JWT: RS256署名アルゴリズム（Cognito公開鍵で検証）

### 3. アクセス制御

- IAMロールによる最小権限の原則
- Lambda関数ごとに個別のIAMロール
- DynamoDBの行レベルアクセス制御（Fine-Grained Access Control）

### 4. 入力バリデーション

- すべてのMCPツール入力のバリデーション
- SQLインジェクション対策（DynamoDBはNoSQLだが、クエリパラメータのサニタイズ）
- パラメータのサニタイズ

### 5. レート制限

- AgentCore Gatewayのスロットリング設定
- ユーザーごとのレート制限（JWTのsubベース）
- Cognitoのレート制限（認証リクエスト）

### 6. 監査ログ

- すべてのMCPツール呼び出しをCloudWatch Logsに記録
- ユーザーID（JWTのsub）、タイムスタンプ、ツール名、パラメータを含む
- 認証成功・失敗のログ記録

## スケーラビリティ考慮事項

### 1. Lambda

- 同時実行数の制限設定（予期しないコスト増加を防ぐ）
- プロビジョニング済み同時実行数（レイテンシ削減）

### 2. DynamoDB

- オンデマンドキャパシティモード（トラフィック変動に自動対応）
- GSI（Global Secondary Index）の適切な設計
- DynamoDB Streamsによる非同期処理（必要に応じて）

### 3. API Gateway

- キャッシング設定（頻繁にアクセスされるエンドポイント）
- スロットリング設定

### 4. Bedrock

- レート制限の考慮
- 非同期処理の検討（長時間かかる推論）

## コスト最適化

### 1. Lambda

- メモリサイズの最適化（パフォーマンステストで適切なサイズを決定）
- 実行時間の最短化（不要な処理の削減）

### 2. DynamoDB

- オンデマンドモードの使用（予測不可能なトラフィック）
- TTL設定による古いデータの自動削除（必要に応じて）

### 3. Bedrock

- プロンプトの最適化（トークン数削減）
- キャッシング戦略（同じ質問への応答）

### 4. CloudWatch

- ログ保持期間の設定（例: 30日）
- 不要なログの削減

## 今後の拡張性

### 1. 他のクライアントAIとの連携

- Claude、Gemini、LLaMAなど他のAIモデルとの連携
- MCPプロトコルの拡張

### 2. データ分析機能の追加

- 活動データの統計分析
- トレンド分析とインサイト提供
- MCPツールとして公開

### 3. 通知機能の追加

- リマインダー機能（運動、食事記録）
- 目標達成通知
- MCPツールとして公開

### 4. ウェアラブルデバイス連携

- Fitbit、Apple Watch等のデータ統合
- 自動活動記録
- MCPツールとして公開

### 5. ナレッジベースの追加

- 医学文献やトレーニングガイドラインの統合
- Bedrock Knowledge Baseの活用

## 技術スタック

### バックエンド

- **言語**: Python 3.12
- **フレームワーク**: AWS Lambda
- **IaC**: AWS CDK v2（Python）
- **テスト**: pytest, hypothesis（プロパティベーステスト）
- **依存関係管理**: pip

### インフラストラクチャ

- **コンピューティング**: AWS Lambda（Python 3.12、30秒タイムアウト、256MB メモリ）
- **認証**: Amazon Cognito User Pool（OAuth 2.0 IdP、Authorization Code Grant with Client Secret）
- **MCP Gateway**: Bedrock AgentCore Gateway（HTTPSエンドポイント、MCP対応、Custom JWT Authorizer）
- **データベース**: Amazon DynamoDB（Pay-per-request、Point-in-time recovery有効）
- **モニタリング**: CloudWatch Logs（1週間保持）
- **IaC**: AWS CDK v2（Python）

### クライアント

- **主要クライアント**: HealthCoachAI（健康アドバイスエージェント）
- **将来的なクライアント**: HealthmateUI（フロントエンドUI）
- **外部AIクライアント**: ChatGPT（OpenAI）、Claude（Anthropic）、Gemini（Google）など
- **プロトコル**: MCP（Model Context Protocol）
- **接続方法**: 各AIクライアントのMCP Connector機能
