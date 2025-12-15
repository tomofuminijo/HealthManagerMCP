from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    CfnResource,
    CfnOutput,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_bedrock as bedrock,
    aws_logs as logs,
    aws_cognito as cognito,
)
from constructs import Construct
import os
import json


class HealthManagerMCPStack(Stack):
    """
    Main CDK Stack for HealthManagerMCP Application

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
        # Cognito User Pool（OAuth 2.0 IdP）
        # ========================================

        # Cognito User Pool
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="healthmate-users",
            # サインイン設定
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=True,
            ),
            # セルフサインアップを有効化
            self_sign_up_enabled=True,
            # ユーザー検証設定
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            # パスワードポリシー
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            # アカウント復旧設定
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # 削除保護（開発用：本番環境ではTrueに変更）
            removal_policy=RemovalPolicy.DESTROY,
        )

        # App Client（HealthCoachAI用）
        self.user_pool_client = self.user_pool.add_client(
            "HealthCoachAIClient",
            user_pool_client_name="healthmate-healthcoachai-client",
            # OAuth 2.0設定
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                ),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PHONE,  # 電話番号スコープ
                ],
                # コールバックURL（HealthCoachAI、HealthmateUI、外部AIクライアント用）
                # 実際のURLは後で更新する必要があります
                callback_urls=[
                    "https://healthcoachai.example.com/oauth/callback",  # HealthCoachAI
                    "https://healthmateui.example.com/oauth/callback",   # HealthmateUI
                    "https://chatgpt.com/connector_platform_oauth_redirect",  # ChatGPT
                    "http://localhost:8000/auth/callback"
                ],
                logout_urls=[
                    "https://healthcoachai.example.com/oauth/logout",
                    "https://healthmateui.example.com/oauth/logout",
                    "https://chatgpt.com/connector_platform_oauth_redirect",
                    "http://localhost:8000/auth/logout"
                ],
            ),
            # トークン有効期限
            access_token_validity=Duration.hours(1),  # アクセストークン: 1時間
            refresh_token_validity=Duration.days(30),  # リフレッシュトークン: 30日
            id_token_validity=Duration.hours(1),  # IDトークン: 1時間
            # クライアントシークレットを生成（AIクライアント連携用）
            generate_secret=True,
            # 認証フロー
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                custom=True,  # ALLOW_CUSTOM_AUTH
            ),
            # 追加の認証フローは、CfnUserPoolClientで設定が必要な場合があります
            # ALLOW_USER_AUTHは比較的新しい認証フローのため、
            # CDKの高レベルAPIでサポートされていない可能性があります
        )

        # ALLOW_USER_AUTH認証フローを追加（CloudFormationレベルで設定）
        cfn_user_pool_client = self.user_pool_client.node.default_child
        cfn_user_pool_client.add_property_override(
            "ExplicitAuthFlows",
            [
                "ALLOW_USER_PASSWORD_AUTH",
                "ALLOW_USER_SRP_AUTH",
                "ALLOW_CUSTOM_AUTH",
                "ALLOW_USER_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
                "ALLOW_ADMIN_USER_PASSWORD_AUTH",  # テスト用のAdmin認証フローを追加
            ]
        )

        # User Pool Domain（ホストされたUIのドメイン）
        self.user_pool_domain = self.user_pool.add_domain(
            "UserPoolDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix="healthmate",  # ユニークなプレフィックスが必要
            ),
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
        discovery_url = f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool.user_pool_id}/.well-known/openid-configuration"
        
        # AgentCore Gateway
        # NOTE: Gateway TargetsはCDKでサポートされていないため、CLIで設定する
        self.agentcore_gateway = CfnResource(
            self,
            "AgentCoreGateway",
            type="AWS::BedrockAgentCore::Gateway",
            properties={
                "Name": "healthmate-gateway",
                "Description": "HealthManagerMCP Gateway for Healthmate ecosystem integration",
                "ProtocolType": "MCP",
                "RoleArn": gateway_role.role_arn,
                "AuthorizerType": "CUSTOM_JWT",
                "AuthorizerConfiguration": {
                    "CustomJWTAuthorizer": {
                        "DiscoveryUrl": discovery_url,
                        "AllowedClients": [
                            self.user_pool_client.user_pool_client_id
                        ],
                    }
                },
            },
        )
        
        # Gateway Targetの作成
        # NOTE: Gateway TargetはCloudFormationでの作成が複雑なため、
        # CDKデプロイ後にcreate-gateway-targets.shスクリプトで作成する

        # ========================================
        # Lambda Permissions
        # ========================================
        
        # Lambda関数にAgentCore Gatewayからの呼び出し権限を付与
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
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID",
            export_name="HealthManagerMCP-UserPoolId"
        )

        CfnOutput(
            self,
            "UserPoolClientId", 
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
            export_name="HealthManagerMCP-UserPoolClientId"
        )

        CfnOutput(
            self,
            "AuthorizationUrl",
            value=f"https://{self.user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com/oauth2/authorize",
            description="OAuth 2.0 Authorization URL",
            export_name="HealthManagerMCP-AuthorizationUrl"
        )

        CfnOutput(
            self,
            "TokenUrl",
            value=f"https://{self.user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com/oauth2/token",
            description="OAuth 2.0 Token URL", 
            export_name="HealthManagerMCP-TokenUrl"
        )

        CfnOutput(
            self,
            "GatewayEndpoint",
            value=f"https://{self.agentcore_gateway.ref}.agentcore.{self.region}.amazonaws.com",
            description="AgentCore Gateway Endpoint",
            export_name="HealthManagerMCP-GatewayEndpoint"
        )

        CfnOutput(
            self,
            "Region",
            value=self.region,
            description="AWS Region",
            export_name="HealthManagerMCP-Region"
        )

        CfnOutput(
            self,
            "AccountId",
            value=self.account,
            description="AWS Account ID",
            export_name="HealthManagerMCP-AccountId"
        )

        # 中優先度（推奨）

        CfnOutput(
            self,
            "GatewayName",
            value="healthmate-gateway",
            description="AgentCore Gateway Name",
            export_name="HealthManagerMCP-GatewayName"
        )

        CfnOutput(
            self,
            "GatewayId",
            value=self.agentcore_gateway.ref,
            description="AgentCore Gateway ID",
            export_name="HealthManagerMCP-GatewayId"
        )

        # Lambda関数ARN
        CfnOutput(
            self,
            "UserLambdaArn",
            value=self.user_lambda.function_arn,
            description="User Lambda Function ARN",
            export_name="HealthManagerMCP-UserLambdaArn"
        )

        CfnOutput(
            self,
            "HealthGoalLambdaArn",
            value=self.health_goal_lambda.function_arn,
            description="Health Goal Lambda Function ARN",
            export_name="HealthManagerMCP-HealthGoalLambdaArn"
        )

        CfnOutput(
            self,
            "HealthPolicyLambdaArn",
            value=self.health_policy_lambda.function_arn,
            description="Health Policy Lambda Function ARN",
            export_name="HealthManagerMCP-HealthPolicyLambdaArn"
        )

        CfnOutput(
            self,
            "ActivityLambdaArn",
            value=self.activity_lambda.function_arn,
            description="Activity Lambda Function ARN",
            export_name="HealthManagerMCP-ActivityLambdaArn"
        )

        # DynamoDBテーブル名
        CfnOutput(
            self,
            "UsersTableName",
            value=self.users_table.table_name,
            description="Users DynamoDB Table Name",
            export_name="HealthManagerMCP-UsersTableName"
        )

        CfnOutput(
            self,
            "GoalsTableName",
            value=self.goals_table.table_name,
            description="Goals DynamoDB Table Name",
            export_name="HealthManagerMCP-GoalsTableName"
        )

        CfnOutput(
            self,
            "PoliciesTableName",
            value=self.policies_table.table_name,
            description="Policies DynamoDB Table Name",
            export_name="HealthManagerMCP-PoliciesTableName"
        )

        CfnOutput(
            self,
            "ActivitiesTableName",
            value=self.activities_table.table_name,
            description="Activities DynamoDB Table Name",
            export_name="HealthManagerMCP-ActivitiesTableName"
        )

        # DynamoDBテーブルARN
        CfnOutput(
            self,
            "UsersTableArn",
            value=self.users_table.table_arn,
            description="Users DynamoDB Table ARN",
            export_name="HealthManagerMCP-UsersTableArn"
        )

        CfnOutput(
            self,
            "GoalsTableArn",
            value=self.goals_table.table_arn,
            description="Goals DynamoDB Table ARN",
            export_name="HealthManagerMCP-GoalsTableArn"
        )

        CfnOutput(
            self,
            "PoliciesTableArn",
            value=self.policies_table.table_arn,
            description="Policies DynamoDB Table ARN",
            export_name="HealthManagerMCP-PoliciesTableArn"
        )

        CfnOutput(
            self,
            "ActivitiesTableArn",
            value=self.activities_table.table_arn,
            description="Activities DynamoDB Table ARN",
            export_name="HealthManagerMCP-ActivitiesTableArn"
        )

        # 低優先度（便利）
        CfnOutput(
            self,
            "JwksUrl",
            value=f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool.user_pool_id}/.well-known/jwks.json",
            description="JWKS URL for JWT token verification",
            export_name="HealthManagerMCP-JwksUrl"
        )

        CfnOutput(
            self,
            "DiscoveryUrl",
            value=discovery_url,
            description="OIDC Discovery URL",
            export_name="HealthManagerMCP-DiscoveryUrl"
        )

        CfnOutput(
            self,
            "UserInfoUrl",
            value=f"https://{self.user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com/oauth2/userInfo",
            description="OAuth 2.0 UserInfo URL",
            export_name="HealthManagerMCP-UserInfoUrl"
        )

        # MCP接続設定（JSON形式）
        mcp_connection_config = {
            "gatewayEndpoint": f"https://{self.agentcore_gateway.ref}.agentcore.{self.region}.amazonaws.com",
            "authConfig": {
                "type": "oauth2",
                "authorizationUrl": f"https://{self.user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com/oauth2/authorize",
                "tokenUrl": f"https://{self.user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com/oauth2/token",
                "userInfoUrl": f"https://{self.user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com/oauth2/userInfo",
                "clientId": self.user_pool_client.user_pool_client_id,
                "scopes": ["openid", "profile", "email", "phone"]
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
            description="Complete MCP connection configuration (JSON)",
            export_name="HealthManagerMCP-MCPConnectionConfig"
        )
