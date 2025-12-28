# 要件定義書

## はじめに

Health Observation Management機能は、HealthManagerシステム内でCoachAIエージェントがMCPプロトコルを通じて利用する健康経過観察管理ツールです。ユーザーの健康症状に対する経過観察を管理し、AIとの会話セッションを超えて継続的な健康状態の追跡と記録を可能にします。

## 用語集

- **HealthObservationManagement**: HealthManagerシステム内の健康経過観察管理ツール
- **ObservationRecord**: 経過観察記録
- **ProgressLog**: 進捗ログ
- **CheckItem**: チェック項目
- **MCPTool**: Model Context Protocol ツール
- **userId**: ユーザー識別子
- **observationId**: 経過観察識別子

## 要件

### 要件 1

**ユーザーストーリー:** CoachAIエージェントとして、MCPプロトコルを通じてユーザーの健康症状に対する経過観察を開始したいので、新しい経過観察記録を作成できるMCPツールが必要です。

#### 受け入れ基準

1. WHEN ユーザーが新しい経過観察を開始する場合、THE HealthObservationManagement SHALL 必要な情報（タイトル、説明、優先度、開始日時、目標日時、頻度、チェック項目）を含む経過観察記録を作成する
2. WHEN 経過観察記録が作成される場合、THE HealthObservationManagement SHALL 一意のobservationIdを自動生成する
3. WHEN 経過観察記録が作成される場合、THE HealthObservationManagement SHALL ステータスをIN_PROGRESSに設定する
4. WHEN 経過観察記録が作成される場合、THE HealthObservationManagement SHALL in_progress属性をTRUEに設定してLSIインデックスに含める
5. WHEN 経過観察記録が作成される場合、THE HealthObservationManagement SHALL 作成日時と更新日時を現在時刻に設定する

### 要件 2

**ユーザーストーリー:** CoachAIエージェントとして、MCPプロトコルを通じて特定の経過観察記録の詳細を確認したいので、observationIdを指定して記録を取得できるMCPツールが必要です。

#### 受け入れ基準

1. WHEN 有効なuserIdとobservationIdが提供される場合、THE HealthObservationManagement SHALL 対応する経過観察記録を返す
2. WHEN 存在しないobservationIdが指定される場合、THE HealthObservationManagement SHALL 適切なエラーメッセージを返す
3. WHEN 他のユーザーのobservationIdが指定される場合、THE HealthObservationManagement SHALL アクセス権限エラーを返す

### 要件 3

**ユーザーストーリー:** CoachAIエージェントとして、MCPプロトコルを通じてユーザーの過去の経過観察履歴を把握したいので、指定期間内の経過観察記録を取得できるMCPツールが必要です。

#### 受け入れ基準

1. WHEN 有効なuserIdと日付範囲が提供される場合、THE HealthObservationManagement SHALL 指定期間内に作成された経過観察記録を返す
2. WHEN 開始日が終了日より後の場合、THE HealthObservationManagement SHALL 入力検証エラーを返す
3. WHEN 日付形式が無効な場合、THE HealthObservationManagement SHALL フォーマットエラーを返す
4. WHEN 指定期間に記録が存在しない場合、THE HealthObservationManagement SHALL 空のリストを返す

### 要件 4

**ユーザーストーリー:** CoachAIエージェントとして、MCPプロトコルを通じて現在進行中の経過観察を把握したいので、ユーザーの実施中の経過観察記録のみを取得できるMCPツールが必要です。

#### 受け入れ基準

1. WHEN 有効なuserIdが提供される場合、THE HealthObservationManagement SHALL ステータスがIN_PROGRESSの経過観察記録のみを返す
2. WHEN LSIインデックスを使用する場合、THE HealthObservationManagement SHALL in_progress属性がTRUEの記録のみを効率的に取得する
3. WHEN 進行中の経過観察が存在しない場合、THE HealthObservationManagement SHALL 空のリストを返す

### 要件 5

**ユーザーストーリー:** CoachAIエージェントとして、MCPプロトコルを通じて経過観察の内容を修正したいので、既存の経過観察記録の特定の属性を更新できるMCPツールが必要です。

#### 受け入れ基準

1. WHEN 有効なuserId、observationId、および更新データが提供される場合、THE HealthObservationManagement SHALL 指定された属性のみを差分更新する
2. WHEN 更新が実行される場合、THE HealthObservationManagement SHALL updatedAt属性を現在時刻に更新する
3. WHEN 存在しないobservationIdが指定される場合、THE HealthObservationManagement SHALL リソース未発見エラーを返す
4. WHEN 無効な属性値が提供される場合、THE HealthObservationManagement SHALL 検証エラーを返す
5. WHEN 記録全体の置き換えが試行される場合、THE HealthObservationManagement SHALL それを拒否し、差分更新のみを許可する

