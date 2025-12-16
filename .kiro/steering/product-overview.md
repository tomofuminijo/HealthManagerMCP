# Healthmate プロダクト概要

## Product Vision

Healthmate プロダクトは、AI駆動の包括的健康管理プラットフォームです。ユーザーが長期的な健康目標（100歳まで健康に生きるなど）を達成できるよう支援します。

## Service Architecture

Healthmate プロダクトは3つの独立したサービスで構成されています：

### Healthmate-HealthManager サービス（このサービス）
- **役割**: 健康データ管理バックエンド
- **技術**: Model Context Protocol (MCP) サーバー
- **責任**: データ永続化、API提供、認証・認可

### HealthCoachAI サービス  
- **役割**: AI健康コーチエージェント
- **技術**: Amazon Bedrock AgentCore Runtime
- **責任**: パーソナライズされた健康アドバイス、ユーザー対話

### HealthmateUI サービス
- **役割**: Webフロントエンドインターフェース
- **技術**: モダンWebフレームワーク
- **責任**: ユーザーインターフェース、認証フロー、データ可視化

## Terminology Standards

### 階層構造
- **プロダクト**: Healthmate プロダクト（完全なソリューション）
- **ワークスペース**: Healthmate ワークスペース（開発環境）
- **サービス**: 個別サービス（Healthmate-HealthManager、HealthCoachAI、HealthmateUI）

### 命名規則
- **サービス名**: 必ず「サービス」を付けて呼ぶ
- **AWS リソース**: `healthmate-` プレフィックス統一
- **コード**: snake_case（関数）、PascalCase（クラス）

## Integration Points

### データフロー
```
HealthmateUI サービス
    ↓ (JWT Token + User Input)
HealthCoachAI サービス  
    ↓ (MCP Protocol)
Healthmate-HealthManager サービス
    ↓ (DynamoDB Operations)
Health Data Storage
```

### 通信プロトコル
- **UI ↔ AI**: WebSocket/Server-Sent Events（リアルタイムチャット）
- **AI ↔ Backend**: Model Context Protocol (MCP)
- **UI ↔ Backend**: RESTful API（直接データ操作時）

## Deployment Order

### 必須デプロイ順序
```
1. Healthmate-HealthManager サービス（基盤インフラ）
2. HealthCoachAI サービス（AI エージェント）
3. HealthmateUI サービス（フロントエンド）
```