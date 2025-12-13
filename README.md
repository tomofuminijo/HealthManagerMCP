# HealthManagerMCP

HealthManagerMCPは、Healthmateエコシステムの中核となる健康情報管理MCPサーバーです。

## Healthmateエコシステム

Healthmateは以下の3つのプロジェクトで構成されます：

- **HealthManagerMCP**（このプロジェクト）: MCPサーバーでユーザーの健康情報の管理を行う
- **HealthCoachAI**（別プロジェクト）: HealthManagerMCPをツールとして利用するユーザーの健康上のアドバイスをして導くエージェントAI
- **HealthmateUI**（別プロジェクト）: このアプリのフロントUI

## 概要

HealthManagerMCPは、AWS上でサーバーレスアーキテクチャを採用し、以下の技術を統合して構築されています：

- Amazon Bedrock AgentCore Gateway（MCP対応）
- Amazon Cognito（OAuth 2.0認証）
- Amazon DynamoDB（データ永続化）
- AWS Lambda（ビジネスロジック）

## 主な機能

- **ユーザー管理**: ユーザー情報の作成、更新、取得
- **健康目標管理**: 長期的な健康目標（100歳まで健康寿命、アスリート体型など）の管理
- **健康ポリシー管理**: 具体的な行動ルール（ローカーボダイエット、16時間ファスティングなど）の管理
- **活動記録管理**: 日々の健康活動（体重、食事、運動、気分など）の記録と取得

## MCPツール

HealthManagerMCPは以下のMCPツールを提供します：

### UserManagement
- `addUser`: 新しいユーザー情報を作成
- `updateUser`: ユーザー情報を更新
- `getUser`: ユーザー情報を取得

### HealthGoalManagement
- `addGoal`: 新しい健康目標を追加
- `updateGoal`: 既存の健康目標を更新
- `deleteGoal`: 健康目標を削除
- `getGoals`: ユーザーのすべての健康目標を取得

### HealthPolicyManagement
- `addPolicy`: 新しい健康ポリシーを追加
- `updatePolicy`: 既存の健康ポリシーを更新
- `deletePolicy`: 健康ポリシーを削除
- `getPolicies`: ユーザーのすべての健康ポリシーを取得

### ActivityManagement
- `addActivities`: 指定した日に新しい活動を追加
- `updateActivity`: 特定の時刻の活動を部分的に更新
- `updateActivities`: 指定した日の全活動を置き換え
- `deleteActivity`: 特定の活動を削除
- `getActivities`: 指定した日の活動を取得
- `getActivitiesInRange`: 指定した期間の活動履歴を取得

## アーキテクチャ

```
HealthCoachAI/HealthmateUI → OAuth 2.0 → Cognito → MCP Gateway → Lambda → DynamoDB
```

## 開発状況

現在、既存の実装を保持しつつ、タスク1から段階的に実装を進めています。

詳細な実装計画については、`.kiro/specs/healthmanagermcp/tasks.md` を参照してください。

## ライセンス

このプロジェクトは、Healthmateエコシステムの一部として開発されています。