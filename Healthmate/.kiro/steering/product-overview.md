# Healthmate プロダクト概要

## Product Vision

Healthmate プロダクトは、AI駆動の包括的健康管理プラットフォームです。ユーザーが長期的な健康目標（100歳まで健康に生きるなど）を達成できるよう支援します。

## Core Value Proposition

- **AI-Powered Personalization**: 個人の健康データに基づくパーソナライズされたアドバイス
- **Comprehensive Tracking**: 食事、運動、睡眠、気分など包括的な活動追跡
- **Goal-Oriented Management**: 目標指向の健康ポリシー管理
- **Seamless AI Integration**: 外部AIクライアント（ChatGPT、Claude、Gemini）との直接連携

## Service Architecture

Healthmate プロダクトは3つの独立したサービスで構成されています：

### HealthManagerMCP サービス
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

## Key Features

### Health Goal Management
- 長期目標（長寿、フィットネス、体重管理）の設定と追跡
- 進捗の可視化と達成度評価
- 目標に基づく個別アドバイス

### Health Policy Management  
- 実行可能なルール（ローカーボダイエット、間欠的断食）の管理
- ポリシーの有効性追跡
- ライフスタイルに合わせた調整

### Activity Tracking
- 日々の健康活動の詳細ログ
- 複数の活動タイプ（食事、運動、睡眠、気分、体重など）
- 時系列データの分析と傾向把握

### AI Integration
- 外部AIアシスタントとの直接連携
- リアルタイムの健康コーチング
- 自然言語での健康データ操作

## Target Users

### Primary Users
- **健康志向の個人**: AI支援による健康管理を求める人
- **目標達成志向**: 具体的な健康目標を持つ人
- **データ活用志向**: 包括的な健康データ追跡を望む人

### Secondary Users  
- **AIアシスタント利用者**: ChatGPT、Claude等を日常的に使用する人
- **テクノロジー愛好者**: 最新の健康管理技術を試したい人

## Multi-language Support

- **日本語**: プライマリ言語として完全対応
- **英語**: セカンダリ言語として対応
- **将来拡張**: 他言語への展開可能性

## Business Model

- **B2C SaaS**: 個人ユーザー向けサブスクリプション
- **AI Integration**: 外部AIプラットフォームとの連携による価値提供
- **Data Insights**: 匿名化された健康データインサイトの活用

## Success Metrics

### User Engagement
- 日次アクティブユーザー数
- 健康データ入力頻度
- AI コーチとの対話回数

### Health Outcomes
- ユーザーの健康目標達成率
- 健康指標の改善度
- 長期継続利用率

### Technical Performance
- システム可用性（99.9%以上）
- API レスポンス時間
- データ整合性

## Competitive Advantages

1. **MCP Protocol Integration**: 標準化されたAI連携プロトコル
2. **Serverless Architecture**: 高可用性・低コスト運用
3. **Comprehensive Data Model**: 包括的な健康データ管理
4. **AI-First Design**: AI との連携を前提とした設計