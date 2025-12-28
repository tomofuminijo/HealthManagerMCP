"""
設定管理モジュール

CloudFormation出力の動的取得と環境変数からの設定読み込みを提供します。
"""

import os
import sys
import boto3
from typing import Dict, Any, Optional
from dataclasses import dataclass

# CDK環境設定モジュールのインポート
sys.path.append(os.path.join(os.path.dirname(__file__), '../../cdk'))
from cdk.environment.configuration_provider import ConfigurationProvider
from cdk.environment.environment_manager import EnvironmentManager


@dataclass
class TestConfig:
    """テスト設定データクラス"""
    environment: str
    aws_region: str
    stack_name: str
    gateway_endpoint: str
    cognito_user_pool_id: str
    cognito_client_id: str
    cognito_client_secret: Optional[str] = None
    timeout_seconds: int = 30
    debug_mode: bool = False


class Config:
    """設定管理クラス"""
    
    def __init__(self):
        self.config_provider = ConfigurationProvider("HealthManager")
        self.cloudformation_client = boto3.client(
            'cloudformation', 
            region_name=self.get_aws_region()
        )
        self._cloudformation_outputs = None
        self._load_cloudformation_outputs()
    
    def get_environment(self) -> str:
        """環境名を取得"""
        return EnvironmentManager.get_environment()
    
    def get_aws_region(self) -> str:
        """AWSリージョンを取得"""
        return self.config_provider.get_aws_region()
    
    def get_stack_name(self) -> str:
        """CloudFormationスタック名を取得"""
        return self.config_provider.get_stack_name("Healthmate-HealthManagerStack")
    
    def _load_cloudformation_outputs(self) -> None:
        """CloudFormation StackのOutputsから設定を動的に取得"""
        try:
            stack_name = self.get_stack_name()
            print(f"🔧 CloudFormation Stack '{stack_name}' から設定を取得中...")
            print(f"🌍 Environment: {self.get_environment()}")
            
            response = self.cloudformation_client.describe_stacks(StackName=stack_name)
            stack = response['Stacks'][0]
            self._cloudformation_outputs = {
                output['OutputKey']: output['OutputValue'] 
                for output in stack.get('Outputs', [])
            }
            
            print(f"✅ CloudFormation設定取得完了")
            
        except Exception as e:
            print(f"❌ CloudFormation設定取得エラー: {str(e)}")
            self._cloudformation_outputs = {}
    
    def get_gateway_endpoint(self) -> str:
        """Gateway エンドポイントを取得（/mcpパスを除去してベースURLを取得）"""
        endpoint = self._cloudformation_outputs.get('GatewayEndpoint')
        if not endpoint:
            raise ValueError("GatewayEndpoint がCloudFormation Outputsに見つかりません")
        
        # /mcpパスを除去してベースURLを取得（元の実装と同じ処理）
        if endpoint.endswith('/mcp'):
            endpoint = endpoint[:-4]
        
        return endpoint
    
    def get_cognito_config(self) -> Dict[str, str]:
        """Cognito設定を取得"""
        user_pool_id = self._cloudformation_outputs.get('UserPoolId')
        client_id = self._cloudformation_outputs.get('UserPoolClientId')
        
        if not all([user_pool_id, client_id]):
            missing = []
            if not user_pool_id:
                missing.append('UserPoolId')
            if not client_id:
                missing.append('UserPoolClientId')
            raise ValueError(f"Cognito設定が不足しています: {', '.join(missing)}")
        
        return {
            'user_pool_id': user_pool_id,
            'client_id': client_id
        }
    
    def get_test_config(self) -> TestConfig:
        """テスト設定を取得"""
        cognito_config = self.get_cognito_config()
        
        return TestConfig(
            environment=self.get_environment(),
            aws_region=self.get_aws_region(),
            stack_name=self.get_stack_name(),
            gateway_endpoint=self.get_gateway_endpoint(),
            cognito_user_pool_id=cognito_config['user_pool_id'],
            cognito_client_id=cognito_config['client_id'],
            cognito_client_secret=None,  # 動的に取得するためNoneに設定
            timeout_seconds=int(os.environ.get('MCP_TIMEOUT_SECONDS', '30')),
            debug_mode=True  # デバッグモードを有効にして通信内容を確認
        )
    
    def get_cloudformation_outputs(self) -> Dict[str, str]:
        """全てのCloudFormation Outputsを取得"""
        return self._cloudformation_outputs.copy()