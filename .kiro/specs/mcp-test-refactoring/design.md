# Design Document

## Overview

Healthmate-HealthManagerサービスの`test_mcp_client.py`ファイル（2600行以上）を、保守性と可読性を向上させるために複数の専門化されたモジュールにリファクタリングする。MCPテスト専用のフォルダ構造を作成し、各XXXManager毎にテストを分離し、共通機能を抽出して、効率的なテストシナリオを実装する。

## Architecture

### 拡張可能なフォルダ構造設計

```
tests/
├── __init__.py                           # Pythonパッケージ化
├── mcp_common/                           # 共通機能モジュール
│   ├── __init__.py
│   ├── auth_client.py                    # Cognito M2M認証クライアント
│   ├── mcp_client.py                     # MCP通信クライアント
│   ├── test_utils.py                     # テスト用ユーティリティ
│   ├── config.py                         # 設定管理
│   ├── base_manager_test.py              # Manager テストの基底クラス
│   └── manager_registry.py               # Manager自動発見・登録システム
├── mcp_managers/                         # 各Manager専用テスト
│   ├── __init__.py
│   ├── test_user_management.py           # UserManagement (3ツール)
│   ├── test_health_goal_management.py    # HealthGoalManagement (4ツール)
│   ├── test_health_policy_management.py  # HealthPolicyManagement (4ツール)
│   ├── test_activity_management.py       # ActivityManagement (6ツール)
│   ├── test_body_measurement_management.py # BodyMeasurementManagement (6ツール)
│   ├── test_health_concern_management.py # HealthConcernManagement (4ツール)
│   ├── test_journal_management.py        # JournalManagement (5ツール)
│   ├── test_health_observation_management.py # HealthObservationManagement (6ツール)
│   └── [future_manager_tests.py]         # 将来追加されるManagerテスト
└── mcp_integration/                      # 統合テスト
    ├── __init__.py
    ├── test_all_managers.py              # 全Manager統合テスト + HolisticUserDataService
    └── manager_discovery.py              # Manager自動発見機能
```

### 拡張性を考慮したアーキテクチャ特徴

1. **Manager自動発見システム**: 新しいManagerテストファイルを追加するだけで自動的に統合テストに組み込まれる
2. **プラグイン型アーキテクチャ**: 各Managerテストは独立したプラグインとして動作
3. **設定駆動型テスト**: 新しいツールの追加は設定ファイルの更新のみで対応
4. **標準化されたインターフェース**: 全てのManagerテストが同じインターフェースを実装

## 拡張性の特徴

### 1. 新しいManagerテストの追加が簡単
- **ファイル追加のみ**: `tests/mcp_managers/test_new_manager.py` を作成するだけ
- **自動発見**: ManagerRegistryが新しいテストクラスを自動発見
- **自動統合**: AllManagersTestが自動的に新しいテストを実行
- **設定不要**: 既存のコードを変更する必要なし

### 2. 標準化されたインターフェース
- **BaseManagerTest**: 全てのManagerテストが同じインターフェースを実装
- **テンプレートメソッドパターン**: 共通の実行フローを提供
- **抽象メソッド**: 必要な情報を強制的に定義

### 3. 自動化されたテストライフサイクル
- **自動実行**: ツールリストに基づいてテストメソッドを自動実行
- **自動クリーンアップ**: 削除ツールマッピングに基づいて自動削除
- **自動レポート**: テスト結果を自動集計・表示

### 4. 設定駆動型の拡張
- **ツールリスト**: 新しいツールは配列に追加するだけ
- **削除マッピング**: 削除ツールは辞書に追加するだけ
- **動的実行**: 設定に基づいて動的にテストを実行

### 5. 将来の拡張例
```python
# 新しいManagerテストの追加例
class NotificationManagementTest(BaseManagerTest):
    def get_manager_name(self) -> str:
        return "NotificationManagement"
    
    def get_tool_list(self) -> List[str]:
        return [
            "NotificationManagement___SendNotification",
            "NotificationManagement___GetNotifications",
            "NotificationManagement___MarkAsRead"
        ]
    
    def get_cleanup_tools(self) -> Dict[str, str]:
        return {}  # 削除ツールなし
    
    # テストメソッドを実装するだけで完了
```

