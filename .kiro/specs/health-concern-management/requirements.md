# 要件定義書

## 概要

HealthConcernManagement機能は、Healthmate-HealthManagerサービスに追加される新しいMCPツールセットです。ユーザーの身体面・メンタル面の悩みや不調を管理し、AIコーチが適切なアドバイスを提供するためのデータ基盤を提供します。

## 用語集

- **System**: HealthConcernManagementシステム
- **User**: Healthmateプロダクトのユーザー
- **Concern**: ユーザーの健康に関する悩みや不調
- **MCP_Client**: Model Context Protocolクライアント（CoachAIエージェント等）
- **JWT_Token**: Cognito認証によるJSONウェブトークン

## 要件

### 要件1: 悩み事の登録

**ユーザーストーリー:** ユーザーとして、身体面やメンタル面の悩みを記録したい。そうすることで、AIコーチが私の状況を理解し、適切なアドバイスを提供できるようになる。

#### 受入基準

1. WHEN MCP_Clientが有効なJWT_Tokenと悩み事データを提供する THEN THE System SHALL 新しい悩み事レコードを作成する
2. WHEN 悩み事データにcategoryが指定される THEN THE System SHALL PHYSICAL、MENTAL、またはその両方を受け入れる
3. WHEN severityが指定されない THEN THE System SHALL デフォルト値3を設定する
4. WHEN statusが指定されない THEN THE System SHALL デフォルト値ACTIVEを設定する
5. THE System SHALL 作成時にconcernIdとしてUUIDを自動生成する
6. THE System SHALL 作成時にcreatedAtとupdatedAtにISO8601形式の現在時刻を設定する

### 要件2: 悩み事の更新

**ユーザーストーリー:** ユーザーとして、既存の悩み事の状況や詳細を更新したい。そうすることで、改善状況や新しい対処法を記録できる。

#### 受入基準

1. WHEN MCP_Clientが有効なJWT_Tokenと既存のconcernIdを提供する THEN THE System SHALL 該当する悩み事レコードを更新する
2. WHEN 存在しないconcernIdが指定される THEN THE System SHALL エラーを返し、データを変更しない
3. WHEN 部分的な更新データが提供される THEN THE System SHALL 指定されたフィールドのみを更新する
4. THE System SHALL 更新時にupdatedAtフィールドを現在時刻に更新する
5. WHEN statusがIMPROVEDまたはRESOLVEDに変更される THEN THE System SHALL 変更を正常に処理する

### 要件3: 悩み事の削除

**ユーザーストーリー:** ユーザーとして、不要になった悩み事レコードを削除したい。そうすることで、現在関連性のある悩み事のみを管理できる。

#### 受入基準

1. WHEN MCP_Clientが有効なJWT_Tokenと既存のconcernIdを提供する THEN THE System SHALL 該当する悩み事レコードを削除する
2. WHEN 存在しないconcernIdが指定される THEN THE System SHALL エラーを返す
3. WHEN 他のユーザーの悩み事レコードが指定される THEN THE System SHALL アクセスを拒否する

### 要件4: 悩み事の取得

**ユーザーストーリー:** AIコーチとして、ユーザーの現在の悩み事を把握したい。そうすることで、個人の状況に応じたアドバイスを提供できる。

#### 受入基準

1. WHEN MCP_Clientが有効なJWT_Tokenを提供する THEN THE System SHALL そのユーザーのすべての悩み事レコードを返す
2. THE System SHALL 悩み事レコードをcreatedAtの降順（新しい順）で返す
3. WHEN ユーザーに悩み事レコードが存在しない THEN THE System SHALL 空の配列を返す
4. THE System SHALL 他のユーザーの悩み事レコードを含めない

### 要件5: データ永続化

**ユーザーストーリー:** システム管理者として、悩み事データが確実に保存されることを確認したい。そうすることで、ユーザーの重要な健康情報が失われることを防げる。

#### 受入基準

1. THE System SHALL すべての悩み事データをDynamoDBテーブルに永続化する
2. THE System SHALL パーティションキーとしてUSER#{userId}を使用する
3. THE System SHALL ソートキーとしてCONCERN#{concernId}を使用する
4. WHEN データベース操作が失敗する THEN THE System SHALL 適切なエラーメッセージを返す

### 要件6: 認証・認可

**ユーザーストーリー:** システム管理者として、悩み事データへのアクセスが適切に制御されることを確認したい。そうすることで、プライベートな健康情報のセキュリティを保てる。

#### 受入基準

1. THE System SHALL すべてのMCPツール呼び出しでJWT_Tokenを要求する
2. WHEN 無効なJWT_Tokenが提供される THEN THE System SHALL 認証エラーを返す
3. THE System SHALL JWT_TokenからuserIdを抽出し、データアクセスを制限する
4. THE System SHALL ユーザーが自分の悩み事データのみにアクセスできるよう制御する

### 要件7: MCPプロトコル準拠

**ユーザーストーリー:** 開発者として、HealthConcernManagementツールが標準的なMCPプロトコルに準拠していることを確認したい。そうすることで、他のMCPクライアントとの互換性を保てる。

#### 受入基準

1. THE System SHALL AddConcern、UpdateConcern、DeleteConcern、GetConcernsの4つのMCPツールを提供する
2. THE System SHALL 各ツールのスキーマをMCP形式で定義する
3. THE System SHALL MCP標準のレスポンス形式でデータを返す
4. WHEN ツール実行が成功する THEN THE System SHALL success: trueとデータを含むレスポンスを返す
5. WHEN ツール実行が失敗する THEN THE System SHALL success: falseとエラー情報を含むレスポンスを返す