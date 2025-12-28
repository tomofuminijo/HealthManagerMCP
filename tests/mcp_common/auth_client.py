"""
認証クライアントモジュール

Cognito M2M認証（Client Credentials Flow）とJWTトークンの自動管理を提供します。
"""

import boto3
import hashlib
import hmac
import base64
import json
import requests
from datetime import datetime, timedelta
from typing import Optional
from .config import Config, TestConfig


class AuthClient:
    """Cognito M2M認証クライアント"""
    
    def __init__(self, config: Config):
        self.config = config
        self.test_config = config.get_test_config()
        self.cognito_client = boto3.client('cognito-idp', region_name=self.test_config.aws_region)
        self.access_token = None
        self.token_expires_at = None
    
    def _get_client_secret(self) -> str:
        """Cognito User Pool ClientのSecretを動的に取得"""
        try:
            print("🔐 Cognito Client Secretを取得中...")
            
            response = self.cognito_client.describe_user_pool_client(
                UserPoolId=self.test_config.cognito_user_pool_id,
                ClientId=self.test_config.cognito_client_id
            )
            
            client_secret = response['UserPoolClient'].get('ClientSecret')
            
            if client_secret:
                print(f"✅ Client Secret取得完了: {client_secret[:10]}...")
                return client_secret
            else:
                raise ValueError("Client Secretが設定されていません")
                
        except Exception as e:
            print(f"❌ Client Secret取得失敗: {str(e)}")
            raise
    
    def _calculate_secret_hash(self, username: str) -> str:
        """Cognito Client Secret Hashを計算"""
        client_secret = self._get_client_secret()
        
        message = username + self.test_config.cognito_client_id
        dig = hmac.new(
            client_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(dig).decode()
    
    def authenticate_m2m(self) -> bool:
        """M2M認証（Client Credentials Flow）でJWTトークンを取得"""
        try:
            print("🔐 M2M認証（Client Credentials Flow）実行中...")
            
            # Client Secretを動的に取得
            client_secret = self._get_client_secret()
            
            # 環境別のOAuth2 Token Endpointを構築
            cognito_domain = f"healthmanager-m2m-auth{self.config.config_provider.get_environment_suffix()}"
            oauth_token_url = f"https://{cognito_domain}.auth.{self.test_config.aws_region}.amazoncognito.com/oauth2/token"
            
            # Basic認証用のCredentials
            auth_string = f"{self.test_config.cognito_client_id}:{client_secret}"
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
            print(f"🌍 Environment: {self.test_config.environment}")
            
            import requests
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
                    # トークンの有効期限を設定
                    expires_in = token_response.get('expires_in', 3600)
                    self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)  # 5分前に期限切れとして扱う
                    
                    print(f"✅ M2M認証成功")
                    print(f"   Access Token: {self.access_token[:20]}...")
                    print(f"   Token Type: {token_response.get('token_type', 'Bearer')}")
                    print(f"   Expires In: {expires_in} seconds")
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
            print(f"❌ M2M認証エラー: {str(e)}")
            
            # フォールバック: 開発環境用の簡易認証
            if self.test_config.environment == 'dev':
                print("🔄 開発環境用フォールバック認証を試行...")
                return self._fallback_auth()
            
            return False
    
    def _fallback_auth(self) -> bool:
        """開発環境用フォールバック認証"""
        try:
            # 開発環境では簡易的なダミートークンを生成
            # 実際の環境では適切なM2M認証を実装する必要があります
            dummy_payload = {
                "sub": "mcp-test-client",
                "aud": self.test_config.cognito_client_id,
                "iss": f"https://cognito-idp.{self.test_config.aws_region}.amazonaws.com/{self.test_config.cognito_user_pool_id}",
                "exp": int((datetime.now() + timedelta(hours=1)).timestamp()),
                "iat": int(datetime.now().timestamp()),
                "token_use": "access"
            }
            
            # Base64エンコードされたダミーJWT（署名なし）
            header = base64.b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip('=')
            payload = base64.b64encode(json.dumps(dummy_payload).encode()).decode().rstrip('=')
            
            self.access_token = f"{header}.{payload}."
            self.token_expires_at = datetime.now() + timedelta(minutes=55)
            
            print("⚠️ 開発環境用ダミートークンを生成しました")
            return True
            
        except Exception as e:
            print(f"❌ フォールバック認証エラー: {str(e)}")
            return False
    
    def get_access_token(self) -> str:
        """有効なアクセストークンを取得"""
        if not self.is_token_valid():
            if not self.authenticate_m2m():
                raise RuntimeError("認証に失敗しました")
        
        return self.access_token
    
    def is_token_valid(self) -> bool:
        """トークンの有効性を確認"""
        if not self.access_token or not self.token_expires_at:
            return False
        
        return datetime.now() < self.token_expires_at
    
    def refresh_token_if_needed(self) -> bool:
        """必要に応じてトークンを更新"""
        if not self.is_token_valid():
            return self.authenticate_m2m()
        return True