この設計により、将来的にツールが増えても：
1. 新しいファイルを1つ作成
2. BaseManagerTestを継承
3. 必要なメソッドを実装

これだけで自動的に統合テストに組み込まれ、HolisticUserDataServiceでの検証も含めた完全なテストが実行されます。

## Components and Interfaces

### 1. 共通機能コンポーネント (mcp_common)

#### AuthClient クラス
```python
class AuthClient:
    """Cognito M2M認証クライアント"""
    
    def __init__(self, config: Config):
        self.config = config
        self.cognito_client = boto3.client('cognito-idp')
        self.access_token = None
    
    def authenticate_m2m(self) -> bool:
        """M2M認証（Client Credentials Flow）でJWTトークンを取得"""
        
    def get_access_token(self) -> str:
        """有効なアクセストークンを取得"""
        
    def is_token_valid(self) -> bool:
        """トークンの有効性を確認"""
```

#### MCPClient クラス
```python
class MCPClient:
    """MCP通信クライアント"""
    
    def __init__(self, auth_client: AuthClient, config: Config):
        self.auth_client = auth_client
        self.config = config
        self.gateway_endpoint = config.get_gateway_endpoint()
    
    def call_tool(self, tool_name: str, arguments: dict, timeout: int = 30) -> dict:
        """MCPツールを呼び出し"""
        
    def list_tools(self) -> list:
        """利用可能なツールリストを取得"""
        
    def test_connection(self) -> bool:
        """MCP接続をテスト"""
```

#### TestUtils クラス
```python
class TestUtils:
    """テスト用ユーティリティ"""
    
    @staticmethod
    def generate_test_user_id() -> str:
        """テスト用ユーザーIDを生成 (test-user-{8桁})"""
        
    @staticmethod
    def parse_mcp_response(response: dict) -> dict:
        """MCPレスポンスを解析"""
        
    @staticmethod
    def validate_response_success(response: dict) -> bool:
        """レスポンスの成功を検証"""
        
    @staticmethod
    def extract_id_from_response(response: dict, id_field: str) -> str:
        """レスポンスからIDを抽出"""
```

#### Config クラス
```python
class Config:
    """設定管理"""
    
    def __init__(self):
        self.environment = self._get_environment()
        self.aws_region = self._get_aws_region()
        self.stack_name = self._get_stack_name()
        self._load_cloudformation_outputs()
    
    def get_gateway_endpoint(self) -> str:
        """Gateway エンドポイントを取得"""
        
    def get_cognito_config(self) -> dict:
        """Cognito設定を取得"""
        
    def get_test_config(self) -> dict:
        """テスト設定を取得"""
```

### 2. Manager専用テストコンポーネント (mcp_managers) - 拡張可能設計

#### BaseManagerTest クラス（拡張可能設計）
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseManagerTest(ABC):
    """Manager テストの基底クラス（拡張可能設計）"""
    
    def __init__(self, mcp_client: MCPClient, test_user_id: str):
        self.mcp_client = mcp_client
        self.test_user_id = test_user_id
        self.created_ids = []  # 削除対象IDを記録
        self.test_results = {}
    
    @abstractmethod
    def get_manager_name(self) -> str:
        """Managerの名前を返す（例: "UserManagement"）"""
        pass
    
    @abstractmethod
    def get_tool_list(self) -> List[str]:
        """テスト対象ツールのリストを返す"""
        pass
    
    @abstractmethod
    def get_cleanup_tools(self) -> Dict[str, str]:
        """削除ツールのマッピングを返す（作成ツール名: 削除ツール名）"""
        pass
    
    def setup(self):
        """テスト前のセットアップ"""
        
    def teardown(self):
        """テスト後のクリーンアップ"""
        
    def run_tests(self) -> bool:
        """テストを実行（テンプレートメソッドパターン）"""
        try:
            self.setup()
            success = self._execute_tool_tests()
            self.cleanup_test_data()
            return success
        finally:
            self.teardown()
    
    def _execute_tool_tests(self) -> bool:
        """各ツールのテストを実行（自動化）"""
        success = True
        for tool_name in self.get_tool_list():
            method_name = f"test_{tool_name.lower().replace('___', '_')}"
            if hasattr(self, method_name):
                test_method = getattr(self, method_name)
                try:
                    result = test_method()
                    self.test_results[tool_name] = result
                    if not result:
                        success = False
                except Exception as e:
                    self.test_results[tool_name] = False
                    success = False
                    print(f"❌ {tool_name} テスト例外: {str(e)}")
        return success
    
    def cleanup_test_data(self):
        """テストデータを削除（自動化）"""
        cleanup_tools = self.get_cleanup_tools()
        for created_tool, cleanup_tool in cleanup_tools.items():
            if cleanup_tool and created_tool in self.test_results:
                self._execute_cleanup(cleanup_tool)

