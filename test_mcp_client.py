#!/usr/bin/env python3
"""
HealthManagerMCP テスト用MCPクライアント（M2M認証版）

このスクリプトは、HealthManagerMCPシステムのM2M認証での動作確認を行います。
以下の流れでテストを実行します：

1. Cognito User PoolからClient Credentials Flowでアクセストークンを取得
2. AgentCore GatewayにM2M認証でMCP接続
3. 各Gateway Targetの動作確認（全23ツール）

テスト対象ツール:
- UserManagement (3ツール): AddUser, UpdateUser, GetUser
- HealthGoalManagement (4ツール): AddGoal, UpdateGoal, DeleteGoal, GetGoals
- HealthPolicyManagement (4ツール): AddPolicy, UpdatePolicy, DeletePolicy, GetPolicies
- ActivityManagement (6ツール): AddActivities, UpdateActivity, UpdateActivities, DeleteActivity, GetActivities, GetActivitiesInRange
- BodyMeasurementManagement (6ツール): AddBodyMeasurement, UpdateBodyMeasurement, DeleteBodyMeasurement, GetLatestMeasurements, GetOldestMeasurements, GetMeasurementHistory

環境設定:
    HEALTHMATE_ENV環境変数で環境を指定（dev/stage/prod、デフォルト: dev）
    
使用方法:
    # デフォルト環境（dev）でテスト
    python test_mcp_client.py
    
    # 特定の環境でテスト
    HEALTHMATE_ENV=stage python test_mcp_client.py
    HEALTHMATE_ENV=prod python test_mcp_client.py
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

# 環境設定モジュールのインポート
sys.path.append(os.path.join(os.path.dirname(__file__), 'cdk'))
from cdk.environment.configuration_provider import ConfigurationProvider
from cdk.environment.environment_manager import EnvironmentManager

# 環境設定の初期化
config_provider = ConfigurationProvider("HealthManager")
AWS_REGION = config_provider.get_aws_region()
STACK_NAME = config_provider.get_stack_name("Healthmate-HealthManagerStack")
ENVIRONMENT = EnvironmentManager.get_environment()
ENVIRONMENT_SUFFIX = config_provider.get_environment_suffix()

# 動的に取得される設定値（CloudFormation Outputsから）
USER_POOL_ID = None
CLIENT_ID = None
CLIENT_SECRET = None
GATEWAY_ENDPOINT = None

# M2M認証用の固定ユーザーID（テスト用）
TEST_USER_ID = f"test-user-{uuid.uuid4().hex[:8]}"

class HealthManagerMCPTestClient:
    """HealthManagerMCP テスト用クライアント（M2M認証版）"""
    
    def __init__(self):
        self.cognito_client = boto3.client('cognito-idp', region_name=AWS_REGION)
        self.cloudformation_client = boto3.client('cloudformation', region_name=AWS_REGION)
        self.access_token = None
        self.user_id = TEST_USER_ID
        self.gateway_endpoint = None
        
        # CloudFormation Outputsから設定を取得
        self._load_config_from_cloudformation()
    
    def _load_config_from_cloudformation(self) -> None:
        """CloudFormation StackのOutputsから設定を動的に取得"""
        global USER_POOL_ID, CLIENT_ID, CLIENT_SECRET, GATEWAY_ENDPOINT
        
        try:
            print(f"🔧 CloudFormation Stack '{STACK_NAME}' から設定を取得中...")
            print(f"🌍 Environment: {ENVIRONMENT}")
            
            # CloudFormation Outputsを取得
            response = self.cloudformation_client.describe_stacks(StackName=STACK_NAME)
            stack = response['Stacks'][0]
            outputs = {output['OutputKey']: output['OutputValue'] for output in stack.get('Outputs', [])}
            
            # 必要な設定値を取得
            USER_POOL_ID = outputs.get('UserPoolId')
            CLIENT_ID = outputs.get('UserPoolClientId')
            GATEWAY_ENDPOINT = outputs.get('GatewayEndpoint')
            
            if not all([USER_POOL_ID, CLIENT_ID, GATEWAY_ENDPOINT]):
                missing = []
                if not USER_POOL_ID: missing.append('UserPoolId')
                if not CLIENT_ID: missing.append('UserPoolClientId')
                if not GATEWAY_ENDPOINT: missing.append('GatewayEndpoint')
                raise ValueError(f"必要なCloudFormation Outputsが見つかりません: {', '.join(missing)}")
            
            print(f"✅ CloudFormation設定取得完了:")
            print(f"   User Pool ID: {USER_POOL_ID}")
            print(f"   Client ID: {CLIENT_ID}")
            print(f"   Gateway Endpoint: {GATEWAY_ENDPOINT}")
            print(f"   Environment Suffix: {ENVIRONMENT_SUFFIX}")
            
            # CLIENT_SECRETをCognito APIから取得
            self._get_client_secret()
            
            # Gateway Endpointを設定（/mcpパスを除去してベースURLを取得）
            self.gateway_endpoint = GATEWAY_ENDPOINT.replace('/mcp', '')
            
        except Exception as e:
            print(f"❌ CloudFormation設定取得失敗: {str(e)}")
            print("   CloudFormation Stackがデプロイされていることを確認してください")
            print(f"   Stack名: {STACK_NAME}")
            print(f"   Environment: {ENVIRONMENT}")
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
        
    def authenticate_m2m(self) -> bool:
        """M2M認証（Client Credentials Flow）でJWTトークンを取得"""
        print("🔐 M2M認証（Client Credentials Flow）実行中...")
        
        try:
            # 環境別のOAuth2 Token Endpointを構築
            # 環境別のCognito Domain名を使用
            cognito_domain = f"healthmanager-m2m-auth{ENVIRONMENT_SUFFIX}"
            oauth_token_url = f"https://{cognito_domain}.auth.{AWS_REGION}.amazoncognito.com/oauth2/token"
            
            # Basic認証用のCredentials
            auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {auth_b64}'
            }
            
            data = {
                'grant_type': 'client_credentials',
                'scope': 'HealthManager/HealthTarget:invoke'
            }
            
            print(f"🔗 OAuth2 Token Endpoint: {oauth_token_url}")
            print(f"🔑 Scope: HealthManager/HealthTarget:invoke")
            print(f"🌍 Environment: {ENVIRONMENT}")
            
            response = requests.post(
                oauth_token_url,
                headers=headers,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                token_response = response.json()
                self.access_token = token_response.get('access_token')
                
                if self.access_token:
                    print(f"✅ M2M認証成功")
                    print(f"   Access Token: {self.access_token[:20]}...")
                    print(f"   Token Type: {token_response.get('token_type', 'Bearer')}")
                    print(f"   Expires In: {token_response.get('expires_in', 'Unknown')} seconds")
                    print(f"   Scope: {token_response.get('scope', 'Unknown')}")
                    return True
                else:
                    print(f"❌ M2M認証失敗: access_token not found in response")
                    print(f"   Response: {token_response}")
                    return False
            else:
                print(f"❌ M2M認証失敗: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ M2M認証失敗: {str(e)}")
            return False
    
    def test_mcp_connection(self) -> bool:
        """MCP接続をテスト"""
        print("🔗 MCP接続をテスト中...")
        
        if not self.gateway_endpoint:
            print("❌ Gatewayエンドポイントが設定されていません")
            return False
        
        # MCPエンドポイントは /mcp パスが必要
        mcp_endpoint = f"{self.gateway_endpoint}/mcp"
        
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
            print(f"🔗 実際のMCP Gateway接続テスト: {mcp_endpoint}")
            
            # 実際のAgentCore Gatewayに接続
            response = requests.post(
                mcp_endpoint,
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
        """実際のMCPツールを呼び出してテスト（全23ツール）"""
        print("🧪 MCP ツール呼び出しテスト中（全23ツール）...")
        
        if not self.gateway_endpoint or not self.access_token:
            print("❌ Gateway EndpointまたはAccess Tokenが設定されていません")
            return False
        
        # MCPエンドポイントは /mcp パスが必要
        mcp_endpoint = f"{self.gateway_endpoint}/mcp"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        success = True
        test_goal_id = None
        test_policy_id = None
        today = datetime.now().strftime("%Y-%m-%d")
        
        # === UserManagement ツール (3個) ===
        
        # テスト1: UserManagement.AddUser
        print("\n--- 1. UserManagement.AddUser テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "UserManagement___AddUser",
                    "arguments": {
                        "userId": self.user_id,
                        "username": f"testuser_{self.user_id[:8]}",
                        "email": f"test_{self.user_id[:8]}@example.com",
                        "goals": ["100歳まで健康寿命", "体重を10kg減らす"]
                    }
                },
                "id": 1
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ AddUser失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ AddUser成功")
            else:
                print(f"❌ AddUser失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ AddUser例外: {str(e)}")
            success = False
        
        # テスト2: UserManagement.UpdateUser
        print("\n--- 2. UserManagement.UpdateUser テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "UserManagement___UpdateUser",
                    "arguments": {
                        "userId": self.user_id,
                        "username": f"updated_testuser_{self.user_id[:8]}",
                        "email": f"updated_test_{self.user_id[:8]}@example.com",
                        "goals": ["100歳まで健康寿命", "体重を15kg減らす", "筋肉量を増やす"]
                    }
                },
                "id": 2
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ UpdateUser失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ UpdateUser成功")
            else:
                print(f"❌ UpdateUser失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ UpdateUser例外: {str(e)}")
            success = False
        
        # テスト3: UserManagement.GetUser
        print("\n--- 3. UserManagement.GetUser テスト ---")
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
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ GetUser失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ GetUser成功")
            else:
                print(f"❌ GetUser失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ GetUser例外: {str(e)}")
            success = False
        
        # === HealthGoalManagement ツール (4個) ===
        
        # テスト4: HealthGoalManagement.AddGoal
        print("\n--- 4. HealthGoalManagement.AddGoal テスト ---")
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
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ AddGoal失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ AddGoal成功")
                    # goalIdを保存（後続のテストで使用）
                    if 'result' in result and 'content' in result['result']:
                        content = result['result']['content']
                        if content and isinstance(content, list) and len(content) > 0:
                            text_content = content[0].get('text', '')
                            if text_content:
                                try:
                                    parsed_content = json.loads(text_content)
                                    if 'goalId' in parsed_content:
                                        test_goal_id = parsed_content['goalId']
                                except json.JSONDecodeError:
                                    pass
            else:
                print(f"❌ AddGoal失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ AddGoal例外: {str(e)}")
            success = False
        
        # テスト5: HealthGoalManagement.GetGoals
        print("\n--- 5. HealthGoalManagement.GetGoals テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "HealthGoalManagement___GetGoals",
                    "arguments": {
                        "userId": self.user_id
                    }
                },
                "id": 5
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ GetGoals失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ GetGoals成功")
                    # goalIdを取得（AddGoalで取得できなかった場合）
                    if not test_goal_id and 'result' in result and 'content' in result['result']:
                        content = result['result']['content']
                        if content and isinstance(content, list) and len(content) > 0:
                            text_content = content[0].get('text', '')
                            if text_content:
                                try:
                                    parsed_content = json.loads(text_content)
                                    if 'goals' in parsed_content and parsed_content['goals']:
                                        first_goal = parsed_content['goals'][0]
                                        if 'goalId' in first_goal:
                                            test_goal_id = first_goal['goalId']
                                except json.JSONDecodeError:
                                    pass
            else:
                print(f"❌ GetGoals失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ GetGoals例外: {str(e)}")
            success = False
        
        # テスト6: HealthGoalManagement.UpdateGoal
        print("\n--- 6. HealthGoalManagement.UpdateGoal テスト ---")
        try:
            if test_goal_id:
                mcp_request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "HealthGoalManagement___UpdateGoal",
                        "arguments": {
                            "userId": self.user_id,
                            "goalId": test_goal_id,
                            "title": "更新されたアスリート体型目標",
                            "description": "体脂肪率を12%以下にして筋肉量を大幅に増やす",
                            "targetValue": "体脂肪率12%",
                            "priority": 4,
                            "status": "active"
                        }
                    },
                    "id": 6
                }
                
                response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'error' in result:
                        print(f"❌ UpdateGoal失敗: {result['error']}")
                        success = False
                    else:
                        print(f"✅ UpdateGoal成功")
                else:
                    print(f"❌ UpdateGoal失敗: HTTP {response.status_code}")
                    success = False
            else:
                print("⚠️ UpdateGoal スキップ: goalIdが取得できませんでした")
                
        except Exception as e:
            print(f"❌ UpdateGoal例外: {str(e)}")
            success = False
        
        # テスト7: HealthGoalManagement.DeleteGoal
        print("\n--- 7. HealthGoalManagement.DeleteGoal テスト ---")
        try:
            if test_goal_id:
                mcp_request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "HealthGoalManagement___DeleteGoal",
                        "arguments": {
                            "userId": self.user_id,
                            "goalId": test_goal_id
                        }
                    },
                    "id": 7
                }
                
                response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'error' in result:
                        print(f"❌ DeleteGoal失敗: {result['error']}")
                        success = False
                    else:
                        print(f"✅ DeleteGoal成功")
                else:
                    print(f"❌ DeleteGoal失敗: HTTP {response.status_code}")
                    success = False
            else:
                print("⚠️ DeleteGoal スキップ: goalIdが取得できませんでした")
                
        except Exception as e:
            print(f"❌ DeleteGoal例外: {str(e)}")
            success = False
        
        # === HealthPolicyManagement ツール (4個) ===
        
        # テスト8: HealthPolicyManagement.AddPolicy
        print("\n--- 8. HealthPolicyManagement.AddPolicy テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "HealthPolicyManagement___AddPolicy",
                    "arguments": {
                        "userId": self.user_id,
                        "policyType": "diet",
                        "description": "低糖質ダイエット",
                        "parameters": {
                            "maxCarbs": "50g/day",
                            "mealTiming": ["8:00", "12:00", "18:00"]
                        }
                    }
                },
                "id": 8
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ AddPolicy失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ AddPolicy成功")
                    # policyIdを保存（後続のテストで使用）
                    if 'result' in result and 'content' in result['result']:
                        content = result['result']['content']
                        if content and isinstance(content, list) and len(content) > 0:
                            text_content = content[0].get('text', '')
                            if text_content:
                                try:
                                    parsed_content = json.loads(text_content)
                                    if 'policyId' in parsed_content:
                                        test_policy_id = parsed_content['policyId']
                                except json.JSONDecodeError:
                                    pass
            else:
                print(f"❌ AddPolicy失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ AddPolicy例外: {str(e)}")
            success = False
        
        # テスト9: HealthPolicyManagement.GetPolicies
        print("\n--- 9. HealthPolicyManagement.GetPolicies テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "HealthPolicyManagement___GetPolicies",
                    "arguments": {
                        "userId": self.user_id
                    }
                },
                "id": 9
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ GetPolicies失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ GetPolicies成功")
                    # policyIdを取得（AddPolicyで取得できなかった場合）
                    if not test_policy_id and 'result' in result and 'content' in result['result']:
                        content = result['result']['content']
                        if content and isinstance(content, list) and len(content) > 0:
                            text_content = content[0].get('text', '')
                            if text_content:
                                try:
                                    parsed_content = json.loads(text_content)
                                    if 'policies' in parsed_content and parsed_content['policies']:
                                        first_policy = parsed_content['policies'][0]
                                        if 'policyId' in first_policy:
                                            test_policy_id = first_policy['policyId']
                                except json.JSONDecodeError:
                                    pass
            else:
                print(f"❌ GetPolicies失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ GetPolicies例外: {str(e)}")
            success = False
        
        # テスト10: HealthPolicyManagement.UpdatePolicy
        print("\n--- 10. HealthPolicyManagement.UpdatePolicy テスト ---")
        try:
            if test_policy_id:
                mcp_request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "HealthPolicyManagement___UpdatePolicy",
                        "arguments": {
                            "userId": self.user_id,
                            "policyId": test_policy_id,
                            "description": "更新された低糖質ダイエット",
                            "parameters": {
                                "maxCarbs": "40g/day",
                                "mealTiming": ["7:30", "12:30", "18:30"],
                                "cheatDay": "Sunday"
                            }
                        }
                    },
                    "id": 10
                }
                
                response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'error' in result:
                        print(f"❌ UpdatePolicy失敗: {result['error']}")
                        success = False
                    else:
                        print(f"✅ UpdatePolicy成功")
                else:
                    print(f"❌ UpdatePolicy失敗: HTTP {response.status_code}")
                    success = False
            else:
                print("⚠️ UpdatePolicy スキップ: policyIdが取得できませんでした")
                
        except Exception as e:
            print(f"❌ UpdatePolicy例外: {str(e)}")
            success = False
        
        # テスト11: HealthPolicyManagement.DeletePolicy
        print("\n--- 11. HealthPolicyManagement.DeletePolicy テスト ---")
        try:
            if test_policy_id:
                mcp_request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "HealthPolicyManagement___DeletePolicy",
                        "arguments": {
                            "userId": self.user_id,
                            "policyId": test_policy_id
                        }
                    },
                    "id": 11
                }
                
                response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'error' in result:
                        print(f"❌ DeletePolicy失敗: {result['error']}")
                        success = False
                    else:
                        print(f"✅ DeletePolicy成功")
                else:
                    print(f"❌ DeletePolicy失敗: HTTP {response.status_code}")
                    success = False
            else:
                print("⚠️ DeletePolicy スキップ: policyIdが取得できませんでした")
                
        except Exception as e:
            print(f"❌ DeletePolicy例外: {str(e)}")
            success = False
        
        # === ActivityManagement ツール (6個) ===
        
        # テスト12: ActivityManagement.AddActivities
        print("\n--- 12. ActivityManagement.AddActivities テスト ---")
        try:
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
                "id": 12
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ AddActivities失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ AddActivities成功")
            else:
                print(f"❌ AddActivities失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ AddActivities例外: {str(e)}")
            success = False
        
        # テスト13: ActivityManagement.GetActivities
        print("\n--- 13. ActivityManagement.GetActivities テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "ActivityManagement___GetActivities",
                    "arguments": {
                        "userId": self.user_id,
                        "date": today
                    }
                },
                "id": 13
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ GetActivities失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ GetActivities成功")
            else:
                print(f"❌ GetActivities失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ GetActivities例外: {str(e)}")
            success = False
        
        # テスト14: ActivityManagement.UpdateActivity
        print("\n--- 14. ActivityManagement.UpdateActivity テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "ActivityManagement___UpdateActivity",
                    "arguments": {
                        "userId": self.user_id,
                        "date": today,
                        "time": "08:00",
                        "activityType": "wakeUp",
                        "description": "更新された起床",
                        "items": ["アラームで目覚めた", "すっきり起床"]
                    }
                },
                "id": 14
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ UpdateActivity失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ UpdateActivity成功")
            else:
                print(f"❌ UpdateActivity失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ UpdateActivity例外: {str(e)}")
            success = False
        
        # テスト15: ActivityManagement.UpdateActivities
        print("\n--- 15. ActivityManagement.UpdateActivities テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "ActivityManagement___UpdateActivities",
                    "arguments": {
                        "operationType": "replace",
                        "userId": self.user_id,
                        "date": today,
                        "activities": [
                            {
                                "time": "07:30",
                                "activityType": "wakeUp",
                                "description": "早起き",
                                "items": ["自然に目覚めた"]
                            },
                            {
                                "time": "08:00",
                                "activityType": "meal",
                                "description": "朝食",
                                "items": ["オートミール", "バナナ", "コーヒー"]
                            },
                            {
                                "time": "09:00",
                                "activityType": "exercise",
                                "description": "朝の運動",
                                "items": ["ヨガ30分", "ストレッチ15分"]
                            }
                        ]
                    }
                },
                "id": 15
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ UpdateActivities失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ UpdateActivities成功")
            else:
                print(f"❌ UpdateActivities失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ UpdateActivities例外: {str(e)}")
            success = False
        
        # テスト16: ActivityManagement.GetActivitiesInRange
        print("\n--- 16. ActivityManagement.GetActivitiesInRange テスト ---")
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "ActivityManagement___GetActivitiesInRange",
                    "arguments": {
                        "userId": self.user_id,
                        "startDate": yesterday,
                        "endDate": today
                    }
                },
                "id": 16
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ GetActivitiesInRange失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ GetActivitiesInRange成功")
            else:
                print(f"❌ GetActivitiesInRange失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ GetActivitiesInRange例外: {str(e)}")
            success = False
        
        # テスト17: ActivityManagement.DeleteActivity
        print("\n--- 17. ActivityManagement.DeleteActivity テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "ActivityManagement___DeleteActivity",
                    "arguments": {
                        "userId": self.user_id,
                        "date": today,
                        "time": "09:00"
                    }
                },
                "id": 17
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ DeleteActivity失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ DeleteActivity成功")
            else:
                print(f"❌ DeleteActivity失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ DeleteActivity例外: {str(e)}")
            success = False
        
        # === BodyMeasurementManagement ツール (6個) ===
        
        # 複数の測定記録を作成してLatest/Oldest処理をテスト
        test_measurement_ids = []
        
        # テスト18: BodyMeasurementManagement.AddBodyMeasurement (複数記録)
        print("\n--- 18. BodyMeasurementManagement.AddBodyMeasurement テスト ---")
        try:
            # 1回目の記録（最古になる予定）- 2時間前
            time_1 = (datetime.now() - timedelta(hours=2)).isoformat()
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "BodyMeasurementManagement___AddBodyMeasurement",
                    "arguments": {
                        "userId": self.user_id,
                        "weight": 65.0,
                        "height": 170.0,
                        "body_fat_percentage": 15.0,
                        "measurement_time": time_1
                    }
                },
                "id": 18
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ AddBodyMeasurement(1回目)失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ AddBodyMeasurement(1回目)成功")
                    # measurement_idを保存
                    if 'result' in result and 'content' in result['result']:
                        content = result['result']['content']
                        if content and isinstance(content, list) and len(content) > 0:
                            text_content = content[0].get('text', '')
                            if text_content:
                                try:
                                    parsed_content = json.loads(text_content)
                                    if 'measurementId' in parsed_content:
                                        test_measurement_ids.append(parsed_content['measurementId'])
                                        print(f"   保存されたmeasurement_id: {parsed_content['measurementId']}")
                                except json.JSONDecodeError:
                                    pass
            else:
                print(f"❌ AddBodyMeasurement(1回目)失敗: HTTP {response.status_code}")
                success = False
            
            # 2回目の記録（中間）- 1時間前
            time_2 = (datetime.now() - timedelta(hours=1)).isoformat()
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "BodyMeasurementManagement___AddBodyMeasurement",
                    "arguments": {
                        "userId": self.user_id,
                        "weight": 66.0,
                        "height": 171.0,
                        "body_fat_percentage": 16.0,
                        "measurement_time": time_2
                    }
                },
                "id": 18
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ AddBodyMeasurement(2回目)失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ AddBodyMeasurement(2回目)成功")
                    # measurement_idを保存
                    if 'result' in result and 'content' in result['result']:
                        content = result['result']['content']
                        if content and isinstance(content, list) and len(content) > 0:
                            text_content = content[0].get('text', '')
                            if text_content:
                                try:
                                    parsed_content = json.loads(text_content)
                                    if 'measurementId' in parsed_content:
                                        test_measurement_ids.append(parsed_content['measurementId'])
                                        print(f"   保存されたmeasurement_id: {parsed_content['measurementId']}")
                                except json.JSONDecodeError:
                                    pass
            else:
                print(f"❌ AddBodyMeasurement(2回目)失敗: HTTP {response.status_code}")
                success = False
            
            # 3回目の記録（最新になる予定）- 現在時刻
            time_3 = datetime.now().isoformat()
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "BodyMeasurementManagement___AddBodyMeasurement",
                    "arguments": {
                        "userId": self.user_id,
                        "weight": 67.0,
                        "height": 172.0,
                        "body_fat_percentage": 17.0,
                        "measurement_time": time_3
                    }
                },
                "id": 18
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ AddBodyMeasurement(3回目)失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ AddBodyMeasurement(3回目)成功")
                    # measurement_idを保存
                    if 'result' in result and 'content' in result['result']:
                        content = result['result']['content']
                        if content and isinstance(content, list) and len(content) > 0:
                            text_content = content[0].get('text', '')
                            if text_content:
                                try:
                                    parsed_content = json.loads(text_content)
                                    if 'measurementId' in parsed_content:
                                        test_measurement_ids.append(parsed_content['measurementId'])
                                        print(f"   保存されたmeasurement_id: {parsed_content['measurementId']}")
                                except json.JSONDecodeError:
                                    pass
            else:
                print(f"❌ AddBodyMeasurement(3回目)失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ AddBodyMeasurement例外: {str(e)}")
            success = False
        
        # テスト19: BodyMeasurementManagement.GetLatestMeasurements
        print("\n--- 19. BodyMeasurementManagement.GetLatestMeasurements テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "BodyMeasurementManagement___GetLatestMeasurements",
                    "arguments": {
                        "userId": self.user_id
                    }
                },
                "id": 19
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ GetLatestMeasurements失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ GetLatestMeasurements成功")
                    # 最新値が67.0であることを確認
                    if 'result' in result and 'content' in result['result']:
                        content = result['result']['content']
                        if content and isinstance(content, list) and len(content) > 0:
                            text_content = content[0].get('text', '')
                            if text_content:
                                try:
                                    parsed_content = json.loads(text_content)
                                    measurements = parsed_content.get('measurements', {})
                                    latest_weight = measurements.get('weight')
                                    if latest_weight == 67.0:
                                        print(f"   ✅ 最新体重確認: {latest_weight}kg")
                                    else:
                                        print(f"   ⚠️ 最新体重が期待値と異なります: 期待67.0kg, 実際{latest_weight}kg")
                                except json.JSONDecodeError:
                                    pass
            else:
                print(f"❌ GetLatestMeasurements失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ GetLatestMeasurements例外: {str(e)}")
            success = False
        
        # テスト20: BodyMeasurementManagement.GetOldestMeasurements
        print("\n--- 20. BodyMeasurementManagement.GetOldestMeasurements テスト ---")
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "BodyMeasurementManagement___GetOldestMeasurements",
                    "arguments": {
                        "userId": self.user_id
                    }
                },
                "id": 20
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ GetOldestMeasurements失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ GetOldestMeasurements成功")
                    # 最古値が65.0であることを確認
                    if 'result' in result and 'content' in result['result']:
                        content = result['result']['content']
                        if content and isinstance(content, list) and len(content) > 0:
                            text_content = content[0].get('text', '')
                            if text_content:
                                try:
                                    parsed_content = json.loads(text_content)
                                    measurements = parsed_content.get('measurements', {})
                                    oldest_weight = measurements.get('weight')
                                    if oldest_weight == 65.0:
                                        print(f"   ✅ 最古体重確認: {oldest_weight}kg")
                                    else:
                                        print(f"   ⚠️ 最古体重が期待値と異なります: 期待65.0kg, 実際{oldest_weight}kg")
                                except json.JSONDecodeError:
                                    pass
            else:
                print(f"❌ GetOldestMeasurements失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ GetOldestMeasurements例外: {str(e)}")
            success = False
        
        # テスト21: BodyMeasurementManagement.GetMeasurementHistory
        print("\n--- 21. BodyMeasurementManagement.GetMeasurementHistory テスト ---")
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "BodyMeasurementManagement___GetMeasurementHistory",
                    "arguments": {
                        "userId": self.user_id,
                        "start_date": yesterday,
                        "end_date": today,
                        "limit": 10
                    }
                },
                "id": 21
            }
            
            response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"❌ GetMeasurementHistory失敗: {result['error']}")
                    success = False
                else:
                    print(f"✅ GetMeasurementHistory成功")
                    # 3件の記録があることを確認
                    if 'result' in result and 'content' in result['result']:
                        content = result['result']['content']
                        if content and isinstance(content, list) and len(content) > 0:
                            text_content = content[0].get('text', '')
                            if text_content:
                                try:
                                    parsed_content = json.loads(text_content)
                                    measurements = parsed_content.get('measurements', [])
                                    count = parsed_content.get('count', 0)
                                    if count >= 3:
                                        print(f"   ✅ 測定記録数確認: {count}件")
                                    else:
                                        print(f"   ⚠️ 測定記録数が期待値より少ないです: 期待3件以上, 実際{count}件")
                                except json.JSONDecodeError:
                                    pass
            else:
                print(f"❌ GetMeasurementHistory失敗: HTTP {response.status_code}")
                success = False
                
        except Exception as e:
            print(f"❌ GetMeasurementHistory例外: {str(e)}")
            success = False
        
        # テスト22: BodyMeasurementManagement.UpdateBodyMeasurement
        print("\n--- 22. BodyMeasurementManagement.UpdateBodyMeasurement テスト ---")
        try:
            if len(test_measurement_ids) >= 3:
                # 最新の記録（3回目）を更新
                latest_measurement_id = test_measurement_ids[2]
                
                mcp_request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "BodyMeasurementManagement___UpdateBodyMeasurement",
                        "arguments": {
                            "userId": self.user_id,
                            "measurement_id": latest_measurement_id,
                            "weight": 68.5  # 67.0から68.5に更新
                        }
                    },
                    "id": 22
                }
                
                response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'error' in result:
                        print(f"❌ UpdateBodyMeasurement失敗: {result['error']}")
                        success = False
                    else:
                        print(f"✅ UpdateBodyMeasurement成功")
                        
                        # 最新値が更新されていることを確認
                        latest_request = {
                            "jsonrpc": "2.0",
                            "method": "tools/call",
                            "params": {
                                "name": "BodyMeasurementManagement___GetLatestMeasurements",
                                "arguments": {
                                    "userId": self.user_id
                                }
                            },
                            "id": 22
                        }
                        
                        latest_response = requests.post(mcp_endpoint, headers=headers, json=latest_request, timeout=30)
                        
                        if latest_response.status_code == 200:
                            latest_result = latest_response.json()
                            if 'result' in latest_result and 'content' in latest_result['result']:
                                content = latest_result['result']['content']
                                if content and isinstance(content, list) and len(content) > 0:
                                    text_content = content[0].get('text', '')
                                    if text_content:
                                        try:
                                            parsed_content = json.loads(text_content)
                                            measurements = parsed_content.get('measurements', {})
                                            updated_weight = measurements.get('weight')
                                            if updated_weight == 68.5:
                                                print(f"   ✅ Latest値更新確認: {updated_weight}kg")
                                            else:
                                                print(f"   ❌ Latest値が更新されていません: 期待68.5kg, 実際{updated_weight}kg")
                                                success = False
                                        except json.JSONDecodeError:
                                            pass
                else:
                    print(f"❌ UpdateBodyMeasurement失敗: HTTP {response.status_code}")
                    success = False
            else:
                print("⚠️ UpdateBodyMeasurement スキップ: measurement_idが不足しています")
                
        except Exception as e:
            print(f"❌ UpdateBodyMeasurement例外: {str(e)}")
            success = False
        
        # テスト23: BodyMeasurementManagement.DeleteBodyMeasurement
        print("\n--- 23. BodyMeasurementManagement.DeleteBodyMeasurement テスト ---")
        try:
            if len(test_measurement_ids) >= 3:
                # 最古の記録（1回目）を削除
                oldest_measurement_id = test_measurement_ids[0]
                
                mcp_request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "BodyMeasurementManagement___DeleteBodyMeasurement",
                        "arguments": {
                            "userId": self.user_id,
                            "measurement_id": oldest_measurement_id
                        }
                    },
                    "id": 23
                }
                
                response = requests.post(mcp_endpoint, headers=headers, json=mcp_request, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'error' in result:
                        print(f"❌ DeleteBodyMeasurement失敗: {result['error']}")
                        success = False
                    else:
                        print(f"✅ DeleteBodyMeasurement成功")
                        
                        # 最古値が更新されていることを確認（2回目の記録が新しい最古になる）
                        oldest_request = {
                            "jsonrpc": "2.0",
                            "method": "tools/call",
                            "params": {
                                "name": "BodyMeasurementManagement___GetOldestMeasurements",
                                "arguments": {
                                    "userId": self.user_id
                                }
                            },
                            "id": 23
                        }
                        
                        oldest_response = requests.post(mcp_endpoint, headers=headers, json=oldest_request, timeout=30)
                        
                        if oldest_response.status_code == 200:
                            oldest_result = oldest_response.json()
                            if 'result' in oldest_result and 'content' in oldest_result['result']:
                                content = oldest_result['result']['content']
                                if content and isinstance(content, list) and len(content) > 0:
                                    text_content = content[0].get('text', '')
                                    if text_content:
                                        try:
                                            parsed_content = json.loads(text_content)
                                            measurements = parsed_content.get('measurements', {})
                                            new_oldest_weight = measurements.get('weight')
                                            if new_oldest_weight == 66.0:  # 2回目の記録が新しい最古
                                                print(f"   ✅ Oldest値更新確認: {new_oldest_weight}kg")
                                            else:
                                                print(f"   ❌ Oldest値が正しく更新されていません: 期待66.0kg, 実際{new_oldest_weight}kg")
                                                success = False
                                        except json.JSONDecodeError:
                                            pass
                else:
                    print(f"❌ DeleteBodyMeasurement失敗: HTTP {response.status_code}")
                    success = False
            else:
                print("⚠️ DeleteBodyMeasurement スキップ: measurement_idが不足しています")
                
        except Exception as e:
            print(f"❌ DeleteBodyMeasurement例外: {str(e)}")
            success = False
        
        print(f"\n🏁 全23ツールのテスト完了")
        return success
    

    def run_tests(self) -> bool:
        """全テストを実行（M2M認証版）"""
        print("🚀 HealthManagerMCP M2M認証テスト開始（全23ツール）")
        print(f"🌍 Environment: {ENVIRONMENT}")
        print(f"📦 Stack Name: {STACK_NAME}")
        print("=" * 60)
        
        success = True
        
        # 1. M2M認証
        if not self.authenticate_m2m():
            return False
        
        # 2. MCP接続テスト
        if not self.test_mcp_connection():
            success = False
        
        # 3. MCPツール呼び出しテスト（全23ツール）
        if not self.test_mcp_tools():
            success = False
        
        print("=" * 60)
        if success:
            print("✅ 全M2M認証テスト完了（23ツール全て成功）")
        else:
            print("⚠️  一部テストで問題が発生しました")
        
        return success

def main():
    """メイン関数"""
    # 環境情報を表示
    print(f"🌍 Environment: {ENVIRONMENT}")
    print(f"📦 Stack Name: {STACK_NAME}")
    print(f"🏷️  Environment Suffix: {ENVIRONMENT_SUFFIX}")
    print()
    
    # 必要なライブラリをチェック
    try:
        import requests
    except ImportError:
        print("❌ requests ライブラリが必要です: pip install requests")
        sys.exit(1)
    
    # M2M認証テスト実行
    client = HealthManagerMCPTestClient()
    success = client.run_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()