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
        print("🔍 AgentCore Gatewayエンドポイントを設定中...")
        
        # 提供されたGateway URLを使用
        self.gateway_endpoint = "https://healthmate-gateway-qasdnfjel0.gateway.bedrock-agentcore.us-west-2.amazonaws.com"
        
        print(f"✅ Gateway Endpoint設定完了: {self.gateway_endpoint}")
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
            print(f"🔗 実際のMCP Gateway接続テスト: {self.gateway_endpoint}")
            
            # 実際のAgentCore Gatewayに接続
            response = requests.post(
                self.gateway_endpoint,
                headers=headers,
                json=mcp_request,
                timeout=30
            )
            
            if response.status_code == 200:
                mcp_response = response.json()
                print("✅ MCP接続成功")
                
                if 'result' in mcp_response and 'tools' in mcp_response['result']:
                    tools = mcp_response['result']['tools']
                    print(f"   利用可能なツール数: {len(tools)}")
                    
                    # ツールリストを表示
                    print("   利用可能なツール:")
                    for tool in tools:
                        print(f"     - {tool['name']}: {tool.get('description', 'No description')}")
                else:
                    print("   ツールリストが見つかりません")
                
                return True
            else:
                print(f"❌ MCP接続失敗: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
            
        except requests.exceptions.RequestException as e:
            print(f"❌ MCP接続失敗 (Network): {str(e)}")
            return False
        except Exception as e:
            print(f"❌ MCP接続失敗: {str(e)}")
            return False
    
    def test_mcp_tools(self) -> bool:
        """実際のMCPツールを呼び出してテスト"""
        print("🧪 MCP ツール呼び出しテスト中...")
        
        if not self.gateway_endpoint or not self.access_token:
            print("❌ Gateway EndpointまたはAccess Tokenが設定されていません")
            return False
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        success = True
        
        # テスト1: UserManagement.AddUser
        print("\n--- UserManagement.AddUser テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "UserManagement___AddUser",
                    "arguments": {
                        "userId": self.user_id,
                        "username": TEST_USERNAME,
                        "email": TEST_EMAIL
                    }
                },
                "id": 2
            }
            
            response = requests.post(
                self.gateway_endpoint,
                headers=headers,
                json=mcp_request,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ AddUser成功: {result}")
            else:
                print(f"❌ AddUser失敗: HTTP {response.status_code} - {response.text}")
                success = False
                
        except Exception as e:
            print(f"❌ AddUser例外: {str(e)}")
            success = False
        
        # テスト2: UserManagement.GetUser
        print("\n--- UserManagement.GetUser テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "UserManagement___GetUser",
                    "arguments": {
                        "userId": self.user_id
                    }
                },
                "id": 3
            }
            
            response = requests.post(
                self.gateway_endpoint,
                headers=headers,
                json=mcp_request,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ GetUser成功: {result}")
            else:
                print(f"❌ GetUser失敗: HTTP {response.status_code} - {response.text}")
                success = False
                
        except Exception as e:
            print(f"❌ GetUser例外: {str(e)}")
            success = False
        
        # テスト3: HealthGoalManagement.AddGoal
        print("\n--- HealthGoalManagement.AddGoal テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "HealthGoalManagement___AddGoal",
                    "arguments": {
                        "userId": self.user_id,
                        "goalType": "fitness",
                        "title": "アスリート体型になる",
                        "description": "体脂肪率を15%以下にして筋肉量を増やす",
                        "targetValue": "体脂肪率15%",
                        "targetDate": "2025-12-31",
                        "priority": 3
                    }
                },
                "id": 4
            }
            
            response = requests.post(
                f"{self.gateway_endpoint}/mcp",
                headers=headers,
                json=mcp_request,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ AddGoal成功: {result}")
            else:
                print(f"❌ AddGoal失敗: HTTP {response.status_code} - {response.text}")
                success = False
                
        except Exception as e:
            print(f"❌ AddGoal例外: {str(e)}")
            success = False
        
        # テスト4: HealthPolicyManagement.AddPolicy
        print("\n--- HealthPolicyManagement.AddPolicy テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "HealthPolicyManagement___AddPolicy",
                    "arguments": {
                        "userId": self.user_id,
                        "policyType": "fasting",
                        "title": "16時間ファスティング",
                        "description": "毎日16時間のファスティングを実施",
                        "rules": {
                            "fastingHours": 16,
                            "eatingWindow": "12:00-20:00"
                        }
                    }
                },
                "id": 5
            }
            
            response = requests.post(
                f"{self.gateway_endpoint}/mcp",
                headers=headers,
                json=mcp_request,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ AddPolicy成功: {result}")
            else:
                print(f"❌ AddPolicy失敗: HTTP {response.status_code} - {response.text}")
                success = False
                
        except Exception as e:
            print(f"❌ AddPolicy例外: {str(e)}")
            success = False
        
        # テスト5: ActivityManagement.AddActivities
        print("\n--- ActivityManagement.AddActivities テスト ---")
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "ActivityManagement___AddActivities",
                    "arguments": {
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
                },
                "id": 6
            }
            
            response = requests.post(
                f"{self.gateway_endpoint}/mcp",
                headers=headers,
                json=mcp_request,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ AddActivities成功: {result}")
            else:
                print(f"❌ AddActivities失敗: HTTP {response.status_code} - {response.text}")
                success = False
                
        except Exception as e:
            print(f"❌ AddActivities例外: {str(e)}")
            success = False
        
        return success
    

    
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
        
        # 5. MCPツール呼び出しテスト
        if not self.test_mcp_tools():
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