#### ManagerRegistry クラス（自動発見システム）
```python
import importlib
import pkgutil
from typing import List, Type

class ManagerRegistry:
    """Manager自動発見・登録システム"""
    
    @staticmethod
    def discover_manager_tests() -> List[Type[BaseManagerTest]]:
        """mcp_managersフォルダから全てのManagerテストクラスを自動発見"""
        manager_tests = []
        
        # mcp_managersパッケージ内の全モジュールを検索
        import tests.mcp_managers as managers_package
        
        for importer, modname, ispkg in pkgutil.iter_modules(managers_package.__path__):
            if modname.startswith('test_') and not ispkg:
                try:
                    module = importlib.import_module(f'tests.mcp_managers.{modname}')
                    
                    # モジュール内のBaseManagerTestのサブクラスを検索
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BaseManagerTest) and 
                            attr != BaseManagerTest):
                            manager_tests.append(attr)
                            
                except ImportError as e:
                    print(f"⚠️ {modname} のインポートに失敗: {e}")
        
        return manager_tests
    
    @staticmethod
    def get_manager_test_names() -> List[str]:
        """登録されている全てのManagerテスト名を取得"""
        manager_tests = ManagerRegistry.discover_manager_tests()
        return [test_class().get_manager_name() for test_class in manager_tests]

#### 各Manager専用テストクラス（拡張可能パターン）
```python
class UserManagementTest(BaseManagerTest):
    """UserManagement テスト (3ツール)"""
    
    def get_manager_name(self) -> str:
        return "UserManagement"
    
    def get_tool_list(self) -> List[str]:
        return [
            "UserManagement___AddUser",
            "UserManagement___UpdateUser", 
            "UserManagement___GetUser"
        ]
    
    def get_cleanup_tools(self) -> Dict[str, str]:
        return {}  # UserManagementには削除ツールなし
    
    def test_usermanagement___adduser(self) -> bool:
        """AddUser ツールテスト"""
        # 実装
        
    def test_usermanagement___updateuser(self) -> bool:
        """UpdateUser ツールテスト"""
        # 実装
        
    def test_usermanagement___getuser(self) -> bool:
        """GetUser ツールテスト"""
        # 実装

class HealthGoalManagementTest(BaseManagerTest):
    """HealthGoalManagement テスト (4ツール)"""
    
    def get_manager_name(self) -> str:
        return "HealthGoalManagement"
    
    def get_tool_list(self) -> List[str]:
        return [
            "HealthGoalManagement___AddGoal",
            "HealthGoalManagement___GetGoals",
            "HealthGoalManagement___UpdateGoal",
            "HealthGoalManagement___DeleteGoal"
        ]
    
    def get_cleanup_tools(self) -> Dict[str, str]:
        return {
            "HealthGoalManagement___AddGoal": "HealthGoalManagement___DeleteGoal"
        }
    
    # テストメソッドの実装...

# 新しいManagerを追加する場合の例
class NewFeatureManagementTest(BaseManagerTest):
    """新機能Management テスト（将来追加される例）"""
    
    def get_manager_name(self) -> str:
        return "NewFeatureManagement"
    
    def get_tool_list(self) -> List[str]:
        return [
            "NewFeatureManagement___AddFeature",
            "NewFeatureManagement___GetFeatures",
            "NewFeatureManagement___DeleteFeature"
        ]
    
    def get_cleanup_tools(self) -> Dict[str, str]:
        return {
            "NewFeatureManagement___AddFeature": "NewFeatureManagement___DeleteFeature"
        }
    
    # 新しいテストメソッドを実装するだけで自動的に統合テストに組み込まれる
