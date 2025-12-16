# Healthmate サービスアーキテクチャ

## Terminology Standards

### 階層構造
- **プロダクト**: Healthmate プロダクト（完全なソリューション）
- **ワークスペース**: Healthmate ワークスペース（開発環境）
- **サービス**: 個別サービス（HealthManagerMCP、HealthCoachAI、HealthmateUI）

### 命名規則
- **サービス名**: 必ず「サービス」を付けて呼ぶ
  - HealthManagerMCP サービス
  - HealthCoachAI サービス  
  - HealthmateUI サービス
- **AWS リソース**: `healthmate-` プレフィックス統一
- **コード**: snake_case（関数）、PascalCase（クラス）

## Service Relationships

### データフロー
```
HealthmateUI サービス
    ↓ (JWT Token + User Input)
HealthCoachAI サービス  
    ↓ (MCP Protocol)
HealthManagerMCP サービス
    ↓ (DynamoDB Operations)
Health Data Storage
```

### 認証フロー
```
User → Cognito OAuth 2.0 → JWT Token
JWT Token → All Services (User Identification)
```

### 通信プロトコル
- **UI ↔ AI**: WebSocket/Server-Sent Events（リアルタイムチャット）
- **AI ↔ Backend**: Model Context Protocol (MCP)
- **UI ↔ Backend**: RESTful API（直接データ操作時）

## Service Dependencies

### Deployment Dependencies
```
1. HealthManagerMCP サービス（基盤）
   ↓
2. HealthCoachAI サービス（MCP クライアント）
   ↓  
3. HealthmateUI サービス（フロントエンド）
```

### Runtime Dependencies
- **HealthCoachAI** → **HealthManagerMCP**: MCP API呼び出し
- **HealthmateUI** → **HealthManagerMCP**: 直接API呼び出し
- **HealthmateUI** → **HealthCoachAI**: チャット機能
- **All Services** → **Cognito**: 認証・認可

## Integration Patterns

### MCP Integration
```python
# HealthCoachAI → HealthManagerMCP
async def call_health_api(tool_name: str, parameters: dict):
    """MCP プロトコルでの健康データアクセス"""
    response = await mcp_client.call_tool(
        server="health-management",
        tool=tool_name, 
        arguments=parameters
    )
    return response
```

### JWT Token Flow
```javascript
// HealthmateUI → Services
const apiCall = async (endpoint, data) => {
    const token = await getValidJWTToken();
    return fetch(endpoint, {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    });
};
```

## Shared Infrastructure

### AWS Resources
- **Cognito User Pool**: 全サービス共通認証
- **DynamoDB Tables**: HealthManagerMCP サービスが管理
- **CloudWatch Logs**: 全サービスのログ集約
- **IAM Roles**: サービス別の最小権限

### Configuration Management
- **CloudFormation Outputs**: サービス間設定共有
- **Environment Variables**: サービス固有設定
- **Parameter Store**: 機密情報管理

## Data Models

### User Context
```json
{
  "userId": "cognito-sub-claim",
  "timezone": "Asia/Tokyo", 
  "language": "ja",
  "preferences": {...}
}
```

### Health Data Schema
```json
{
  "goals": [...],      // 健康目標
  "policies": [...],   // 健康ポリシー  
  "activities": [...], // 日々の活動
  "user": {...}        // ユーザー情報
}
```

## Error Handling Patterns

### Unified Error Response
```json
{
  "success": false,
  "error": "ERROR_TYPE",
  "message": "詳細なエラーメッセージ", 
  "details": {...}
}
```

### Service-Level Error Handling
- **HealthManagerMCP**: DynamoDB例外 → MCP エラーレスポンス
- **HealthCoachAI**: MCP呼び出し失敗 → 代替アドバイス提供
- **HealthmateUI**: API失敗 → ユーザーフレンドリーなエラー表示

## Security Architecture

### Authentication & Authorization
- **Cognito User Pool**: 中央認証システム
- **JWT Tokens**: サービス間認証
- **IAM Roles**: AWS リソースアクセス制御

### Data Protection
- **Encryption in Transit**: HTTPS/TLS 1.3
- **Encryption at Rest**: DynamoDB暗号化
- **PII Handling**: 健康データの適切な匿名化

## Monitoring & Observability

### Logging Strategy
- **Structured Logging**: JSON形式での統一ログ
- **Correlation IDs**: リクエスト追跡用ID
- **User Context**: ログにユーザーIDを含める（PII除く）

### Metrics Collection
- **Service Health**: 各サービスの稼働状況
- **API Performance**: レスポンス時間・エラー率
- **User Engagement**: 機能利用状況

## Scalability Considerations

### Horizontal Scaling
- **HealthManagerMCP**: Lambda自動スケーリング
- **HealthCoachAI**: AgentCore Runtime スケーリング
- **HealthmateUI**: CDN + 静的ホスティング

### Data Scaling
- **DynamoDB**: オンデマンドスケーリング
- **Caching**: 頻繁アクセスデータのキャッシュ戦略
- **Archiving**: 古い活動データのアーカイブ