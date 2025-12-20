# Requirements Document

## Introduction

Healthmate-HealthManagerサービスのAgentCore Gateway認証システムをM2M（Machine-to-Machine）認証に対応させるためのリファクタリングを行います。現在のユーザー認証ベースのCognito User Poolから、AgentCore Gatewayに最適化されたM2M認証システムへの移行を実現します。

## Glossary

- **M2M Authentication**: Machine-to-Machine認証。サービス間の自動認証を行う仕組み
- **AgentCore Gateway**: Amazon Bedrock AgentCoreのMCPプロトコルゲートウェイ
- **Gateway Identity**: AgentCore Gatewayが使用する認証アイデンティティ
- **Client Credentials Flow**: OAuth 2.0のクライアントクレデンシャル認証フロー
- **Secrets Manager**: AWS Secrets Managerサービス
- **Custom Scope**: カスタムOAuthスコープ（HealthManager/HealthTarget:invoke形式）
- **Discovery URL**: OIDC Discovery エンドポイントURL
- **CDK Stack**: AWS Cloud Development Kitのインフラストラクチャスタック

## Requirements

### Requirement 1

**User Story:** As a system architect, I want to implement M2M authentication for AgentCore Gateway, so that the gateway can authenticate automatically without user intervention.

#### Acceptance Criteria

1. WHEN the system creates a Cognito User Pool THEN the system SHALL configure it specifically for M2M authentication with self-signup disabled
2. WHEN the system creates an App Client THEN the system SHALL enable client credentials flow and generate a client secret
3. WHEN the system defines OAuth scopes THEN the system SHALL create a custom scope in the format "HealthManager/HealthTarget:invoke"
4. WHEN the system stores client credentials THEN the system SHALL save the client secret to AWS Secrets Manager with proper naming convention
5. WHEN the system outputs configuration THEN the system SHALL provide all necessary values for AgentCore Identity and Gateway setup

### Requirement 2

**User Story:** As a DevOps engineer, I want the client secret to be securely stored in Secrets Manager, so that AgentCore Identity can access it safely during deployment.

#### Acceptance Criteria

1. WHEN the system creates a client secret THEN the system SHALL store it in Secrets Manager with the name format "AgentCoreIdentitySecret/HealthManager/{stack_name}"
2. WHEN the system stores the secret THEN the system SHALL use the CDK SecretValue mechanism to ensure secure handling
3. WHEN the system configures removal policy THEN the system SHALL set it to DESTROY for development environments
4. WHEN the system outputs the secret ARN THEN the system SHALL provide the full ARN for AgentCore Identity configuration

### Requirement 3

**User Story:** As an integration developer, I want proper CloudFormation outputs for AgentCore setup, so that I can configure Gateway Identity and Gateway resources correctly.

#### Acceptance Criteria

1. WHEN the system deploys the stack THEN the system SHALL output the User Pool ID for OIDC configuration
2. WHEN the system deploys the stack THEN the system SHALL output the App Client ID for authentication
3. WHEN the system deploys the stack THEN the system SHALL output the Secrets Manager ARN for client secret access
4. WHEN the system deploys the stack THEN the system SHALL output the OIDC Discovery URL for identity provider configuration
5. WHEN the system deploys the stack THEN the system SHALL output the custom OAuth scope for permission configuration

### Requirement 4

**User Story:** As a developer, I want to maintain backward compatibility during the transition, so that existing integrations continue to work while new M2M authentication is implemented.

#### Acceptance Criteria

1. WHEN the system refactors authentication THEN the system SHALL preserve existing DynamoDB table configurations
2. WHEN the system refactors authentication THEN the system SHALL preserve existing Lambda function configurations
3. WHEN the system refactors authentication THEN the system SHALL maintain existing AgentCore Gateway and Target configurations
4. WHEN the system refactors authentication THEN the system SHALL preserve existing CloudFormation output names where possible

### Requirement 5

**User Story:** As a security engineer, I want proper IAM configuration for M2M authentication, so that the system follows security best practices.

#### Acceptance Criteria

1. WHEN the system configures the User Pool THEN the system SHALL disable self-signup to prevent unauthorized access
2. WHEN the system configures the App Client THEN the system SHALL enable only the client credentials authentication flow
3. WHEN the system stores secrets THEN the system SHALL use AWS Secrets Manager with proper encryption
4. WHEN the system configures removal policies THEN the system SHALL set appropriate policies for development vs production environments
5. WHEN the system defines custom scopes THEN the system SHALL follow the AgentCore naming convention for resource access