```

### 3. 統合テストコンポーネント (mcp_integration) - 拡張可能設計

#### AllManagersTest クラス（自動発見機能付き）
```python
class AllManagersTest:
    """全Manager統合テスト（拡張可能設計）"""
    
    def __init__(self):
        self.config = Config()
        self.auth_client = AuthClient(self.config)
        self.mcp_client = MCPClient(self.auth_client, self.config)
        self.test_user_id = TestUtils.generate_test_user_id()
        self.manager_tests = []
        self.test_results = {}
    
    def setup_manager_tests(self):
        """各Managerテストを自動発見・初期化"""
        manager_test_classes = ManagerRegistry.discover_manager_tests()
        
        for test_class in manager_test_classes:
            try:
                manager_test = test_class(self.mcp_client, self.test_user_id)
                self.manager_tests.append(manager_test)
                print(f"✅ {manager_test.get_manager_name()} テストを登録")
            except Exception as e:
                print(f"⚠️ {test_class.__name__} の初期化に失敗: {e}")
    
    def run_all_tests(self) -> bool:
        """全てのManagerテストを自動実行"""
        print(f"🚀 発見されたManagerテスト数: {len(self.manager_tests)}")
        
        overall_success = True
        
        for manager_test in self.manager_tests:
            manager_name = manager_test.get_manager_name()
            print(f"\n--- {manager_name} テスト開始 ---")
            
            try:
                success = manager_test.run_tests()
                self.test_results[manager_name] = {
                    'success': success,
                    'tool_results': manager_test.test_results
                }
                
                if success:
                    print(f"✅ {manager_name} テスト完了")
                else:
                    print(f"❌ {manager_name} テストで問題発生")
                    overall_success = False
                    
            except Exception as e:
                print(f"❌ {manager_name} テスト例外: {str(e)}")
                self.test_results[manager_name] = {
                    'success': False,
                    'error': str(e)
                }
                overall_success = False
        
        return overall_success
    
    def test_holistic_user_data(self) -> bool:
        """HolisticUserDataService テスト"""
        # 既存の実装
        
    def cleanup_all_test_data(self):
        """全てのテストデータを自動削除"""
        for manager_test in self.manager_tests:
            try:
                manager_test.cleanup_test_data()
            except Exception as e:
                print(f"⚠️ {manager_test.get_manager_name()} のクリーンアップ失敗: {e}")
        
    def generate_test_report(self):
        """拡張可能なテスト結果レポートを生成"""
        print("\n" + "="*60)
        print("📊 テスト結果サマリー")
        print("="*60)
        
        total_managers = len(self.test_results)
        successful_managers = sum(1 for result in self.test_results.values() if result.get('success', False))
        
        print(f"総Managerテスト数: {total_managers}")
        print(f"成功: {successful_managers}")
        print(f"失敗: {total_managers - successful_managers}")
        
        for manager_name, result in self.test_results.items():
            status = "✅" if result.get('success', False) else "❌"
            print(f"{status} {manager_name}")
            
            if 'tool_results' in result:
                for tool_name, tool_success in result['tool_results'].items():
                    tool_status = "  ✅" if tool_success else "  ❌"
                    print(f"{tool_status} {tool_name}")

#### 新しいManagerの追加手順（拡張ガイド）
```python
"""
新しいManagerテストを追加する手順:

1. tests/mcp_managers/ に新しいファイルを作成
   例: test_new_feature_management.py

2. BaseManagerTestを継承したクラスを実装
   - get_manager_name(): Manager名を返す
   - get_tool_list(): テスト対象ツールのリストを返す  
   - get_cleanup_tools(): 削除ツールのマッピングを返す
   - test_xxx(): 各ツールのテストメソッドを実装

3. ファイルを保存するだけで自動的に統合テストに組み込まれる
   - ManagerRegistryが自動発見
   - AllManagersTestが自動実行
   - HolisticUserDataServiceテストで自動検証

追加作業は一切不要！
"""
```

## Data Models

### テスト設定データモデル
```python
@dataclass
class TestConfig:
    environment: str
    aws_region: str
    stack_name: str
    gateway_endpoint: str
    cognito_user_pool_id: str
    cognito_client_id: str
    cognito_client_secret: str
    timeout_seconds: int = 30
    debug_mode: bool = False

@dataclass
class TestResult:
    manager_name: str
    tool_name: str
    success: bool
    execution_time: float
    error_message: Optional[str] = None
    created_ids: List[str] = field(default_factory=list)

@dataclass
class HolisticDataValidation:
    user_profile_valid: bool
    goals_count: int
    policies_count: int
    activities_count: int
    body_measurements_count: int
    concerns_count: int
    journals_count: int
    observations_count: int
    missing_sections: List[str] = field(default_factory=list)
```

