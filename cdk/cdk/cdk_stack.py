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

# 環境設定モジュールをインポート
from .environment import EnvironmentManager, ConfigurationProvider, LogController


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

        # 環境設定の初期化
        self.config_provider = ConfigurationProvider("healthmate-healthmanager")
        self.current_environment = EnvironmentManager.get_environment()
        
        # ログ設定の初期化
        self.log_controller = LogController("healthmate-healthmanager")
        logger = self.log_controller.get_logger(__name__)
        logger.info(f"Initializing HealthManager stack for environment: {self.current_environment}")

        # ========================================
        # DynamoDBテーブル
        # ========================================

        # ユーザーテーブル
        self.users_table = dynamodb.Table(
            self,
            "UsersTable",
            table_name=f"healthmate-users{self.config_provider.get_environment_suffix()}",
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
            table_name=f"healthmate-goals{self.config_provider.get_environment_suffix()}",
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
            table_name=f"healthmate-policies{self.config_provider.get_environment_suffix()}",
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
            table_name=f"healthmate-activities{self.config_provider.get_environment_suffix()}",
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
            user_pool_name=f"HealthManagerM2MUserPool{self.config_provider.get_environment_suffix()}",
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

        # Cognito User Pool Domain（OAuth2 Token URL用）
        self.gateway_user_pool_domain = self.gateway_user_pool.add_domain(
            "HealthManagerM2MUserPoolDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"healthmanager-m2m-auth{self.config_provider.get_environment_suffix()}",
            )
        )

        # AgentCore用のResource Serverとカスタムスコープを定義
        health_target_scope = cognito.ResourceServerScope(
            scope_name="HealthTarget:invoke",
            scope_description="Permission to invoke HealthTarget operations via MCP Gateway"
        )
        
        self.gateway_resource_server = self.gateway_user_pool.add_resource_server(
            "HealthManagerResourceServer",
            identifier="HealthManager",
            user_pool_resource_server_name="HealthManager MCP Resource Server",
            scopes=[health_target_scope]
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
                    client_credentials=True  # Client Credentials Flowを有効化
                ),
                scopes=[
                    # カスタムスコープ：HealthManager/HealthTarget:invoke
                    cognito.OAuthScope.resource_server(
                        self.gateway_resource_server, 
                        health_target_scope
                    )
                ]
            ),
            # 認証フロー（M2M用に最小限に設定）
            auth_flows=cognito.AuthFlow(
                # M2M認証では通常のユーザー認証フローは無効化
                user_password=False,
                user_srp=False,
                custom=False,
                admin_user_password=False,  # M2M認証では不要
            ),
            # トークン有効期限（M2M用に調整）
            access_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            id_token_validity=Duration.hours(1),
        )

        # CloudFormationレベルでの追加設定は不要（OAuth設定で十分）

        # ========================================
        # AgentCore Identity (Workload Identity)
        # ========================================

        # AgentCore Identity (Workload Identity) の生成
        # RuntimeのエージェントがGatewayを呼び出す際の認証情報を定義
        self.workload_identity = bedrockagentcore.CfnWorkloadIdentity(
            self,
            "HealthManagerWorkloadIdentity",
            # Workload Identity名（エージェントコードで指定する名称）
            name=f"healthmanager-agentcore-identity{self.config_provider.get_environment_suffix()}"
        )

        # 注意: OAuth2 Credential Providerは、AgentCore Identity APIを使用して
        # シェルスクリプトで作成します。CDKでは直接作成できません。



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
            log_group_name=f"/aws/lambda/healthmanagermcp-user{self.config_provider.get_environment_suffix()}",
            retention=logs.RetentionDays.ONE_WEEK,  # 1週間保持
            removal_policy=RemovalPolicy.DESTROY,  # スタック削除時に削除
        )

        # UserLambda関数
        self.user_lambda = lambda_.Function(
            self,
            "UserLambda",
            function_name=f"healthmanagermcp-user{self.config_provider.get_environment_suffix()}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="user.handler.lambda_handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "USERS_TABLE_NAME": self.users_table.table_name,
                "HEALTHMATE_ENV": self.current_environment,
                "LOG_LEVEL": self.log_controller.get_log_level(),
            },
            log_group=user_log_group,  # ロググループを明示的に指定
        )

        # UserLambdaにDynamoDBテーブルへのアクセス権限を付与
        self.users_table.grant_read_write_data(self.user_lambda)

        # HealthGoalLambda用のCloudWatch Logsロググループ
        health_goal_log_group = logs.LogGroup(
            self,
            "HealthGoalLambdaLogGroup",
            log_group_name=f"/aws/lambda/healthmanagermcp-health-goal{self.config_provider.get_environment_suffix()}",
            retention=logs.RetentionDays.ONE_WEEK,  # 1週間保持
            removal_policy=RemovalPolicy.DESTROY,  # スタック削除時に削除
        )

        # HealthGoalLambda関数
        self.health_goal_lambda = lambda_.Function(
            self,
            "HealthGoalLambda",
            function_name=f"healthmanagermcp-health-goal{self.config_provider.get_environment_suffix()}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="health_goal.handler.lambda_handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "GOALS_TABLE_NAME": self.goals_table.table_name,
                "HEALTHMATE_ENV": self.current_environment,
                "LOG_LEVEL": self.log_controller.get_log_level(),
            },
            log_group=health_goal_log_group,  # ロググループを明示的に指定
        )

        # HealthGoalLambdaにDynamoDBテーブルへのアクセス権限を付与
        self.goals_table.grant_read_write_data(self.health_goal_lambda)

        # HealthPolicyLambda用のCloudWatch Logsロググループ
        health_policy_log_group = logs.LogGroup(
            self,
            "HealthPolicyLambdaLogGroup",
            log_group_name=f"/aws/lambda/healthmanagermcp-health-policy{self.config_provider.get_environment_suffix()}",
            retention=logs.RetentionDays.ONE_WEEK,  # 1週間保持
            removal_policy=RemovalPolicy.DESTROY,  # スタック削除時に削除
        )

        # HealthPolicyLambda関数
        self.health_policy_lambda = lambda_.Function(
            self,
            "HealthPolicyLambda",
            function_name=f"healthmanagermcp-health-policy{self.config_provider.get_environment_suffix()}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="health_policy.handler.lambda_handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "POLICIES_TABLE_NAME": self.policies_table.table_name,
                "HEALTHMATE_ENV": self.current_environment,
                "LOG_LEVEL": self.log_controller.get_log_level(),
            },
            log_group=health_policy_log_group,  # ロググループを明示的に指定
        )

        # HealthPolicyLambdaにDynamoDBテーブルへのアクセス権限を付与
        self.policies_table.grant_read_write_data(self.health_policy_lambda)

        # ActivityLambda用のCloudWatch Logsロググループ
        activity_log_group = logs.LogGroup(
            self,
            "ActivityLambdaLogGroup",
            log_group_name=f"/aws/lambda/healthmanagermcp-activity{self.config_provider.get_environment_suffix()}",
            retention=logs.RetentionDays.ONE_WEEK,  # 1週間保持
            removal_policy=RemovalPolicy.DESTROY,  # スタック削除時に削除
        )

        # ActivityLambda関数
        self.activity_lambda = lambda_.Function(
            self,
            "ActivityLambda",
            function_name=f"healthmanagermcp-activity{self.config_provider.get_environment_suffix()}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="activity.handler.lambda_handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "ACTIVITIES_TABLE_NAME": self.activities_table.table_name,
                "HEALTHMATE_ENV": self.current_environment,
                "LOG_LEVEL": self.log_controller.get_log_level(),
            },
            log_group=activity_log_group,  # ロググループを明示的に指定
        )

        # ActivityLambdaにDynamoDBテーブルへのアクセス権限を付与
        self.activities_table.grant_read_write_data(self.activity_lambda)

        # 身体測定テーブル
        self.body_measurements_table = dynamodb.Table(
            self,
            "BodyMeasurementsTable",
            table_name=f"healthmate-body-measurements{self.config_provider.get_environment_suffix()}",
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="measurementId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # 開発用：本番環境ではRETAINに変更
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
        )

        # LSI: RecordTypeIndex (Latest/Oldest レコード用)
        self.body_measurements_table.add_local_secondary_index(
            index_name="RecordTypeIndex",
            sort_key=dynamodb.Attribute(
                name="record_type", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # 健康悩みテーブル
        self.concerns_table = dynamodb.Table(
            self,
            "ConcernsTable",
            table_name=f"healthmate-concerns{self.config_provider.get_environment_suffix()}",
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="concernId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # 開発用：本番環境ではRETAINに変更
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
        )

        # GSI: status-index
        self.concerns_table.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(
                name="status", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="createdAt", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # 日記管理テーブル
        self.journals_table = dynamodb.Table(
            self,
            "JournalsTable",
            table_name=f"healthmate-journals{self.config_provider.get_environment_suffix()}",
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

        # BodyMeasurementLambda用のCloudWatch Logsロググループ
        body_measurement_log_group = logs.LogGroup(
            self,
            "BodyMeasurementLambdaLogGroup",
            log_group_name=f"/aws/lambda/healthmanagermcp-body-measurement{self.config_provider.get_environment_suffix()}",
            retention=logs.RetentionDays.ONE_WEEK,  # 1週間保持
            removal_policy=RemovalPolicy.DESTROY,  # スタック削除時に削除
        )

        # BodyMeasurementLambda関数
        self.body_measurement_lambda = lambda_.Function(
            self,
            "BodyMeasurementLambda",
            function_name=f"healthmanagermcp-body-measurement{self.config_provider.get_environment_suffix()}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="body_measurement.handler.lambda_handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "BODY_MEASUREMENTS_TABLE_NAME": self.body_measurements_table.table_name,
                "HEALTHMATE_ENV": self.current_environment,
                "LOG_LEVEL": self.log_controller.get_log_level(),
            },
            log_group=body_measurement_log_group,  # ロググループを明示的に指定
        )

        # BodyMeasurementLambdaにDynamoDBテーブルへのアクセス権限を付与
        self.body_measurements_table.grant_read_write_data(self.body_measurement_lambda)

        # HealthConcernLambda用のCloudWatch Logsロググループ
        health_concern_log_group = logs.LogGroup(
            self,
            "HealthConcernLambdaLogGroup",
            log_group_name=f"/aws/lambda/healthmanagermcp-health-concern{self.config_provider.get_environment_suffix()}",
            retention=logs.RetentionDays.ONE_WEEK,  # 1週間保持
            removal_policy=RemovalPolicy.DESTROY,  # スタック削除時に削除
        )

        # HealthConcernLambda関数
        self.health_concern_lambda = lambda_.Function(
            self,
            "HealthConcernLambda",
            function_name=f"healthmanagermcp-health-concern{self.config_provider.get_environment_suffix()}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="health_concern.handler.lambda_handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "CONCERNS_TABLE_NAME": self.concerns_table.table_name,
                "HEALTHMATE_ENV": self.current_environment,
                "LOG_LEVEL": self.log_controller.get_log_level(),
            },
            log_group=health_concern_log_group,  # ロググループを明示的に指定
        )

        # HealthConcernLambdaにDynamoDBテーブルへのアクセス権限を付与
        self.concerns_table.grant_read_write_data(self.health_concern_lambda)

        # JournalLambda用のCloudWatch Logsロググループ
        journal_log_group = logs.LogGroup(
            self,
            "JournalLambdaLogGroup",
            log_group_name=f"/aws/lambda/healthmanagermcp-journal{self.config_provider.get_environment_suffix()}",
            retention=logs.RetentionDays.ONE_WEEK,  # 1週間保持
            removal_policy=RemovalPolicy.DESTROY,  # スタック削除時に削除
        )

        # JournalLambda関数
        self.journal_lambda = lambda_.Function(
            self,
            "JournalLambda",
            function_name=f"healthmanagermcp-journal{self.config_provider.get_environment_suffix()}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="journal.handler.lambda_handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "JOURNALS_TABLE_NAME": self.journals_table.table_name,
                "HEALTHMATE_ENV": self.current_environment,
                "LOG_LEVEL": self.log_controller.get_log_level(),
            },
            log_group=journal_log_group,  # ロググループを明示的に指定
        )

        # JournalLambdaにDynamoDBテーブルへのアクセス権限を付与
        self.journals_table.grant_read_write_data(self.journal_lambda)



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
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/healthmate-gateway{self.config_provider.get_environment_suffix()}-*"
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
                    self.body_measurement_lambda.function_arn,
                    self.health_concern_lambda.function_arn,
                    self.journal_lambda.function_arn,
                ],
            )
        )
        
        # Gateway自身へのアクセス権限を付与
        gateway_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock-agentcore:GetGateway"],
                resources=[
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/healthmate-gateway{self.config_provider.get_environment_suffix()}-*"
                ],
            )
        )
        
        # Cognito User PoolのDiscovery URL（OIDC設定）
        discovery_url = f"https://cognito-idp.{self.region}.amazonaws.com/{self.gateway_user_pool.user_pool_id}/.well-known/openid-configuration"
        
        # AgentCore Gateway（L1コンストラクト使用）
        self.agentcore_gateway = bedrockagentcore.CfnGateway(
            self,
            "AgentCoreGateway",
            name=f"healthmate-gateway{self.config_provider.get_environment_suffix()}",
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

        # BodyMeasurementManagement Target
        body_measurement_mcp_schema = load_mcp_schema("body-measurement-mcp-schema.json")
        
        self.body_measurement_target = bedrockagentcore.CfnGatewayTarget(
            self,
            "BodyMeasurementManagementTarget",
            gateway_identifier=self.agentcore_gateway.ref,
            name="BodyMeasurementManagement",
            description="ユーザーの身体測定値（体重、身長、体脂肪率）を記録・管理する",
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=self.body_measurement_lambda.function_arn,
                        tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=body_measurement_mcp_schema
                        )
                    )
                )
            )
        )

        # HealthConcernManagement Target
        health_concern_mcp_schema = load_mcp_schema("health-concern-management-mcp-schema.json")
        
        self.health_concern_target = bedrockagentcore.CfnGatewayTarget(
            self,
            "HealthConcernManagementTarget",
            gateway_identifier=self.agentcore_gateway.ref,
            name="HealthConcernManagement",
            description="ユーザーの健康上の悩み（身体面・メンタル面）を管理する",
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=self.health_concern_lambda.function_arn,
                        tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=health_concern_mcp_schema
                        )
                    )
                )
            )
        )

        # JournalManagement Target
        journal_mcp_schema = load_mcp_schema("journal-management-mcp-schema.json")
        
        self.journal_target = bedrockagentcore.CfnGatewayTarget(
            self,
            "JournalManagementTarget",
            gateway_identifier=self.agentcore_gateway.ref,
            name="JournalManagement",
            description="ユーザーの日記（毎日の振り返り）を管理する",
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=self.journal_lambda.function_arn,
                        tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=journal_mcp_schema
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

        self.body_measurement_lambda.add_permission(
            "AllowAgentCoreGatewayInvoke",
            principal=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            action="lambda:InvokeFunction",
        )

        self.health_concern_lambda.add_permission(
            "AllowAgentCoreGatewayInvoke",
            principal=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            action="lambda:InvokeFunction",
        )

        self.journal_lambda.add_permission(
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
            export_name=f"Healthmate-HealthManager-UserPoolId{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "UserPoolClientId", 
            value=self.gateway_app_client.user_pool_client_id,
            description="M2M Cognito User Pool Client ID",
            export_name=f"Healthmate-HealthManager-UserPoolClientId{self.config_provider.get_environment_suffix()}"
        )

        # AgentCore Identity名（Runtime環境変数用）
        CfnOutput(
            self,
            "WorkloadIdentityName",
            value=self.workload_identity.name,
            description="AgentCore Workload Identity name for Runtime agent authentication",
            export_name=f"Healthmate-HealthManager-WorkloadIdentityName{self.config_provider.get_environment_suffix()}"
        )

        # Workload Identity ARN（参照用）
        CfnOutput(
            self,
            "WorkloadIdentityArn",
            value=self.workload_identity.attr_workload_identity_arn,
            description="AgentCore Workload Identity ARN",
            export_name=f"Healthmate-HealthManager-WorkloadIdentityArn{self.config_provider.get_environment_suffix()}"
        )

        # Cognito Domain（Token URL用）
        CfnOutput(
            self,
            "CognitoDomain",
            value=self.gateway_user_pool_domain.domain_name,
            description="Cognito User Pool Domain for OAuth2 token endpoint",
            export_name=f"Healthmate-HealthManager-CognitoDomain{self.config_provider.get_environment_suffix()}"
        )

        # OAuth2 Token URL（Credential Provider作成用）
        CfnOutput(
            self,
            "OAuth2TokenUrl",
            value=f"https://{self.gateway_user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com/oauth2/token",
            description="OAuth2 Token URL for Credential Provider configuration",
            export_name=f"Healthmate-HealthManager-OAuth2TokenUrl{self.config_provider.get_environment_suffix()}"
        )

        # M2M認証では直接トークンエンドポイントを使用
        CfnOutput(
            self,
            "TokenUrl",
            value=f"https://cognito-idp.{self.region}.amazonaws.com/",
            description="Cognito Identity Provider Base URL for M2M Token Exchange",
            export_name=f"Healthmate-HealthManager-TokenUrl{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "GatewayEndpoint",
            value=f"https://{self.agentcore_gateway.ref}.gateway.bedrock-agentcore.{self.region}.amazonaws.com/mcp",
            description="AgentCore Gateway MCP Endpoint",
            export_name=f"Healthmate-HealthManager-GatewayEndpoint{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "GatewayId",
            value=self.agentcore_gateway.ref,
            description="AgentCore Gateway ID",
            export_name=f"Healthmate-HealthManager-GatewayId{self.config_provider.get_environment_suffix()}"
        )

        # Lambda関数ARN
        CfnOutput(
            self,
            "UserLambdaArn",
            value=self.user_lambda.function_arn,
            description="User Lambda Function ARN",
            export_name=f"Healthmate-HealthManager-UserLambdaArn{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "HealthGoalLambdaArn",
            value=self.health_goal_lambda.function_arn,
            description="Health Goal Lambda Function ARN",
            export_name=f"Healthmate-HealthManager-HealthGoalLambdaArn{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "HealthPolicyLambdaArn",
            value=self.health_policy_lambda.function_arn,
            description="Health Policy Lambda Function ARN",
            export_name=f"Healthmate-HealthManager-HealthPolicyLambdaArn{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "ActivityLambdaArn",
            value=self.activity_lambda.function_arn,
            description="Activity Lambda Function ARN",
            export_name=f"Healthmate-HealthManager-ActivityLambdaArn{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "BodyMeasurementLambdaArn",
            value=self.body_measurement_lambda.function_arn,
            description="Body Measurement Lambda Function ARN",
            export_name=f"Healthmate-HealthManager-BodyMeasurementLambdaArn{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "HealthConcernLambdaArn",
            value=self.health_concern_lambda.function_arn,
            description="Health Concern Lambda Function ARN",
            export_name=f"Healthmate-HealthManager-HealthConcernLambdaArn{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "JournalLambdaArn",
            value=self.journal_lambda.function_arn,
            description="Journal Lambda Function ARN",
            export_name=f"Healthmate-HealthManager-JournalLambdaArn{self.config_provider.get_environment_suffix()}"
        )

        # DynamoDBテーブル名
        CfnOutput(
            self,
            "UsersTableName",
            value=self.users_table.table_name,
            description="Users DynamoDB Table Name",
            export_name=f"Healthmate-HealthManager-UsersTableName{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "GoalsTableName",
            value=self.goals_table.table_name,
            description="Goals DynamoDB Table Name",
            export_name=f"Healthmate-HealthManager-GoalsTableName{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "PoliciesTableName",
            value=self.policies_table.table_name,
            description="Policies DynamoDB Table Name",
            export_name=f"Healthmate-HealthManager-PoliciesTableName{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "ActivitiesTableName",
            value=self.activities_table.table_name,
            description="Activities DynamoDB Table Name",
            export_name=f"Healthmate-HealthManager-ActivitiesTableName{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "BodyMeasurementsTableName",
            value=self.body_measurements_table.table_name,
            description="Body Measurements DynamoDB Table Name",
            export_name=f"Healthmate-HealthManager-BodyMeasurementsTableName{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "ConcernsTableName",
            value=self.concerns_table.table_name,
            description="Concerns DynamoDB Table Name",
            export_name=f"Healthmate-HealthManager-ConcernsTableName{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "JournalsTableName",
            value=self.journals_table.table_name,
            description="Journals DynamoDB Table Name",
            export_name=f"Healthmate-HealthManager-JournalsTableName{self.config_provider.get_environment_suffix()}"
        )

        # M2M認証用のJWKS URL
        CfnOutput(
            self,
            "JwksUrl",
            value=f"https://cognito-idp.{self.region}.amazonaws.com/{self.gateway_user_pool.user_pool_id}/.well-known/jwks.json",
            description="JWKS URL for M2M JWT token verification",
            export_name=f"Healthmate-HealthManager-JwksUrl{self.config_provider.get_environment_suffix()}"
        )

        CfnOutput(
            self,
            "DiscoveryUrl",
            value=discovery_url,
            description="OIDC Discovery URL",
            export_name=f"Healthmate-HealthManager-DiscoveryUrl{self.config_provider.get_environment_suffix()}"
        )

        # カスタムOAuthスコープ
        CfnOutput(
            self,
            "CustomScope",
            value="HealthManager/HealthTarget:invoke",
            description="Custom OAuth scope for AgentCore Gateway M2M authentication",
            export_name=f"Healthmate-HealthManager-CustomScope{self.config_provider.get_environment_suffix()}"
        )
