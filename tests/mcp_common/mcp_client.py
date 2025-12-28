"""
MCP通信クライアントモジュール

MCPプロトコル通信、エラーハンドリング、リトライ機能を提供します。
"""

import requests
import json
import time
from typing import Dict, Any, Optional, List
from .auth_client import AuthClient
from .config import Config, TestConfig


class MCPClient:
    """MCP通信クライアント"""
    
    def __init__(self, auth_client: AuthClient, config: Config):
        self.auth_client = auth_client
        self.config = config
        self.test_config = config.get_test_config()
        self.gateway_endpoint = self.test_config.gateway_endpoint
        self.session = requests.Session()
        
        # デフォルトヘッダーを設定
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'HealthManager-MCP-TestClient/1.0'
        })
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout: int = None) -> Dict[str, Any]:
        """MCPツールを呼び出し"""
        if timeout is None:
            timeout = self.test_config.timeout_seconds
        
        # 認証トークンを取得
        try:
            access_token = self.auth_client.get_access_token()
        except Exception as e:
            return {
                "success": False,
                "error": "AUTHENTICATION_ERROR",
                "message": f"認証エラー: {str(e)}"
            }
        
        # MCPプロトコル形式でリクエストペイロードを構築（元の実装と同じ形式）
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": 1
        }
        
        # リクエストヘッダーを設定
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # MCPエンドポイント（/mcpパスを追加）
        mcp_endpoint = f"{self.gateway_endpoint}/mcp"
        
        # リトライ機能付きでリクエストを実行
        return self._execute_request_with_retry(payload, headers, timeout, mcp_endpoint)
    
    def _execute_request_with_retry(self, payload: Dict[str, Any], headers: Dict[str, str], timeout: int, endpoint: str, max_retries: int = 3) -> Dict[str, Any]:
        """リトライ機能付きリクエスト実行"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                if self.test_config.debug_mode:
                    print(f"🔄 MCP呼び出し試行 {attempt + 1}/{max_retries}")
                    print(f"📤 Endpoint: {endpoint}")
                    print(f"📤 Method: {payload.get('method')}")
                    print(f"📤 Tool: {payload.get('params', {}).get('name')}")
                    print(f"📤 Arguments: {json.dumps(payload.get('params', {}).get('arguments', {}), indent=2, ensure_ascii=False)}")
                
                response = self.session.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
                
                if self.test_config.debug_mode:
                    print(f"📥 Status: {response.status_code}")
                    print(f"📥 Response: {response.text[:500]}...")
                
                # HTTPステータスコードをチェック
                if response.status_code == 401:
                    # 認証エラーの場合、トークンを再取得して再試行
                    if attempt < max_retries - 1:
                        print("🔄 認証エラー、トークンを再取得して再試行...")
                        if self.auth_client.authenticate_m2m():
                            headers['Authorization'] = f'Bearer {self.auth_client.get_access_token()}'
                            continue
                    
                    return {
                        "success": False,
                        "error": "AUTHENTICATION_ERROR",
                        "message": "認証に失敗しました"
                    }
                
                elif response.status_code == 429:
                    # レート制限の場合、待機して再試行
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 指数バックオフ
                        print(f"⏳ レート制限、{wait_time}秒待機して再試行...")
                        time.sleep(wait_time)
                        continue
                
                elif response.status_code >= 500:
                    # サーバーエラーの場合、待機して再試行
                    if attempt < max_retries - 1:
                        wait_time = 1 + attempt
                        print(f"⏳ サーバーエラー、{wait_time}秒待機して再試行...")
                        time.sleep(wait_time)
                        continue
                
                # レスポンスを解析
                try:
                    response_data = response.json()
                    
                    # MCPレスポンス形式を標準化（元の実装に合わせる）
                    if response.status_code == 200:
                        # JSON-RPC 2.0レスポンスの場合
                        if 'result' in response_data:
                            return {
                                "success": True,
                                "data": response_data,
                                "status_code": response.status_code
                            }
                        # エラーレスポンスの場合
                        elif 'error' in response_data:
                            return {
                                "success": False,
                                "error": response_data['error'].get('code', 'MCP_ERROR'),
                                "message": response_data['error'].get('message', 'MCPエラーが発生しました'),
                                "data": response_data,
                                "status_code": response.status_code
                            }
                        else:
                            return {
                                "success": True,
                                "data": response_data,
                                "status_code": response.status_code
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP_{response.status_code}",
                            "message": response_data.get("message", f"HTTPエラー: {response.status_code}"),
                            "data": response_data,
                            "status_code": response.status_code
                        }
                        
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "RESPONSE_PARSE_ERROR",
                        "message": f"レスポンス解析エラー: {response.text[:200]}",
                        "status_code": response.status_code
                    }
                
            except requests.exceptions.Timeout:
                last_error = f"タイムアウト（{timeout}秒）"
                if attempt < max_retries - 1:
                    print(f"⏳ タイムアウト、再試行...")
                    continue
                    
            except requests.exceptions.ConnectionError as e:
                last_error = f"接続エラー: {str(e)}"
                if attempt < max_retries - 1:
                    wait_time = 1 + attempt
                    print(f"⏳ 接続エラー、{wait_time}秒待機して再試行...")
                    time.sleep(wait_time)
                    continue
                    
            except Exception as e:
                last_error = f"予期しないエラー: {str(e)}"
                break
        
        # 全ての試行が失敗した場合
        return {
            "success": False,
            "error": "REQUEST_FAILED",
            "message": f"リクエスト失敗（{max_retries}回試行）: {last_error}"
        }
    
    def list_tools(self) -> List[str]:
        """利用可能なツールリストを取得"""
        try:
            # MCPプロトコルでツールリストを取得
            mcp_endpoint = f"{self.gateway_endpoint}/mcp"
            
            # 認証トークンを取得
            access_token = self.auth_client.get_access_token()
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # MCPプロトコル: ツールリスト取得
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            }
            
            response = self.session.post(
                mcp_endpoint,
                json=payload,
                headers=headers,
                timeout=self.test_config.timeout_seconds
            )
            
            if response.status_code == 200:
                mcp_response = response.json()
                if 'result' in mcp_response and 'tools' in mcp_response['result']:
                    tools = mcp_response['result']['tools']
                    return [tool['name'] for tool in tools]
            
            print(f"⚠️ ツールリスト取得失敗: HTTP {response.status_code}")
            return []
            
        except Exception as e:
            print(f"⚠️ ツールリスト取得例外: {str(e)}")
            return []
    
    def test_connection(self) -> bool:
        """MCP接続をテスト"""
        try:
            # MCPプロトコルでツールリスト取得をテスト
            mcp_endpoint = f"{self.gateway_endpoint}/mcp"
            
            # 認証トークンを取得
            access_token = self.auth_client.get_access_token()
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # MCPプロトコル: ツールリスト取得
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            }
            
            print(f"🔗 MCP接続テスト: {mcp_endpoint}")
            
            response = self.session.post(
                mcp_endpoint,
                json=payload,
                headers=headers,
                timeout=self.test_config.timeout_seconds
            )
            
            if response.status_code == 200:
                mcp_response = response.json()
                print("✅ MCP接続成功")
                
                if 'result' in mcp_response and 'tools' in mcp_response['result']:
                    tools = mcp_response['result']['tools']
                    print(f"   利用可能なツール数: {len(tools)}")
                    
                    # ツールリストを表示
                    print("   利用可能なツール:")
                    for tool in tools[:5]:  # 最初の5つだけ表示
                        print(f"     - {tool['name']}: {tool.get('description', 'No description')}")
                    if len(tools) > 5:
                        print(f"     ... 他 {len(tools) - 5} ツール")
                else:
                    print("   ツールリストが見つかりません")
                
                return True
            else:
                print(f"❌ MCP接続失敗: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"⚠️ 接続テスト例外: {str(e)}")
            return False