### 要件 6

**ユーザーストーリー:** CoachAIエージェントとして、MCPプロトコルを通じて日々の経過観察結果を記録したいので、既存の経過観察記録に進捗ログを追加できるMCPツールが必要です。

#### 受け入れ基準

1. WHEN 有効なuserId、observationId、および進捗データが提供される場合、THE HealthObservationManagement SHALL progressLogsリストに新しいエントリを追加する
2. WHEN 進捗ログが追加される場合、THE HealthObservationManagement SHALL 記録日時（recordedAt）を現在時刻に自動設定する
3. WHEN 進捗ログが追加される場合、THE HealthObservationManagement SHALL updatedAt属性を現在時刻に更新する
4. WHEN 必須フィールド（date、note）が欠けている場合、THE HealthObservationManagement SHALL 検証エラーを返す

### 要件 7

**ユーザーストーリー:** CoachAIエージェントとして、MCPプロトコルを通じて経過観察を正常に終了したいので、結論を記録して経過観察を完了状態にできるMCPツールが必要です。

#### 受け入れ基準

1. WHEN 有効なuserId、observationId、および結論が提供される場合、THE HealthObservationManagement SHALL ステータスをCOMPLETEDに変更する
2. WHEN 経過観察が完了される場合、THE HealthObservationManagement SHALL conclusion属性に提供された結論を設定する
3. WHEN 経過観察が完了される場合、THE HealthObservationManagement SHALL in_progress属性を削除してLSIインデックスから除外する
4. WHEN 経過観察が完了される場合、THE HealthObservationManagement SHALL updatedAt属性を現在時刻に更新する
5. WHEN 結論が提供されない場合、THE HealthObservationManagement SHALL 必須フィールドエラーを返す

### 要件 8

**ユーザーストーリー:** CoachAIエージェントとして、MCPプロトコルを通じて経過観察を中止する必要がある場合に、キャンセル理由を記録して経過観察をキャンセル状態にできるMCPツールが必要です。

#### 受け入れ基準

1. WHEN 有効なuserId、observationId、およびキャンセル理由が提供される場合、THE HealthObservationManagement SHALL ステータスをCANCELLEDに変更する
2. WHEN 経過観察がキャンセルされる場合、THE HealthObservationManagement SHALL conclusion属性にキャンセル理由を設定する
3. WHEN 経過観察がキャンセルされる場合、THE HealthObservationManagement SHALL in_progress属性を削除してLSIインデックスから除外する
4. WHEN 経過観察がキャンセルされる場合、THE HealthObservationManagement SHALL updatedAt属性を現在時刻に更新する
5. WHEN キャンセル理由が提供されない場合、THE HealthObservationManagement SHALL 必須フィールドエラーを返す

### 要件 9

**ユーザーストーリー:** システム管理者として、MCPツールのデータ整合性を保ちたいので、すべての経過観察データが適切に検証され、DynamoDBに永続化される機能が必要です。

#### 受け入れ基準

1. WHEN 日時データが保存される場合、THE HealthObservationManagement SHALL ISO 8601形式（"2025-12-28T00:00:00Z"）で検証する
2. WHEN 頻度データが保存される場合、THE HealthObservationManagement SHALL ISO 8601 Duration形式（"P1D"など）で検証する
3. WHEN 優先度が設定される場合、THE HealthObservationManagement SHALL 1から5の範囲内であることを検証する
4. WHEN ステータスが設定される場合、THE HealthObservationManagement SHALL 有効な値（IN_PROGRESS、COMPLETED、CANCELLED）であることを検証する
5. WHEN DynamoDBエラーが発生する場合、THE HealthObservationManagement SHALL 適切なMCP形式のエラーレスポンスを返す

### 要件 10

**ユーザーストーリー:** CoachAIエージェント開発者として、MCPプロトコルを通じて経過観察機能にアクセスしたいので、すべての操作が標準化されたMCPツールとして提供される機能が必要です。

#### 受け入れ基準

1. WHEN MCPクライアントがツールを呼び出す場合、THE HealthObservationManagement SHALL 統一されたレスポンス形式（success、data、messageフィールド）を返す
2. WHEN エラーが発生する場合、THE HealthObservationManagement SHALL 統一されたエラー形式（success: false、error、messageフィールド）を返す
3. WHEN JWTトークンが提供される場合、THE HealthObservationManagement SHALL ユーザーIDを抽出して認証を行う
4. WHEN 無効なJWTトークンが提供される場合、THE HealthObservationManagement SHALL 認証エラーを返す
5. WHEN すべてのMCPツールが呼び出される場合、THE HealthObservationManagement SHALL 適切なログ記録を行う