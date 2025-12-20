from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    CfnOutput,
    SecretValue,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_logs as logs,
    aws_cognito as cognito,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct
import os
import json

# AgentCore パッケージをインポート（正式版）
from aws_cdk import aws_bedrockagentcore as bedrockagentcore


class HealthmateHealthManagerStack(Stack):
    """
    Main CDK Stack for Healthmate-HealthManager Application

    This stack manages the following resources:
    - DynamoDB Tables (Users, Health Goals, Health Policies, Activity Records)
    - Cognito User Pool (OAuth 2.0 IdP)
    - Lambda Functions (User, HealthGoal, HealthPolicy, Activity)
    - AgentCore Gateway (MCP Server)
    - IAM Roles and Permissions
    - CloudWatch Log Groups
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ========================================
        # DynamoDBテーブル
        # ========================================

        # ユーザーテーブル
        self.users_table = dynamodb.Table(
            self,
            "UsersTable",
            table_name="healthmate-users",
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # 開発用：本番環境ではRETAINに変更
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
        )

        # 健康目標テーブル
        self.goals_table = dynamodb.Table(
            self,
            "GoalsTable",
            table_name="healthmate-goals",
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="goalId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # 開発用：本番環境ではRETAINに変更
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
        )

        # GSI: goalType-index
        self.goals_table.add_global_secondary_index(
            index_name="goalType-index",
            partition_key=dynamodb.Attribute(
                name="goalType", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # GSI: status-index
        self.goals_table.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(
                name="status", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # 健康ポリシーテーブル
        self.policies_table = dynamodb.Table(
            self,
            "PoliciesTable",
            table_name="healthmate-policies",
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="policyId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # 開発用：本番環境ではRETAINに変更
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
        )

        # GSI: policyType-index
        self.policies_table.add_global_secondary_index(
            index_name="policyType-index",
            partition_key=dynamodb.Attribute(
                name="policyType", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # GSI: isActive-index
        self.policies_table.add_global_secondary_index(
            index_name="isActive-index",
            partition_key=dynamodb.Attribute(
                name="isActive", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # 活動記録テーブル
        self.activities_table = dynamodb.Table(
            self,
            "ActivitiesTable",
            table_name="healthmate-activities",
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="date", type=dynamodb.AttributeType.STRING  # YYYY-MM-DD形式
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # 開発用：本番環境ではRETAINに変更
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
        )

        # GSI: date-index（日付範囲クエリ用）
        self.activities_table.add_global_secondary_index(
            index_name="date-index",
            partition_key=dynamodb.Attribute(
                name="date", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ========================================
        # Cognito User Pool（M2M Authentication）
        # ========================================

        # M2M認証専用のCognito User Pool
        self.gateway_user_pool = cognito.UserPool(
            self,
            "HealthManagerM2MUserPool",
            user_pool_name="HealthManagerM2MUserPool",
            # M2M認証設定
            sign_in_aliases=cognito.SignInAliases(username=True),
            # セルフサインアップを無効化（M2M認証のため）
            self_sign_up_enabled=False,
            # パスワードポリシー（管理者作成ユーザー用）
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            # アカウント復旧設定（M2M用では不要だが設定）
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # 削除保護（開発用：本番環境では適切に設定）
            removal_policy=RemovalPolicy.DESTROY,
        )

        # AgentCore用のResource Serverとカスタムスコープを定義
        self.gateway_resource_server = self.gateway_user_pool.add_resource_server(
            "HealthManagerResourceServer",
            identifier="HealthManager",
            user_pool_resource_server_name="HealthManager MCP Resource Server",
            scopes=[
                cognito.ResourceServerScope(
                    scope_name="HealthTarget:invoke",
                    scope_description="Permission to invoke HealthTarget operations via MCP Gateway"
                )
            ]
        )

        # M2M認証専用のApp Client（AgentCore Gateway用）
        self.gateway_app_client = self.gateway_user_pool.add_client(
            "HealthManagerM2MAppClient",
            user_pool_client_name="AgentCoreGatewayClient",
            # クライアントシークレット生成（M2Mフローに必須）
            generate_secret=True,
            # OAuth設定（カスタムスコープ用）
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    client_credentials=True,  # M2M認証フロー
                ),
                scopes=[
                    # カスタムスコープ：HealthManager/HealthTarget:invoke
                    cognito.OAuthScope.resource_server(
                        self.gateway_resource_server, 
                        self.gateway_resource_server.scopes[0]
                    )
                ]
            ),
            # 認証フロー（クライアントクレデンシャルフローのみ）
            auth_flows=cognito.AuthFlow(
                # M2M認証では通常のユーザー認証フローは無効化
                user_password=False,
                user_srp=False,
                custom=False,
                # 管理者認証は保持（テスト用）
                admin_user_password=True,
            ),
            # トークン有効期限（M2M用に調整）
            access_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            id_token_validity=Duration.hours(1),
        )

        # クライアントクレデンシャルフローを有効化（CloudFormationレベルで設定）
        cfn_gateway_app_client = self.gateway_app_client.node.default_child
        cfn_gateway_app_client.add_property_override(
            "ExplicitAuthFlows",
            [
                "ALLOW_CLIENT_CREDENTIALS",  # M2M認証の核心
                "ALLOW_ADMIN_USER_PASSWORD_AUTH",  # テスト用
                "ALLOW_REFRESH_TOKEN_AUTH",  # トークン更新用
            ]
        )

        # ========================================
        # Secrets Manager統合
        # ========================================

        # クライアントシークレットをSecrets Managerに保存
        self.client_secret = secretsmanager.Secret(
            self,
            "HealthManagerM2MClientSecret",
            secret_name=f"AgentCoreIdentitySecret/HealthManager/{self.stack_name}",
            description="Client secret for AgentCore Gateway M2M authentication",
            # CDK SecretValueメカニズムを使用してクライアントシークレットを安全に保存
            secret_string_value=SecretValue.unsafe_plain_text(
                self.gateway_app_client.user_pool_client_secret.unsafe_unwrap()
            ),
            # 環境別RemovalPolicy設定（開発環境用のDESTROY）
            removal_policy=RemovalPolicy.DESTROY,  # 本番環境ではRETAINに変更
        )



        # ========================================
        # Lambda関数
        # ========================================

        # Lambda関数のコードパスを取得
        lambda_code_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "lambda"
        )

        # UserLambda用のCloudWatch Logsロググループ
        user_log_group = logs.LogGroup(
            self,
            "UserLambdaLogGroup",
            log_group_name="/aws/lambda/healthmanagermcp-user",
            retention=logs.RetentionDays.ONE_WEEK,  # 1週間保持
            removal_policy=RemovalPolicy.DESTROY,  # スタック削除時に削除
        )

        # UserLambda関数
        self.user_lambda = lambda_.Function(
            self,
            "UserLambda",
            function_name="healthmanagermcp-user",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="user.handler.lambda_handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "USERS_TABLE_NAME": self.users_table.table_name,
            },
            log_group=user_log_group,  # ロググループを明示的に指定
        )

        # UserLambdaにDynamoDBテーブルへのアクセス権限を付与
        self.users_table.grant_read_write_data(self.user_lambda)

        # HealthGoalLambda用のCloudWatch Logsロググループ
        health_goal_log_group = logs.LogGroup(
            self,
            "HealthGoalLambdaLogGroup",
            log_group_name="/aws/lambda/healthmanagermcp-health-goal",
            retention=logs.RetentionDays.ONE_WEEK,  # 1週間保持
            removal_policy=RemovalPolicy.DESTROY,  # スタック削除時に削除
        )

        # HealthGoalLambda関数
        self.health_goal_lambda = lambda_.Function(
            self,
            "HealthGoalLambda",
            function_name="healthmanagermcp-health-goal",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="health_goal.handler.lambda_handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "GOALS_TABLE_NAME": self.goals_table.table_name,
            },
            log_group=health_goal_log_group,  # ロググループを明示的に指定
        )

        # HealthGoalLambdaにDynamoDBテーブルへのアクセス権限を付与
        self.goals_table.grant_read_write_data(self.health_goal_lambda)

        # HealthPolicyLambda用のCloudWatch Logsロググループ
        health_policy_log_group = logs.LogGroup(
            self,
            "HealthPolicyLambdaLogGroup",
            log_group_name="/aws/lambda/healthmanagermcp-health-policy",
            retention=logs.RetentionDays.ONE_WEEK,  # 1週間保持
            removal_policy=RemovalPolicy.DESTROY,  # スタック削除時に削除
        )

        # HealthPolicyLambda関数
        self.health_policy_lambda = lambda_.Function(
            self,
            "HealthPolicyLambda",
            function_name="healthmanagermcp-health-policy",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="health_policy.handler.lambda_handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "POLICIES_TABLE_NAME": self.policies_table.table_name,
            },
            log_group=health_policy_log_group,  # ロググループを明示的に指定
        )

        # HealthPolicyLambdaにDynamoDBテーブルへのアクセス権限を付与
        self.policies_table.grant_read_write_data(self.health_policy_lambda)

        # ActivityLambda用のCloudWatch Logsロググループ
        activity_log_group = logs.LogGroup(
            self,
            "ActivityLambdaLogGroup",
            log_group_name="/aws/lambda/healthmanagermcp-activity",
            retention=logs.RetentionDays.ONE_WEEK,  # 1週間保持
            removal_policy=RemovalPolicy.DESTROY,  # スタック削除時に削除
        )

        # ActivityLambda関数
        self.activity_lambda = lambda_.Function(
            self,
            "ActivityLambda",
            function_name="healthmanagermcp-activity",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="activity.handler.lambda_handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "ACTIVITIES_TABLE_NAME": self.activities_table.table_name,
            },
            log_group=activity_log_group,  # ロググループを明示的に指定
        )

        # ActivityLambdaにDynamoDBテーブルへのアクセス権限を付与
        self.activities_table.grant_read_write_data(self.activity_lambda)



        # ========================================
        # Bedrock AgentCore Gateway
        # ========================================
        
        # AgentCore Gateway用のIAMロール
        gateway_role = iam.Role(
            self,
            "AgentCoreGatewayRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {
                        "aws:SourceAccount": self.account
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/healthmate-gateway-*"
                    }
                }
            ),
            description="IAM role for AgentCore Gateway to invoke Lambda functions",
        )
        
        # Lambda関数の呼び出し権限を付与
        gateway_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[
                    self.user_lambda.function_arn,
                    self.health_goal_lambda.function_arn,
                    self.health_policy_lambda.function_arn,
                    self.activity_lambda.function_arn,
                ],
            )
        )
        
        # Gateway自身へのアクセス権限を付与
        gateway_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock-agentcore:GetGateway"],
                resources=[
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/healthmate-gateway-*"
                ],
            )
        )
        
        # Cognito User PoolのDiscovery URL（OIDC設定）
        discovery_url = f"https://cognito-idp.{self.region}.amazonaws.com/{self.gateway_user_pool.user_pool_id}/.well-known/openid-configuration"
        
        # AgentCore Gateway（L1コンストラクト使用）
        self.agentcore_gateway = bedrockagentcore.CfnGateway(
            self,
            "AgentCoreGateway",
            name="healthmate-gateway",
            description="HealthManagerMCP Gateway for Healthmate ecosystem integration",
            protocol_type="MCP",
            role_arn=gateway_role.role_arn,
            authorizer_type="CUSTOM_JWT",
            authorizer_configuration=bedrockagentcore.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=bedrockagentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=discovery_url,
                    allowed_clients=[self.gateway_app_client.user_pool_client_id]
                )
            )
        )
        
        # ========================================
        # Gateway Targets作成
        # ========================================
        
        # MCPスキーマファイルのパス
        mcp_schema_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mcp-schema"
        )
        
        # MCPスキーマファイルを読み込む関数
        def load_mcp_schema(schema_file_name: str) -> dict:
            schema_file_path = os.path.join(mcp_schema_path, schema_file_name)
            with open(schema_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # UserManagement Target
        user_mcp_schema = load_mcp_schema("user-management-mcp-schema.json")
        
        self.user_target = bedrockagentcore.CfnGatewayTarget(
            self,
            "UserManagementTarget",
            gateway_identifier=self.agentcore_gateway.ref,
            name="UserManagement",
            description="ユーザー情報を管理する",
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=self.user_lambda.function_arn,
                        tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=user_mcp_schema
                        )
                    )
                )
            )
        )
        
        # HealthGoalManagement Target
        health_goal_mcp_schema = load_mcp_schema("health-goal-management-mcp-schema.json")
        
        self.health_goal_target = bedrockagentcore.CfnGatewayTarget(
            self,
            "HealthGoalManagementTarget",
            gateway_identifier=self.agentcore_gateway.ref,
            name="HealthGoalManagement",
            description="ユーザーの健康目標（長期的な理想状態）を管理する",
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=self.health_goal_lambda.function_arn,
                        tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=health_goal_mcp_schema
                        )
                    )
                )
            )
        )
        
        # HealthPolicyManagement Target
        health_policy_mcp_schema = load_mcp_schema("health-policy-management-mcp-schema.json")
        
        self.health_policy_target = bedrockagentcore.CfnGatewayTarget(
            self,
            "HealthPolicyManagementTarget",
            gateway_identifier=self.agentcore_gateway.ref,
            name="HealthPolicyManagement",
            description="ユーザーの健康ポリシー（具体的な行動ルール）を管理する",
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=self.health_policy_lambda.function_arn,
                        tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=health_policy_mcp_schema
                        )
                    )
                )
            )
        )
        
        # ActivityManagement Target
        activity_mcp_schema = load_mcp_schema("activity-management-mcp-schema.json")
        
        self.activity_target = bedrockagentcore.CfnGatewayTarget(
            self,
            "ActivityManagementTarget",
            gateway_identifier=self.agentcore_gateway.ref,
            name="ActivityManagement",
            description="ユーザーの日々の健康活動を記録・取得する",
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=self.activity_lambda.function_arn,
                        tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=activity_mcp_schema
                        )
                    )
                )
            )
        )

        # ========================================
        # Lambda Permissions
        # ========================================
        
        # Lambda関数にAgentCore Gatewayからの呼び出し権限を付与
        # L1コンストラクトでは自動設定されないため手動で設定
        self.user_lambda.add_permission(
            "AllowAgentCoreGatewayInvoke",
            principal=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            action="lambda:InvokeFunction",
        )

        self.health_goal_lambda.add_permission(
            "AllowAgentCoreGatewayInvoke",
            principal=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            action="lambda:InvokeFunction",
        )

        self.health_policy_lambda.add_permission(
            "AllowAgentCoreGatewayInvoke",
            principal=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            action="lambda:InvokeFunction",
        )

        self.activity_lambda.add_permission(
            "AllowAgentCoreGatewayInvoke",
            principal=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            action="lambda:InvokeFunction",
        )

        # ========================================
        # CloudFormation Outputs
        # ========================================

        # 高優先度（必須）
        CfnOutput(
            self,
            "UserPoolId",
            value=self.gateway_user_pool.user_pool_id,
            description="M2M Cognito User Pool ID",
            export_name="Healthmate-HealthManager-UserPoolId"
        )

        CfnOutput(
            self,
            "UserPoolClientId", 
            value=self.gateway_app_client.user_pool_client_id,
            description="M2M Cognito User Pool Client ID",
            export_name="Healthmate-HealthManager-UserPoolClientId"
        )

        # Secrets Manager ARN（AgentCore Identity用）
        CfnOutput(
            self,
            "IdentitySecretArn",
            value=self.client_secret.secret_full_arn,
            description="Secrets Manager ARN for AgentCore Identity client secret access",
            export_name="Healthmate-HealthManager-IdentitySecretArn"
        )

        # M2M認証では直接トークンエンドポイントを使用
        CfnOutput(
            self,
            "TokenUrl",
            value=f"https://cognito-idp.{self.region}.amazonaws.com/",
            description="Cognito Identity Provider Base URL for M2M Token Exchange",
            export_name="Healthmate-HealthManager-TokenUrl"
        )

        CfnOutput(
            self,
            "GatewayEndpoint",
            value=f"https://{self.agentcore_gateway.ref}.agentcore.{self.region}.amazonaws.com",
            description="AgentCore Gateway Endpoint",
            export_name="Healthmate-HealthManager-GatewayEndpoint"
        )

        CfnOutput(
            self,
            "GatewayId",
            value=self.agentcore_gateway.ref,
            description="AgentCore Gateway ID",
            export_name="Healthmate-HealthManager-GatewayId"
        )

        # Lambda関数ARN
        CfnOutput(
            self,
            "UserLambdaArn",
            value=self.user_lambda.function_arn,
            description="User Lambda Function ARN",
            export_name="Healthmate-HealthManager-UserLambdaArn"
        )

        CfnOutput(
            self,
            "HealthGoalLambdaArn",
            value=self.health_goal_lambda.function_arn,
            description="Health Goal Lambda Function ARN",
            export_name="Healthmate-HealthManager-HealthGoalLambdaArn"
        )

        CfnOutput(
            self,
            "HealthPolicyLambdaArn",
            value=self.health_policy_lambda.function_arn,
            description="Health Policy Lambda Function ARN",
            export_name="Healthmate-HealthManager-HealthPolicyLambdaArn"
        )

        CfnOutput(
            self,
            "ActivityLambdaArn",
            value=self.activity_lambda.function_arn,
            description="Activity Lambda Function ARN",
            export_name="Healthmate-HealthManager-ActivityLambdaArn"
        )

        # DynamoDBテーブル名
        CfnOutput(
            self,
            "UsersTableName",
            value=self.users_table.table_name,
            description="Users DynamoDB Table Name",
            export_name="Healthmate-HealthManager-UsersTableName"
        )

        CfnOutput(
            self,
            "GoalsTableName",
            value=self.goals_table.table_name,
            description="Goals DynamoDB Table Name",
            export_name="Healthmate-HealthManager-GoalsTableName"
        )

        CfnOutput(
            self,
            "PoliciesTableName",
            value=self.policies_table.table_name,
            description="Policies DynamoDB Table Name",
            export_name="Healthmate-HealthManager-PoliciesTableName"
        )

        CfnOutput(
            self,
            "ActivitiesTableName",
            value=self.activities_table.table_name,
            description="Activities DynamoDB Table Name",
            export_name="Healthmate-HealthManager-ActivitiesTableName"
        )

        # M2M認証用のJWKS URL
        CfnOutput(
            self,
            "JwksUrl",
            value=f"https://cognito-idp.{self.region}.amazonaws.com/{self.gateway_user_pool.user_pool_id}/.well-known/jwks.json",
            description="JWKS URL for M2M JWT token verification",
            export_name="Healthmate-HealthManager-JwksUrl"
        )

        CfnOutput(
            self,
            "DiscoveryUrl",
            value=discovery_url,
            description="OIDC Discovery URL",
            export_name="Healthmate-HealthManager-DiscoveryUrl"
        )

        # カスタムOAuthスコープ
        CfnOutput(
            self,
            "CustomScope",
            value="HealthManager/HealthTarget:invoke",
            description="Custom OAuth scope for AgentCore Gateway M2M authentication",
            export_name="Healthmate-HealthManager-CustomScope"
        )

        # M2M認証用のMCP接続設定（JSON形式）
        mcp_connection_config = {
            "gatewayEndpoint": f"https://{self.agentcore_gateway.ref}.agentcore.{self.region}.amazonaws.com",
            "authConfig": {
                "type": "m2m",
                "userPoolId": self.gateway_user_pool.user_pool_id,
                "clientId": self.gateway_app_client.user_pool_client_id,
                "identitySecretArn": self.client_secret.secret_full_arn,
                "discoveryUrl": discovery_url,
                "jwksUrl": f"https://cognito-idp.{self.region}.amazonaws.com/{self.gateway_user_pool.user_pool_id}/.well-known/jwks.json",
                "customScope": "HealthManager/HealthTarget:invoke"
            },
            "tools": {
                "userManagement": "UserManagement",
                "healthGoalManagement": "HealthGoalManagement",
                "healthPolicyManagement": "HealthPolicyManagement", 
                "activityManagement": "ActivityManagement"
            },
            "region": self.region,
            "accountId": self.account
        }

        CfnOutput(
            self,
            "MCPConnectionConfig",
            value=json.dumps(mcp_connection_config, indent=2),
            description="M2M MCP connection configuration (JSON)",
            export_name="Healthmate-HealthManager-MCPConnectionConfig"
        )