### テストデータモデル
```python
@dataclass
class TestUserData:
    user_id: str
    username: str
    email: str
    goals: List[str]

@dataclass
class TestGoalData:
    goal_type: str
    title: str
    description: str
    target_value: str
    target_date: str
    priority: int

@dataclass
class TestActivityData:
    date: str
    time: str
    activity_type: str
    description: str
    items: List[str]

# 他のテストデータモデルも同様に定義
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property-Based Testing Overview

Property-based testing (PBT) validates software correctness by testing universal properties across many generated inputs. Each property is a formal specification that should hold for all valid inputs.

### Core Principles

1. **Universal Quantification**: Every property must contain an explicit "for all" statement
2. **Requirements Traceability**: Each property must reference the requirements it validates
3. **Executable Specifications**: Properties must be implementable as automated tests
4. **Comprehensive Coverage**: Properties should cover all testable acceptance criteria

### Correctness Properties

#### Property 1: フォルダ構造の整合性
*For any* リファクタリング実行後のテストフォルダ構造において、必要な全てのディレクトリとファイルが正しく作成され、既存の未使用ファイルが削除されていること
**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**

#### Property 2: Manager テストの分離完全性
*For any* Manager テストファイルにおいて、対応するMCPツールの全てが適切にテストされ、他のManagerのテストコードが含まれていないこと
**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8**

#### Property 3: 共通機能の重複排除
*For any* 共通機能（認証、MCP通信、ユーティリティ、設定）において、複数のファイルで重複する実装が存在せず、全てのManagerテストから適切に利用可能であること
**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

#### Property 4: テストシナリオの効率性
*For any* Managerテストにおいて、基本的なCRUD操作が最小限のテストケースでカバーされ、不要な複雑なテストケースが除去されていること
**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

#### Property 5: HolisticUserDataService 検証の包括性
*For any* HolisticUserDataService テスト実行において、全ての想定する属性（userProfile, goals, policies, activities, bodyMeasurements, concerns, journals, observations）が正しく取得され、テストで作成したデータが含まれていること
**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10**

#### Property 6: テストデータ削除の完全性
*For any* 削除機能を持つMCPツールにおいて、テスト実行後に作成された全てのテストデータが適切に削除され、削除機能のないツールのデータは保持されること
**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9**

#### Property 7: テストユーザーID の識別可能性
*For any* テスト実行において、生成される全てのテストユーザーIDが `test-user-{8桁のランダム文字列}` 形式に従い、テストデータとして識別可能であること
**Validates: Requirements 7.1, 7.2, 7.3, 7.4**

#### Property 8: 統合テストの実行順序
*For any* 統合テスト実行において、全てのManagerテストが正しい順序で実行され、失敗したテストがあっても他のテストに影響を与えず、最終的にHolisticUserDataServiceテストが実行されること
**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

#### Property 9: エラーハンドリングの一貫性
*For any* MCPツール呼び出しにおいて、エラーが発生した場合に適切なエラーメッセージがログに記録され、テスト実行が継続可能な状態を維持すること
**Validates: Requirements 9.1, 9.2, 9.3, 9.4**

#### Property 10: 設定の外部化と動的取得
*For any* テスト実行環境において、CloudFormation出力から動的に取得された設定値が正しく使用され、環境変数による設定変更が適切に反映されること
**Validates: Requirements 10.1, 10.2, 10.3, 10.4**

## Error Handling

### エラー分類と対応戦略

#### 1. 認証エラー
- **M2M認証失敗**: Cognito設定の確認、Client Secretの再取得
- **トークン期限切れ**: 自動リフレッシュ機能
- **権限不足**: IAMロールとスコープの確認

#### 2. 通信エラー
- **ネットワークタイムアウト**: リトライ機能（最大3回）
- **Gateway接続失敗**: エンドポイント設定の確認
- **MCPプロトコルエラー**: リクエスト形式の検証

#### 3. データエラー
- **レスポンス解析失敗**: JSON形式の検証とフォールバック
- **必須フィールド不足**: デフォルト値の設定
- **データ型不一致**: 型変換とバリデーション

#### 4. テスト実行エラー
- **テストデータ作成失敗**: 代替データでの継続実行
- **削除処理失敗**: 警告ログの出力と継続実行
- **HolisticData検証失敗**: 部分的な検証結果の報告

### エラーハンドリング実装パターン

```python
class ErrorHandler:
    """統一エラーハンドリング"""
    
    @staticmethod
    def handle_mcp_error(error: Exception, context: str) -> dict:
        """MCPエラーの統一処理"""
        
    @staticmethod
    def handle_auth_error(error: Exception) -> bool:
        """認証エラーの処理"""
        
    @staticmethod
    def handle_network_error(error: Exception, retry_count: int) -> bool:
        """ネットワークエラーの処理"""
        
    @staticmethod
    def log_error(error: Exception, context: str, additional_info: dict = None):
        """エラーログの統一出力"""
