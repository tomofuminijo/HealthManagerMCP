# 要件文書

## はじめに

GetUserHolisticData MCPツールは、ユーザーの包括的な健康データを一括で取得するための新しいMCPツールです。このツールは、AI健康コーチが効果的なアドバイスを提供するために必要な、ユーザーの最新の健康状態を包括的に把握することを目的としています。

## 用語集

- **HolisticUserDataService**: ユーザーの包括的健康データを取得するMCPサービス
- **User_Health_Profile**: ユーザーの基本情報、目標、ポリシー、悩みを含む健康プロファイル
- **Recent_Activity_Data**: 本日を含む直近3日間の活動履歴データ
- **Body_Measurement_Data**: 身体測定データ（最新、最古、直近3日分）
- **Progress_Observation**: 現在進行中（InProgress）の経過観測データ
- **Daily_Reflection**: 前日の振り返り日記データ

## 要件

### 要件1: 包括的健康データ取得

**ユーザーストーリー:** AI健康コーチとして、単一のAPI呼び出しでユーザーの包括的な健康データを取得したい。これにより、パーソナライズされた文脈に関連する健康アドバイスを提供できる。

#### 受入基準

1. WHEN 有効なユーザーIDでGetUserHolisticDataツールが呼び出される THEN HolisticUserDataService はユーザープロファイル情報を返す
2. WHEN GetUserHolisticDataツールが呼び出される THEN HolisticUserDataService はユーザーのすべてのアクティブな健康目標を返す
3. WHEN GetUserHolisticDataツールが呼び出される THEN HolisticUserDataService はユーザーのすべてのアクティブな健康ポリシーを返す
4. WHEN GetUserHolisticDataツールが呼び出される THEN HolisticUserDataService はユーザーの現在の健康コンサーンをすべて返す
5. WHEN GetUserHolisticDataツールが呼び出される THEN HolisticUserDataService は最新、最古、直近3日分を含む身体測定データを返す
6. WHEN GetUserHolisticDataツールが呼び出される THEN HolisticUserDataService は当日と過去2日間の活動履歴を返す
7. WHEN GetUserHolisticDataツールが呼び出される THEN HolisticUserDataService はすべてのInProgress状態の健康観測を返す
8. WHEN GetUserHolisticDataツールが呼び出される THEN HolisticUserDataService は前日の振り返り日記エントリを返す

### 要件2: データ統合と構造化

**ユーザーストーリー:** AI健康コーチとして、包括的データが適切に構造化され整理されていることを望む。これにより、情報を簡単に処理し分析できる。

#### 受入基準

1. WHEN 包括的データが返される THEN HolisticUserDataService は論理的なセクション（プロファイル、目標、ポリシー、悩み、測定、活動、観測、振り返り）にデータを整理する
2. WHEN 包括的データが返される THEN HolisticUserDataService はデータ取得タイムスタンプやデータ鮮度指標などのメタデータを含める
3. WHEN 包括的データが返される THEN HolisticUserDataService はすべてのセクションで一貫したデータフォーマットを維持する
4. WHEN 包括的データが返される THEN HolisticUserDataService は欠損データセクションを省略するのではなく、空の配列やnull値を含める

### 要件3: セキュリティとアクセス制御

**ユーザーストーリー:** システム管理者として、包括的データ取得が適切なアクセス制御を持つことを望む。これによりユーザーのプライバシーが保護される。

#### 受入基準

1. WHEN GetUserHolisticDataツールが呼び出される THEN HolisticUserDataService はMCP Gatewayから渡されたユーザーIDを使用する
2. WHEN ユーザーがデータを要求する THEN HolisticUserDataService は指定されたユーザーに属するデータのみを返す
3. WHEN DynamoDBテーブルにアクセスする THEN HolisticUserDataService は適切なIAM権限と最小権限アクセスを使用する

### 要件4: エラーハンドリングと可用性

**ユーザーストーリー:** AI健康コーチとして、包括的データ取得がエラーを適切に処理することを望む。これにより、一部のデータが存在しない場合でも適切な応答を提供できる。

#### 受入基準

1. WHEN DynamoDBクエリでシステムエラーが発生する THEN HolisticUserDataService は適切なエラーをスローして処理を停止する
2. WHEN 特定のカテゴリでユーザーのデータが存在しない THEN HolisticUserDataService は空の構造を返して他のセクションの処理を継続する
3. WHEN データベース接続エラーが発生する THEN HolisticUserDataService は説明的なエラーメッセージと共に例外をスローする
4. WHEN 予期しないデータ形式が検出される THEN HolisticUserDataService は適切なエラーをスローして処理を停止する

### 要件5: パフォーマンスと効率性

**ユーザーストーリー:** システムオペレーターとして、包括的データ取得が効率的でパフォーマンスが良いことを望む。これによりシステムが複数の同時リクエストを処理できる。

#### 受入基準

1. WHEN 最近の活動データを取得する THEN HolisticUserDataService は指定された3日間の範囲にクエリを制限する
2. WHEN 身体測定を取得する THEN HolisticUserDataService はPartitionKeyとSortKeyを使用して効率的にクエリする
3. WHEN 各データセクションを取得する THEN HolisticUserDataService は適切なDynamoDBクエリパターンを使用する
4. WHEN 大量のアイテムが返される可能性がある THEN HolisticUserDataService は適切な制限を設定する

### 要件6: MCPスキーマ定義

**ユーザーストーリー:** 開発者として、GetUserHolisticDataツールの明確なMCPスキーマ定義を望む。これによりAIクライアントと適切に統合できる。

#### 受入基準

1. THE HolisticUserDataService はGetUserHolisticDataツールの包括的なMCPスキーマを定義する
2. THE MCPスキーマはユーザー識別要件を含む入力パラメータを指定する
3. THE MCPスキーマはすべてのデータセクションを含む完全な出力構造を定義する
4. THE MCPスキーマは適切なデータ型定義と検証ルールを含める
5. THE MCPスキーマは既存のHealthManager MCPアーキテクチャと互換性がある

### 要件7: 既存システムとの統合

**ユーザーストーリー:** システムアーキテクトとして、包括的データ取得が既存のHealthManagerコンポーネントとシームレスに統合されることを望む。これによりシステムの一貫性が維持される。

#### 受入基準

1. WHEN 新しいツールを実装する THEN HolisticUserDataService は既存のLambda関数やデータベーススキーマを変更しない
2. WHEN 新しいLambda関数を追加する THEN HolisticUserDataService は既存の命名規則とパターンに従う
3. WHEN Lambda関数を実装する THEN HolisticUserDataService は既存のLambda実装作法（エラーハンドリング、ログ出力、レスポンス形式）に従う
4. WHEN CDKインフラストラクチャと統合する THEN HolisticUserDataService は既存のIAMロールと権限パターンを使用する
5. WHEN MCPゲートウェイに追加する THEN HolisticUserDataService は既存のツール登録との互換性を維持する