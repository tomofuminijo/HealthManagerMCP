# Requirements Document

## Introduction

HealthManagerサービスに身体測定値記録機能を追加します。ユーザーが体重、身長、体脂肪率などの身体測定データを記録し、履歴を管理できる機能を提供します。AIエージェントとの自然な対話を通じて測定値を記録し、最新・最古の記録を効率的に取得できるシステムを構築します。

## Glossary

- **Body_Measurement_System**: 身体測定値記録システム
- **Measurement_Record**: 個別の測定記録
- **Latest_Record**: 最新の測定値を保持する特別なレコード
- **Oldest_Record**: 最古の測定値を保持する特別なレコード
- **MCP_Tool**: Model Context Protocol ツール
- **DynamoDB_Table**: 身体測定データを格納するテーブル
- **LSI**: Local Secondary Index（ローカルセカンダリインデックス）

## Requirements

### Requirement 1

**User Story:** As a user, I want to record my body measurements through natural conversation with the AI agent, so that I can easily track my health progress over time.

#### Acceptance Criteria

1. WHEN a user tells the AI agent their current weight, THE Body_Measurement_System SHALL record the weight with current timestamp
2. WHEN a user specifies a measurement time (e.g., "今日の8:00に測った"), THE Body_Measurement_System SHALL record the measurement with the specified timestamp
3. WHEN a user provides multiple measurements in one statement, THE Body_Measurement_System SHALL record all provided measurements with the same timestamp
4. WHEN a measurement is recorded, THE Body_Measurement_System SHALL update the latest record with the new measurement data
5. WHEN a measurement is recorded, THE Body_Measurement_System SHALL preserve existing measurement types in the latest record that were not updated

### Requirement 2

**User Story:** As a user, I want my measurement history to be stored persistently, so that I can track changes over time and maintain a complete health record.

#### Acceptance Criteria

1. THE Body_Measurement_System SHALL store each measurement record in DynamoDB with unique timestamp
2. WHEN storing measurement records, THE Body_Measurement_System SHALL use partition key format "USER#{user_id}"
3. WHEN storing measurement records, THE Body_Measurement_System SHALL use sort key format "MEASUREMENT#{timestamp}"
4. THE Body_Measurement_System SHALL support weight measurements in kilograms with decimal precision
5. THE Body_Measurement_System SHALL support height measurements in centimeters with decimal precision
6. THE Body_Measurement_System SHALL support body fat percentage measurements with decimal precision

### Requirement 3

**User Story:** As a user, I want to quickly access my latest and oldest measurements, so that I can see my current status and track long-term progress.

#### Acceptance Criteria

1. THE Body_Measurement_System SHALL maintain a special "latest" record containing the most recent values for all measurement types
2. THE Body_Measurement_System SHALL maintain a special "oldest" record containing the first recorded values for all measurement types
3. WHEN a new measurement is recorded, THE Body_Measurement_System SHALL update the latest record with the new measurement while preserving other measurement types from previous records
4. THE Body_Measurement_System SHALL create a Local Secondary Index with "record_type" as sort key for efficient latest/oldest record retrieval
5. THE Body_Measurement_System SHALL only assign "latest" or "oldest" values to the record_type attribute for special records

### Requirement 4

**User Story:** As a user, I want to correct or remove incorrect measurement records, so that I can maintain accurate health data.

#### Acceptance Criteria

1. WHEN a user requests to update a specific measurement record, THE Body_Measurement_System SHALL modify the record with new values
2. WHEN a measurement record is updated, THE Body_Measurement_System SHALL recalculate and update the latest record if the updated record was the most recent
3. WHEN a user requests to delete a specific measurement record, THE Body_Measurement_System SHALL remove the record from the database
4. WHEN the latest measurement record is deleted, THE Body_Measurement_System SHALL recalculate the latest record from remaining measurements
5. WHEN the oldest measurement record is deleted, THE Body_Measurement_System SHALL recalculate the oldest record from remaining measurements

### Requirement 5

**User Story:** As a developer, I want MCP tools for body measurement management, so that AI agents can interact with the measurement data through standardized interfaces.

#### Acceptance Criteria

1. THE Body_Measurement_System SHALL provide an "addBodyMeasurement" MCP_Tool for recording new measurements
2. THE Body_Measurement_System SHALL provide an "updateBodyMeasurement" MCP_Tool for modifying existing measurements
3. THE Body_Measurement_System SHALL provide a "deleteBodyMeasurement" MCP_Tool for removing measurement records
4. THE Body_Measurement_System SHALL provide a "getLatestMeasurements" MCP_Tool for retrieving current measurement values
5. THE Body_Measurement_System SHALL provide a "getOldestMeasurements" MCP_Tool for retrieving initial measurement values
6. THE Body_Measurement_System SHALL provide a "getMeasurementHistory" MCP_Tool for retrieving measurement records within a date range
7. WHEN MCP tools are called, THE Body_Measurement_System SHALL validate user authentication through JWT tokens

### Requirement 6

**User Story:** As a user, I want my measurement data to be validated and handled safely, so that I can trust the accuracy and security of my health records.

#### Acceptance Criteria

1. WHEN invalid measurement values are provided, THE Body_Measurement_System SHALL reject the input and return descriptive error messages
2. THE Body_Measurement_System SHALL validate that weight values are positive numbers within reasonable ranges (1-1000 kg)
3. THE Body_Measurement_System SHALL validate that height values are positive numbers within reasonable ranges (50-300 cm)
4. THE Body_Measurement_System SHALL validate that body fat percentage values are between 0 and 100
5. WHEN measurement timestamps are provided, THE Body_Measurement_System SHALL validate that they are not in the future
6. WHEN updating or deleting measurements, THE Body_Measurement_System SHALL verify that the record belongs to the authenticated user

### Requirement 7

**User Story:** As a system administrator, I want the measurement system to integrate seamlessly with existing HealthManager infrastructure, so that it maintains consistency with other health data management features.

#### Acceptance Criteria

1. THE Body_Measurement_System SHALL use the same authentication patterns as existing HealthManager MCP tools
2. THE Body_Measurement_System SHALL follow the same error handling patterns as existing Lambda functions
3. THE Body_Measurement_System SHALL use consistent DynamoDB table naming conventions with "healthmate-" prefix
4. THE Body_Measurement_System SHALL implement the same logging and monitoring patterns as existing services
5. THE Body_Measurement_System SHALL be deployable through the existing CDK infrastructure stack