```

## Testing Strategy

## テストシナリオ設計

### 実際のユーザー使用方法に基づくテストフロー

#### フェーズ1: 登録・更新・参照系テスト

```python
class IntegratedUserScenarioTest:
    """実際のユーザー使用パターンに基づく統合テストシナリオ"""
    
    def run_user_registration_scenario(self) -> bool:
        """ユーザー登録から包括情報取得までの完全なシナリオ"""
        
        # 1. ユーザー情報登録
        user_data = self.test_user_registration()
        
        # 2. 健康目標登録・追加・変更
        goals_data = self.test_health_goals_lifecycle()
        
        # 3. 健康ポリシー登録・追加・変更  
        policies_data = self.test_health_policies_lifecycle()
        
        # 4. 健康不安登録・追加・変更
        concerns_data = self.test_health_concerns_lifecycle()
        
        # 5. 身体測定履歴追加・更新・変更、数日分追加、latest/oldest チェック
        measurements_data = self.test_body_measurements_multi_day_scenario()
        
        # 6. 活動履歴登録・追加・変更、複数日数分追加、複数日数分取得
        activities_data = self.test_activities_multi_day_scenario()
        
        # 7. ジャーナル登録・追加・変更
        journal_data = self.test_journal_lifecycle()
        
        # 8. 経過観測登録・追加・変更、複数登録、Complete
        observations_data = self.test_observations_complete_scenario()
        
        # 9. ユーザー包括情報取得（全データの整合性確認）
        holistic_validation = self.test_holistic_data_comprehensive_validation()
        
        return all([
            user_data, goals_data, policies_data, concerns_data,
            measurements_data, activities_data, journal_data,
            observations_data, holistic_validation
        ])
    
    def test_body_measurements_multi_day_scenario(self) -> bool:
        """身体測定の複数日シナリオ（latest/oldest検証含む）"""
        
        # 複数日の測定データを時系列順ではない順序で登録
        measurement_dates = [
            "2025-01-15T10:00:00Z",  # 中間日
            "2025-01-10T09:00:00Z",  # 最古日（oldest期待値）
            "2025-01-20T11:00:00Z",  # 最新日（latest期待値）
            "2025-01-12T08:30:00Z",  # 中間日
        ]
        
        measurement_data = [
            {"weight": 70.0, "height": 175.0, "body_fat_percentage": 18.0},
            {"weight": 69.5, "height": 175.0, "body_fat_percentage": 17.5},
            {"weight": 71.0, "height": 175.0, "body_fat_percentage": 18.5},  # latest期待値
            {"weight": 69.8, "height": 175.0, "body_fat_percentage": 17.8},
        ]
        
        # 各日の測定データを登録
        for i, (date, data) in enumerate(zip(measurement_dates, measurement_data)):
            success = self.add_body_measurement(date, **data)
            if not success:
                return False
        
        # Latest測定値の検証（2025-01-20のデータが取得されることを確認）
        latest = self.get_latest_measurements()
        if not self.validate_latest_measurement(latest, measurement_data[2]):
            return False
        
        # Oldest測定値の検証（2025-01-10のデータが取得されることを確認）
        oldest = self.get_oldest_measurements()
        if not self.validate_oldest_measurement(oldest, measurement_data[1]):
            return False
        
        # 期間指定での履歴取得
        history = self.get_measurement_history("2025-01-09", "2025-01-21")
        if len(history) != 4:
            return False
        
        return True
    
    def test_activities_multi_day_scenario(self) -> bool:
        """活動履歴の複数日シナリオ"""
        
        # 複数日の活動データを登録
        activity_dates = ["2025-01-15", "2025-01-16", "2025-01-17"]
        
        for date in activity_dates:
            # 各日に複数の活動を登録
            activities = [
                {"time": "08:00", "activityType": "wakeUp", "description": "起床", "items": ["自然に目覚めた"]},
                {"time": "09:00", "activityType": "exercise", "description": "運動", "items": ["ジョギング30分"]},
                {"time": "12:00", "activityType": "meal", "description": "昼食", "items": ["サラダ", "チキン"]},
            ]
            
            success = self.add_activities(date, activities)
            if not success:
                return False
        
        # 複数日数分の活動取得
        range_activities = self.get_activities_in_range("2025-01-15", "2025-01-17")
        if not self.validate_multi_day_activities(range_activities, activity_dates):
            return False
        
        return True
    
    def test_observations_complete_scenario(self) -> bool:
        """経過観測の完了シナリオ"""
        
        # 複数の経過観測を登録
        observations = [
            {
                "title": "腰痛改善観測",
                "description": "ストレッチによる腰痛改善効果の観測",
                "priority": 3,
                "startDatetime": "2025-01-10T00:00:00Z",
                "targetDatetime": "2025-01-20T00:00:00Z",
                "frequency": "P1D",
                "checkItems": ["腰痛レベル", "ストレッチ実施状況"]
            },
            {
                "title": "睡眠質改善観測", 
                "description": "就寝時間変更による睡眠質改善の観測",
                "priority": 2,
                "startDatetime": "2025-01-12T00:00:00Z",
                "targetDatetime": "2025-01-25T00:00:00Z",
                "frequency": "P1D",
                "checkItems": ["睡眠時間", "睡眠質スコア"]
            }
        ]
        
        observation_ids = []
        
        # 各観測を登録
        for obs_data in observations:
            obs_id = self.add_observation(**obs_data)
            if not obs_id:
                return False
            observation_ids.append(obs_id)
        
        # 進行中の観測を取得
        in_progress = self.get_observations(status="IN_PROGRESS")
        if len(in_progress) < 2:
            return False
        
        # 1つ目の観測を完了
        complete_success = self.complete_observation(
            observation_ids[0],
            conclusion="ストレッチにより腰痛が大幅に改善されました"
        )
        if not complete_success:
            return False
        
        # 完了した観測を確認
        completed = self.get_observations(status="COMPLETED")
        if len(completed) < 1:
            return False
        
        return True

