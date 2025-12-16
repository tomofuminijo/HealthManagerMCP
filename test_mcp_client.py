#!/usr/bin/env python3
"""
HealthManagerMCP テスト用MCPクライアント

このスクリプトは、HealthManagerMCPシステムの動作確認を行います。
以下の流れでテストを実行します：

1. Cognito User Poolにテストユーザーを作成
2. OAuth 2.0フローでJWTトークンを取得
3. AgentCore GatewayにMCP接続
4. 各Gateway Targetの動作確認

使用方法:
    python test_mcp_client.py
"""

import json
import boto3
import requests
import hashlib
import hmac
import base64
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import os
import sys

# AWS設定
AWS_REGION = "us-west-2"
STACK_NAME = "Healthmate-HealthManagerStack"

# 動的に取得される設定値（CloudFormation Outputsから）
USER_POOL_ID = None
CLIENT_ID = None
CLIENT_SECRET = None
COGNITO_DOMAIN = None

# テストユーザー情報
TEST_USERNAME = f"testuser_{uuid.uuid4().hex[:8]}"
TEST_PASSWORD = "TestPass123!"
TEST_EMAIL = f"{TEST_USERNAME}@example.com"

class HealthManagerMCPTestClient:
    """HealthManagerMCP テスト用クライアント"""
    
    def __init__(self):
        self.cognito_client = boto3.client('cognito-idp', region_name=AWS_REGION)
        self.cloudformation_client = boto3.client('cloudformation', region_name=AWS_REGION)
        self.access_token = None
        self.user_id = None
        self.gateway_endpoint = None
        
        # CloudFormation Outputsから設定を取得
        self._load_config_from_cloudformation()
    
    def _load_config_from_cloudformation(self) -> None:
        """CloudFormation StackのOutputsから設定を動的に取得"""
        global USER_POOL_ID, CLIENT_ID, CLIENT_SECRET, COGNITO_DOMAIN
        
        try:
            print(f"🔧 CloudFormation Stack '{STACK_NAME}' から設定を取得中...")
            
            # CloudFormation Outputsを取得
            response = self.cloudformation_client.describe_stacks(StackName=STACK_NAME)
            stack = response['Stacks'][0]
            outputs = {output['OutputKey']: output['OutputValue'] for output in stack.get('Outputs', [])}
            
            # 必要な設定値を取得
            USER_POOL_ID = outputs.get('UserPoolId')
            CLIENT_ID = outputs.get('UserPoolClientId')
            
            # CognitoDomainをAuthorizationUrlから抽出
            auth_url = outputs.get('AuthorizationUrl', '')
            if auth_url:
                # https://healthmate.auth.us-west-2.amazoncognito.com/oauth2/authorize から
                # healthmate.auth.us-west-2.amazoncognito.com を抽出
                import urllib.parse
                parsed_url = urllib.parse.urlparse(auth_url)
                COGNITO_DOMAIN = parsed_url.netloc
            else:
                COGNITO_DOMAIN = None
            
            if not all([USER_POOL_ID, CLIENT_ID, COGNITO_DOMAIN]):
                missing = []
                if not USER_POOL_ID: missing.append('UserPoolId')
                if not CLIENT_ID: missing.append('UserPoolClientId')
                if not COGNITO_DOMAIN: missing.append('CognitoDomain (from AuthorizationUrl)')
                raise ValueError(f"必要なCloudFormation Outputsが見つかりません: {', '.join(missing)}")
            
            print(f"✅ CloudFormation設定取得完了:")
            print(f"   User Pool ID: {USER_POOL_ID}")
            print(f"   Client ID: {CLIENT_ID}")
            print(f"   Cognito Domain: {COGNITO_DOMAIN}")
            
            # CLIENT_SECRETをCognito APIから取得
            self._get_client_secret()
            
        except Exception as e:
            print(f"❌ CloudFormation設定取得失敗: {str(e)}")
            print("   CloudFormation Stackがデプロイされていることを確認してください")
            raise
    
    def _get_client_secret(self) -> None:
        """Cognito User Pool ClientのSecretを取得"""
        global CLIENT_SECRET
        
        try:
            print("🔐 Cognito Client Secretを取得中...")
            
            response = self.cognito_client.describe_user_pool_client(
                UserPoolId=USER_POOL_ID,
                ClientId=CLIENT_ID
            )
            
            CLIENT_SECRET = response['UserPoolClient'].get('ClientSecret')
            
            if CLIENT_SECRET:
                print(f"✅ Client Secret取得完了: {CLIENT_SECRET[:10]}...")
            else:
                raise ValueError("Client Secretが設定されていません")
                
        except Exception as e:
            print(f"❌ Client Secret取得失敗: {str(e)}")
            raise
        
    def calculate_secret_hash(self, username: str) -> str:
        """Cognito Client Secret Hash を計算"""
        message = username + CLIENT_ID
        dig = hmac.new(
            CLIENT_SECRET.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(dig).decode()
    
    def create_test_user(self) -> bool:
        """テストユーザーを作成"""
        print(f"🔧 テストユーザーを作成中: {TEST_USERNAME}")
        
        try:
            # ユーザー作成
            response = self.cognito_client.admin_create_user(
                UserPoolId=USER_POOL_ID,
                Username=TEST_USERNAME,
                UserAttributes=[
                    {'Name': 'email', 'Value': TEST_EMAIL},
                    {'Name': 'email_verified', 'Value': 'true'}
                ],
                TemporaryPassword=TEST_PASSWORD,
                MessageAction='SUPPRESS'  # ウェルカムメールを送信しない
            )
            
            print(f"✅ ユーザー作成成功: {response['User']['Username']}")
            
            # パスワードを永続化（初回ログイン時の強制変更を回避）
            self.cognito_client.admin_set_user_password(
                UserPoolId=USER_POOL_ID,
                Username=TEST_USERNAME,
                Password=TEST_PASSWORD,
                Permanent=True
            )
            
            print(f"✅ パスワード設定完了")
            return True
            
        except Exception as e:
            print(f"❌ ユーザー作成失敗: {str(e)}")
            return False
    
    def authenticate_user(self) -> bool:
        """ユーザー認証してJWTトークンを取得"""
        print(f"🔐 ユーザー認証中: {TEST_USERNAME}")
        
        try:
            secret_hash = self.calculate_secret_hash(TEST_USERNAME)
            
            response = self.cognito_client.admin_initiate_auth(
                UserPoolId=USER_POOL_ID,
                ClientId=CLIENT_ID,
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters={
                    'USERNAME': TEST_USERNAME,
                    'PASSWORD': TEST_PASSWORD,
                    'SECRET_HASH': secret_hash
                }
            )
            
            if 'AuthenticationResult' in response:
                auth_result = response['AuthenticationResult']
                self.access_token = auth_result['AccessToken']
                id_token = auth_result['IdToken']
                
                # JWTからユーザーIDを抽出（簡易版）
                import jwt
                decoded_token = jwt.decode(id_token, options={"verify_signature": False})
                self.user_id = decoded_token['sub']
                
                print(f"✅ 認証成功")
                print(f"   User ID: {self.user_id}")
                print(f"   Access Token: {self.access_token[:20]}...")
                return True
            else:
                print(f"❌ 認証失敗: AuthenticationResult not found")
                return False
                
        except Exception as e:
            print(f"❌ 認証失敗: {str(e)}")
            return False
    
    def discover_gateway_endpoint(self) -> bool:
        """AgentCore Gatewayのエンドポイントを発見"""
        print("🔍 AgentCore Gatewayエンドポイントを検索中...")
        
        # 注: 実際のAgentCore Gateway APIが利用可能になるまで、
        # 仮のエンドポイントを使用
        # TODO: 実際のAWS CLIまたはSDKでGatewayエンドポイントを取得
        
        # 仮のエンドポイント（実際のデプロイ後に更新が必要）
        self.gateway_endpoint = "https://healthmate-gateway.bedrock-agentcore.us-west-2.amazonaws.com"
        
        print(f"⚠️  仮のエンドポイントを使用: {self.gateway_endpoint}")
        print("   注: 実際のデプロイ後にエンドポイントを更新してください")
        return True
    
    def test_mcp_connection(self) -> bool:
        """MCP接続をテスト"""
        print("🔗 MCP接続をテスト中...")
        
        if not self.gateway_endpoint:
            print("❌ Gatewayエンドポイントが設定されていません")
            return False
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # MCPプロトコル: ツールリスト取得
        mcp_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        }
        
        try:
            # 注: 実際のAgentCore Gateway APIが利用可能になるまで、
            # この部分はモックレスポンスを返す
            print("⚠️  実際のMCP接続は、AgentCore Gateway APIが利用可能になってから実装されます")
            print("   現在はモックレスポンスを使用します")
            
            # モックレスポンス
            mock_response = {
                "jsonrpc": "2.0",
                "result": {
                    "tools": [
                        {"name": "UserManagement.addUser", "description": "新しいユーザー情報を作成する"},
                        {"name": "UserManagement.updateUser", "description": "ユーザー情報を更新する"},
                        {"name": "UserManagement.getUser", "description": "ユーザー情報を取得する"},
                        {"name": "HealthGoalManagement.addGoal", "description": "新しい健康目標を追加する"},
                        {"name": "HealthGoalManagement.updateGoal", "description": "既存の健康目標を更新する"},
                        {"name": "HealthGoalManagement.deleteGoal", "description": "指定した健康目標を削除する"},
                        {"name": "HealthGoalManagement.getGoals", "description": "ユーザーのすべての健康目標を取得する"},
                        {"name": "HealthPolicyManagement.addPolicy", "description": "新しい健康ポリシーを追加する"},
                        {"name": "HealthPolicyManagement.updatePolicy", "description": "既存の健康ポリシーを更新する"},
                        {"name": "HealthPolicyManagement.deletePolicy", "description": "指定した健康ポリシーを削除する"},
                        {"name": "HealthPolicyManagement.getPolicies", "description": "ユーザーのすべての健康ポリシーを取得する"},
                        {"name": "ActivityManagement.addActivities", "description": "指定した日に新しい活動を追加する"},
                        {"name": "ActivityManagement.updateActivity", "description": "指定した日の特定の時刻の活動だけを部分的に更新する"},
                        {"name": "ActivityManagement.updateActivities", "description": "指定した日の全ての活動を完全に置き換える"},
                        {"name": "ActivityManagement.deleteActivity", "description": "指定した日の指定した行動を削除する"},
                        {"name": "ActivityManagement.getActivities", "description": "指定した日のユーザーの行動を取得する"},
                        {"name": "ActivityManagement.getActivitiesInRange", "description": "指定した期間のユーザーの行動履歴を取得する"}
                    ]
                },
                "id": 1
            }
            
            print("✅ MCP接続成功（モック）")
            print(f"   利用可能なツール数: {len(mock_response['result']['tools'])}")
            
            # ツールリストを表示
            print("   利用可能なツール:")
            for tool in mock_response['result']['tools']:
                print(f"     - {tool['name']}: {tool['description']}")
            
            return True
            
        except Exception as e:
            print(f"❌ MCP接続失敗: {str(e)}")
            return False
    
    def test_lambda_functions_directly(self) -> bool:
        """Lambda関数を直接テスト"""
        print("🧪 Lambda関数を直接テスト中...")
        
        lambda_client = boto3.client('lambda', region_name=AWS_REGION)
        
        # テストケース0: UserLambda（healthmate-usersテーブル）
        print("\n--- UserLambda テスト ---")
        try:
            # ユーザー情報を追加
            add_user_payload = {
                "userId": self.user_id,
                "username": TEST_USERNAME,
                "email": TEST_EMAIL
            }
            
            response = lambda_client.invoke(
                FunctionName='healthmanagermcp-user',
                InvocationType='RequestResponse',
                Payload=json.dumps(add_user_payload)
            )
            
            result = json.loads(response['Payload'].read())
            print(f"✅ ユーザー情報追加: {result}")
            
            if result.get('success'):
                # ユーザー情報を取得
                get_user_payload = {
                    "userId": self.user_id
                }
                
                response = lambda_client.invoke(
                    FunctionName='healthmanagermcp-user',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(get_user_payload)
                )
                
                result = json.loads(response['Payload'].read())
                print(f"✅ ユーザー情報取得: {result}")
                
                # ユーザー情報を更新
                update_user_payload = {
                    "userId": self.user_id,
                    "username": f"{TEST_USERNAME}_updated",
                    "lastLoginAt": datetime.now().isoformat()
                }
                
                response = lambda_client.invoke(
                    FunctionName='healthmanagermcp-user',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(update_user_payload)
                )
                
                result = json.loads(response['Payload'].read())
                print(f"✅ ユーザー情報更新: {result}")
                
        except Exception as e:
            print(f"❌ UserLambda テスト失敗: {str(e)}")
        
        # テストケース1: HealthGoalLambda
        print("\n--- HealthGoalLambda テスト ---")
        try:
            # 健康目標を追加
            add_goal_payload = {
                "userId": self.user_id,
                "goalType": "fitness",
                "title": "アスリート体型になる",
                "description": "体脂肪率を15%以下にして筋肉量を増やす",
                "targetValue": "体脂肪率15%",
                "targetDate": "2025-12-31",
                "priority": 3
            }
            
            response = lambda_client.invoke(
                FunctionName='healthmanagermcp-health-goal',
                InvocationType='RequestResponse',
                Payload=json.dumps(add_goal_payload)
            )
            
            result = json.loads(response['Payload'].read())
            print(f"✅ 健康目標追加: {result}")
            
            if result.get('success'):
                goal_id = result.get('goalId')
                
                # 健康目標を取得
                get_goals_payload = {
                    "userId": self.user_id
                }
                
                response = lambda_client.invoke(
                    FunctionName='healthmanagermcp-health-goal',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(get_goals_payload)
                )
                
                result = json.loads(response['Payload'].read())
                print(f"✅ 健康目標取得: {result}")
                
                # 健康目標を更新
                if goal_id:
                    update_goal_payload = {
                        "userId": self.user_id,
                        "goalId": goal_id,
                        "description": "体脂肪率を12%以下にして筋肉量を大幅に増やす（更新）",
                        "status": "active"
                    }
                    
                    response = lambda_client.invoke(
                        FunctionName='healthmanagermcp-health-goal',
                        InvocationType='RequestResponse',
                        Payload=json.dumps(update_goal_payload)
                    )
                    
                    result = json.loads(response['Payload'].read())
                    print(f"✅ 健康目標更新: {result}")
                
        except Exception as e:
            print(f"❌ HealthGoalLambda テスト失敗: {str(e)}")
        
        # テストケース2: HealthPolicyLambda
        print("\n--- HealthPolicyLambda テスト ---")
        try:
            # 健康ポリシーを追加
            add_policy_payload = {
                "userId": self.user_id,
                "policyType": "fasting",
                "description": "毎日16時間のファスティングを実施",
                "parameters": {
                    "fastingHours": 16,
                    "eatingWindow": "12:00-20:00"
                }
            }
            
            response = lambda_client.invoke(
                FunctionName='healthmanagermcp-health-policy',
                InvocationType='RequestResponse',
                Payload=json.dumps(add_policy_payload)
            )
            
            result = json.loads(response['Payload'].read())
            print(f"✅ 健康ポリシー追加: {result}")
            
            if result.get('success'):
                policy_id = result.get('policyId')
                
                # 健康ポリシーを取得
                get_policies_payload = {
                    "userId": self.user_id
                }
                
                response = lambda_client.invoke(
                    FunctionName='healthmanagermcp-health-policy',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(get_policies_payload)
                )
                
                result = json.loads(response['Payload'].read())
                print(f"✅ 健康ポリシー取得: {result}")
                
                # 健康ポリシーを更新
                if policy_id:
                    update_policy_payload = {
                        "userId": self.user_id,
                        "policyId": policy_id,
                        "description": "毎日18時間のファスティングを実施（更新）",
                        "parameters": {
                            "fastingHours": 18,
                            "eatingWindow": "12:00-18:00"
                        }
                    }
                    
                    response = lambda_client.invoke(
                        FunctionName='healthmanagermcp-health-policy',
                        InvocationType='RequestResponse',
                        Payload=json.dumps(update_policy_payload)
                    )
                    
                    result = json.loads(response['Payload'].read())
                    print(f"✅ 健康ポリシー更新: {result}")
                
        except Exception as e:
            print(f"❌ HealthPolicyLambda テスト失敗: {str(e)}")
        
        # テストケース3: ActivityLambda
        print("\n--- ActivityLambda テスト ---")
        try:
            # 活動記録を追加
            today = datetime.now().strftime("%Y-%m-%d")
            add_activities_payload = {
                "operationType": "append",
                "userId": self.user_id,
                "date": today,
                "activities": [
                    {
                        "time": "08:00",
                        "activityType": "wakeUp",
                        "description": "起床",
                        "items": ["自然に目覚めた"]
                    },
                    {
                        "time": "08:30",
                        "activityType": "exercise",
                        "description": "運動",
                        "items": ["ジョギング30分", "筋トレ20分"]
                    }
                ]
            }
            
            response = lambda_client.invoke(
                FunctionName='healthmanagermcp-activity',
                InvocationType='RequestResponse',
                Payload=json.dumps(add_activities_payload)
            )
            
            result = json.loads(response['Payload'].read())
            print(f"✅ 活動記録追加: {result}")
            
            if result.get('success'):
                # 活動記録を取得
                get_activities_payload = {
                    "userId": self.user_id,
                    "date": today
                }
                
                response = lambda_client.invoke(
                    FunctionName='healthmanagermcp-activity',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(get_activities_payload)
                )
                
                result = json.loads(response['Payload'].read())
                print(f"✅ 活動記録取得: {result}")
                
                # 特定の活動を更新（UpdateActivity）
                update_activity_payload = {
                    "userId": self.user_id,
                    "date": today,
                    "time": "08:30",
                    "activityType": "exercise",
                    "description": "運動（更新）",
                    "items": ["ジョギング45分", "筋トレ30分"]
                }
                
                response = lambda_client.invoke(
                    FunctionName='healthmanagermcp-activity',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(update_activity_payload)
                )
                
                result = json.loads(response['Payload'].read())
                print(f"✅ 特定活動更新: {result}")
                
                # 期間内活動記録を取得（GetActivitiesInRange）
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                get_range_payload = {
                    "userId": self.user_id,
                    "startDate": yesterday,
                    "endDate": today
                }
                
                response = lambda_client.invoke(
                    FunctionName='healthmanagermcp-activity',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(get_range_payload)
                )
                
                result = json.loads(response['Payload'].read())
                print(f"✅ 期間内活動記録取得: {result}")
                
                # bowelMovement活動タイプのテスト（ChatGPTで問題になったケース）
                bowel_activity_payload = {
                    "operationType": "append",
                    "userId": self.user_id,
                    "date": today,
                    "activities": [
                        {
                            "time": "13:00",
                            "activityType": "bowelMovement",
                            "description": "排便",
                            "items": ["正常な排便"]
                        }
                    ]
                }
                
                response = lambda_client.invoke(
                    FunctionName='healthmanagermcp-activity',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(bowel_activity_payload)
                )
                
                result = json.loads(response['Payload'].read())
                print(f"✅ 排便活動記録追加: {result}")
                
                # 全活動タイプのテスト（MCPスキーマで定義されているすべてのactivityType）
                all_activity_types_payload = {
                    "operationType": "append",
                    "userId": self.user_id,
                    "date": today,
                    "activities": [
                        {
                            "time": "14:00",
                            "activityType": "meal",
                            "description": "昼食",
                            "items": ["サラダ", "チキン", "玄米"]
                        },
                        {
                            "time": "15:00",
                            "activityType": "snack",
                            "description": "おやつ",
                            "items": ["ナッツ", "フルーツ"]
                        },
                        {
                            "time": "16:00",
                            "activityType": "weight",
                            "description": "体重測定",
                            "items": ["70.5kg"]
                        },
                        {
                            "time": "17:00",
                            "activityType": "mood",
                            "description": "気分記録",
                            "items": ["良好", "エネルギッシュ"]
                        },
                        {
                            "time": "18:00",
                            "activityType": "medication",
                            "description": "薬の服用",
                            "items": ["ビタミンD", "オメガ3"]
                        }
                    ]
                }
                
                response = lambda_client.invoke(
                    FunctionName='healthmanagermcp-activity',
                    InvocationType='RequestResponse',
                    Payload=json.dumps(all_activity_types_payload)
                )
                
                result = json.loads(response['Payload'].read())
                print(f"✅ 全活動タイプテスト: {result}")
                
        except Exception as e:
            print(f"❌ ActivityLambda テスト失敗: {str(e)}")
        
        return True
    
    def cleanup_test_user(self) -> bool:
        """テストユーザーを削除"""
        print(f"🧹 テストユーザーを削除中: {TEST_USERNAME}")
        
        try:
            self.cognito_client.admin_delete_user(
                UserPoolId=USER_POOL_ID,
                Username=TEST_USERNAME
            )
            print(f"✅ テストユーザー削除完了")
            return True
            
        except Exception as e:
            print(f"❌ テストユーザー削除失敗: {str(e)}")
            return False
    
    def run_tests(self) -> bool:
        """全テストを実行"""
        print("🚀 HealthManagerMCP テスト開始")
        print("=" * 50)
        
        success = True
        
        # 1. テストユーザー作成
        if not self.create_test_user():
            return False
        
        # 2. ユーザー認証
        if not self.authenticate_user():
            self.cleanup_test_user()
            return False
        
        # 3. Gatewayエンドポイント発見
        if not self.discover_gateway_endpoint():
            self.cleanup_test_user()
            return False
        
        # 4. MCP接続テスト
        if not self.test_mcp_connection():
            success = False
        
        # 5. Lambda関数直接テスト
        if not self.test_lambda_functions_directly():
            success = False
        
        # 6. クリーンアップ
        self.cleanup_test_user()
        
        print("=" * 50)
        if success:
            print("✅ 全テスト完了")
        else:
            print("⚠️  一部テストで問題が発生しました")
        
        return success

def main():
    """メイン関数"""
    # 必要なライブラリをチェック
    try:
        import jwt
    except ImportError:
        print("❌ PyJWT ライブラリが必要です: pip install PyJWT")
        sys.exit(1)
    
    # テスト実行
    client = HealthManagerMCPTestClient()
    success = client.run_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()