#### フェーズ2: 削除系テスト（逆順実行）

    def run_cleanup_scenario(self) -> bool:
        """削除機能のテスト（作成の逆順で実行）"""
        
        # 削除順序（依存関係を考慮した逆順）
        cleanup_results = []
        
        # 1. 経過観測キャンセル（削除機能なし - キャンセル機能のみ）
        cleanup_results.append(self.test_observations_cancel())
        
        # 2. ジャーナル削除
        cleanup_results.append(self.test_journal_deletion())
        
        # 3. 活動履歴削除
        cleanup_results.append(self.test_activities_deletion())
        
        # 4. 身体測定履歴削除
        cleanup_results.append(self.test_body_measurements_deletion())
        
        # 5. 健康不安削除
        cleanup_results.append(self.test_health_concerns_deletion())
        
        # 6. 健康ポリシー削除
        cleanup_results.append(self.test_health_policies_deletion())
        
        # 7. 健康目標削除
        cleanup_results.append(self.test_health_goals_deletion())
        
        # 8. ユーザー情報は削除機能なし（保持される）
        cleanup_results.append(self.verify_user_data_preserved())
        
        return all(cleanup_results)
    
    def test_observations_cancel(self) -> bool:
        """経過観測のキャンセル（削除機能なし）"""
        
        # 進行中の観測を取得
        in_progress_observations = self.get_observations(status="IN_PROGRESS")
        
        if not in_progress_observations:
            return True  # キャンセル対象がない場合は成功
        
        # 最初の観測をキャンセル
        observation_id = in_progress_observations[0]['observationId']
        cancel_success = self.cancel_observation(
            observation_id,
            conclusion="テスト完了のためキャンセルします"
        )
        
        if not cancel_success:
            return False
        
        # キャンセル後の状態確認
        cancelled_obs = self.get_observation(observation_id)
        return cancelled_obs['status'] == 'CANCELLED'
```

### テストデータの一貫性検証

```python
class HolisticDataValidator:
    """包括データの一貫性検証"""
    
    def validate_comprehensive_user_data(self, holistic_data: dict, expected_data: dict) -> bool:
        """作成したテストデータが包括データに正しく反映されているかを検証"""
        
        validations = [
            self.validate_user_profile(holistic_data, expected_data),
            self.validate_health_goals(holistic_data, expected_data),
            self.validate_health_policies(holistic_data, expected_data),
            self.validate_health_concerns(holistic_data, expected_data),
            self.validate_body_measurements_timeline(holistic_data, expected_data),
            self.validate_activities_timeline(holistic_data, expected_data),
            self.validate_journal_entries(holistic_data, expected_data),
            self.validate_observations_status(holistic_data, expected_data),
        ]
        
        return all(validations)
    
    def validate_body_measurements_timeline(self, holistic_data: dict, expected_data: dict) -> bool:
        """身体測定データのタイムライン検証"""
        
        measurements = holistic_data.get('bodyMeasurements', {})
        
        # Latest/Oldest の正確性確認
        latest = measurements.get('latest', {})
        oldest = measurements.get('oldest', {})
        
        # 期待される最新値と最古値の確認
        expected_latest = expected_data['measurements']['latest']
        expected_oldest = expected_data['measurements']['oldest']
        
        latest_valid = (
            latest.get('weight') == expected_latest['weight'] and
            latest.get('measurement_time') == expected_latest['measurement_time']
        )
        
        oldest_valid = (
            oldest.get('weight') == expected_oldest['weight'] and
            oldest.get('measurement_time') == expected_oldest['measurement_time']
        )
        
        return latest_valid and oldest_valid
```

### テスト実行パターン

#### 1. 個別Managerテスト
```bash
# 特定のManagerのみテスト
python -m pytest tests/mcp_managers/test_user_management.py -v

# 全Managerテスト
python -m pytest tests/mcp_managers/ -v
```

#### 2. 統合テスト
```bash
# 全Manager + HolisticUserDataService テスト
python -m pytest tests/mcp_integration/test_all_managers.py -v

# 既存の統合テスト（互換性維持）
python test_mcp_client.py
```

#### 3. 継続的インテグレーション
```yaml
# GitHub Actions での自動テスト
- name: Run MCP Manager Tests
  run: python -m pytest tests/mcp_managers/ -v --tb=short

- name: Run MCP Integration Tests  
  run: python -m pytest tests/mcp_integration/ -v --tb=short
```

### テスト設定とタイムアウト

- **MCPツール呼び出し**: 30秒タイムアウト
- **HolisticUserDataService**: 60秒タイムアウト（大量データ処理のため）
- **認証処理**: 10秒タイムアウト
- **リトライ回数**: 最大3回（ネットワークエラー時）

### テストデータ管理

#### テストデータライフサイクル
1. **作成**: 各テスト開始時に最小限のテストデータを作成
2. **使用**: テスト実行中にデータを参照・更新
3. **検証**: HolisticUserDataServiceでデータ整合性を確認
4. **削除**: 削除機能があるツールでクリーンアップ

#### データ削除対応表
| Manager | 削除ツール | 削除対象 | 対応 |
|---------|------------|----------|------|
| UserManagement | なし | ユーザーデータ | 削除しない |
| HealthGoalManagement | DeleteGoal | 健康目標 | 削除する |
| HealthPolicyManagement | DeletePolicy | 健康ポリシー | 削除する |
| ActivityManagement | DeleteActivity | 活動記録 | 削除する |
| BodyMeasurementManagement | DeleteBodyMeasurement | 身体測定 | 削除する |
| HealthConcernManagement | DeleteConcern | 健康コンサーン | 削除する |
| JournalManagement | DeleteJournal | 日記 | 削除する |
| HealthObservationManagement | DeleteObservation | 経過観測 | 削除する |