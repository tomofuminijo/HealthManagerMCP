"""
テスト用ユーティリティモジュール

テストユーザーID生成、MCPレスポンス解析、データ検証機能を提供します。
"""

import uuid
import json
import re
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
from dataclasses import dataclass


@dataclass
class TestResult:
    """テスト結果データクラス"""
    manager_name: str
    tool_name: str
    success: bool
    execution_time: float
    error_message: Optional[str] = None
    created_ids: List[str] = None
    
    def __post_init__(self):
        if self.created_ids is None:
            self.created_ids = []


class TestUtils:
    """テスト用ユーティリティクラス"""
    
    @staticmethod
    def generate_test_user_id() -> str:
        """テスト用ユーザーIDを生成 (test-user-{8桁})"""
        random_suffix = uuid.uuid4().hex[:8]
        return f"test-user-{random_suffix}"
    
    @staticmethod
    def generate_test_id(prefix: str = "test") -> str:
        """テスト用IDを生成"""
        random_suffix = uuid.uuid4().hex[:8]
        return f"{prefix}-{random_suffix}"
    
    @staticmethod
    def is_test_user_id(user_id: str) -> bool:
        """テスト用ユーザーIDかどうかを判定"""
        return bool(re.match(r'^test-user-[a-f0-9]{8}$', user_id))
    
    @staticmethod
    def parse_mcp_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """MCPレスポンスを解析"""
        if not isinstance(response, dict):
            return {
                "success": False,
                "error": "INVALID_RESPONSE_FORMAT",
                "message": "レスポンスが辞書形式ではありません",
                "raw_response": response
            }
        
        # 標準化されたレスポンス形式に変換
        parsed = {
            "success": response.get("success", False),
            "data": response.get("data"),
            "error": response.get("error"),
            "message": response.get("message"),
            "status_code": response.get("status_code")
        }
        
        # データの詳細解析
        if parsed["success"] and parsed["data"]:
            parsed["parsed_data"] = TestUtils._parse_response_data(parsed["data"])
        
        return parsed
    
    @staticmethod
    def _parse_response_data(data: Any) -> Dict[str, Any]:
        """レスポンスデータの詳細解析"""
        if isinstance(data, dict):
            parsed = {}
            
            # 共通フィールドの抽出
            for key in ["userId", "goalId", "policyId", "activityId", "measurementId", 
                       "concernId", "journalId", "observationId"]:
                if key in data:
                    parsed[f"extracted_{key}"] = data[key]
            
            # タイムスタンプフィールドの解析
            for key, value in data.items():
                if key.endswith(('Time', 'Date', 'Datetime')) and isinstance(value, str):
                    try:
                        parsed[f"parsed_{key}"] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except ValueError:
                        parsed[f"invalid_{key}"] = value
            
            return parsed
        
        return {"raw_data": data}
    
    @staticmethod
    def validate_response_success(response: Dict[str, Any]) -> bool:
        """レスポンスの成功を検証"""
        parsed = TestUtils.parse_mcp_response(response)
        return parsed.get("success", False)
    
    @staticmethod
    def extract_id_from_response(response: Dict[str, Any], id_field: str) -> Optional[str]:
        """レスポンスからIDを抽出（JSON-RPC 2.0対応版）"""
        if not TestUtils.validate_response_success(response):
            return None
        
        data = response.get("data", {})
        if not isinstance(data, dict):
            return None
        
        # JSON-RPC 2.0レスポンス形式の場合
        if 'result' in data and 'content' in data['result']:
            content = data['result']['content']
            
            # contentが配列の場合、最初の要素のtextを解析
            if isinstance(content, list) and len(content) > 0:
                text_content = content[0].get('text', '')
                if text_content:
                    try:
                        parsed_content = json.loads(text_content)
                        
                        # 直接IDフィールドを確認
                        if id_field in parsed_content:
                            return parsed_content[id_field]
                        
                        # ActivityManagement特有のフィールド名マッピング
                        if id_field == "activityId" and "addedActivityIds" in parsed_content:
                            activity_ids = parsed_content["addedActivityIds"]
                            if isinstance(activity_ids, list) and len(activity_ids) > 0:
                                return activity_ids[0]  # 最初のIDを返す
                        
                        # BodyMeasurementManagement特有のフィールド名マッピング
                        if id_field == "measurementId" and "measurementId" in parsed_content:
                            return parsed_content["measurementId"]
                        
                    except json.JSONDecodeError:
                        pass
            
            # contentが直接辞書の場合
            elif isinstance(content, dict) and id_field in content:
                return content[id_field]
        
        # 直接IDフィールドを確認
        if id_field in data:
            return data[id_field]
        
        # ネストされた構造を確認
        for key, value in data.items():
            if isinstance(value, dict) and id_field in value:
                return value[id_field]
            elif isinstance(value, list) and len(value) > 0:
                first_item = value[0]
                if isinstance(first_item, dict) and id_field in first_item:
                    return first_item[id_field]
        
        # parsed_dataからも確認
        parsed_data = TestUtils.parse_mcp_response(response).get("parsed_data", {})
        if isinstance(parsed_data, dict):
            extracted_key = f"extracted_{id_field}"
            if extracted_key in parsed_data:
                return parsed_data[extracted_key]
        
        return None
    
    @staticmethod
    def extract_ids_from_response(response: Dict[str, Any], ids_field: str) -> List[str]:
        """レスポンスから複数のIDを抽出（JSON-RPC 2.0対応版）"""
        if not TestUtils.validate_response_success(response):
            return []
        
        data = response.get("data", {})
        if not isinstance(data, dict):
            return []
        
        # JSON-RPC 2.0レスポンス形式の場合
        if 'result' in data and 'content' in data['result']:
            content = data['result']['content']
            
            # contentが配列の場合、最初の要素のtextを解析
            if isinstance(content, list) and len(content) > 0:
                text_content = content[0].get('text', '')
                if text_content:
                    try:
                        parsed_content = json.loads(text_content)
                        if ids_field in parsed_content:
                            ids = parsed_content[ids_field]
                            return ids if isinstance(ids, list) else []
                    except json.JSONDecodeError:
                        pass
            
            # contentが直接辞書の場合
            elif isinstance(content, dict) and ids_field in content:
                ids = content[ids_field]
                return ids if isinstance(ids, list) else []
        
        # 直接IDsフィールドを確認
        if ids_field in data:
            ids = data[ids_field]
            return ids if isinstance(ids, list) else []
        
        # ネストされた構造を確認
        for key, value in data.items():
            if isinstance(value, dict) and ids_field in value:
                ids = value[ids_field]
                return ids if isinstance(ids, list) else []
        
        return []
    
    @staticmethod
    def extract_data_count_from_response(response: Dict[str, Any], data_field: str) -> int:
        """レスポンスからデータ数を抽出（JSON-RPC 2.0対応版）"""
        if not TestUtils.validate_response_success(response):
            return 0
        
        data = response.get("data", {})
        if not isinstance(data, dict):
            return 0
        
        # JSON-RPC 2.0レスポンス形式の場合
        if 'result' in data and 'content' in data['result']:
            content = data['result']['content']
            
            # contentが配列の場合、最初の要素のtextを解析
            if isinstance(content, list) and len(content) > 0:
                text_content = content[0].get('text', '')
                if text_content:
                    try:
                        parsed_content = json.loads(text_content)
                        if data_field in parsed_content:
                            data_list = parsed_content[data_field]
                            return len(data_list) if isinstance(data_list, list) else 0
                    except json.JSONDecodeError:
                        pass
            
            # contentが直接辞書の場合
            elif isinstance(content, dict) and data_field in content:
                data_list = content[data_field]
                return len(data_list) if isinstance(data_list, list) else 0
        
        # 直接データフィールドを確認
        if data_field in data:
            data_list = data[data_field]
            return len(data_list) if isinstance(data_list, list) else 0
        
        # ネストされた構造を確認
        for key, value in data.items():
            if isinstance(value, dict) and data_field in value:
                data_list = value[data_field]
                return len(data_list) if isinstance(data_list, list) else 0
        
        return 0
    
    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
        """必須フィールドの存在を検証"""
        missing_fields = []
        present_fields = []
        
        for field in required_fields:
            if field in data and data[field] is not None:
                present_fields.append(field)
            else:
                missing_fields.append(field)
        
        return {
            "valid": len(missing_fields) == 0,
            "missing_fields": missing_fields,
            "present_fields": present_fields,
            "total_required": len(required_fields),
            "total_present": len(present_fields)
        }
    
    @staticmethod
    def compare_data_objects(expected: Dict[str, Any], actual: Dict[str, Any], ignore_fields: List[str] = None) -> Dict[str, Any]:
        """データオブジェクトの比較"""
        if ignore_fields is None:
            ignore_fields = ["createdAt", "updatedAt", "lastModified"]
        
        differences = []
        matches = []
        
        # 期待値のフィールドをチェック
        for key, expected_value in expected.items():
            if key in ignore_fields:
                continue
                
            if key not in actual:
                differences.append({
                    "field": key,
                    "type": "missing",
                    "expected": expected_value,
                    "actual": None
                })
            elif actual[key] != expected_value:
                differences.append({
                    "field": key,
                    "type": "value_mismatch",
                    "expected": expected_value,
                    "actual": actual[key]
                })
            else:
                matches.append(key)
        
        # 実際のデータにあって期待値にないフィールドをチェック
        for key in actual.keys():
            if key not in expected and key not in ignore_fields:
                differences.append({
                    "field": key,
                    "type": "unexpected",
                    "expected": None,
                    "actual": actual[key]
                })
        
        return {
            "match": len(differences) == 0,
            "differences": differences,
            "matches": matches,
            "total_differences": len(differences),
            "total_matches": len(matches)
        }
    
    @staticmethod
    def format_test_data_for_display(data: Any, max_length: int = 100) -> str:
        """テストデータを表示用にフォーマット"""
        if data is None:
            return "None"
        
        if isinstance(data, (dict, list)):
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            if len(json_str) > max_length:
                return json_str[:max_length] + "..."
            return json_str
        
        str_data = str(data)
        if len(str_data) > max_length:
            return str_data[:max_length] + "..."
        
        return str_data
    
    @staticmethod
    def create_test_timestamp() -> str:
        """テスト用タイムスタンプを生成"""
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    @staticmethod
    def validate_timestamp_format(timestamp: str) -> bool:
        """タイムスタンプ形式を検証"""
        try:
            # ISO 8601形式の検証
            if timestamp.endswith('Z'):
                datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                datetime.fromisoformat(timestamp)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def generate_test_email(prefix: str = "test") -> str:
        """テスト用メールアドレスを生成"""
        random_suffix = uuid.uuid4().hex[:8]
        return f"{prefix}-{random_suffix}@healthmate-test.local"
    
    @staticmethod
    def create_summary_report(test_results: List[TestResult]) -> Dict[str, Any]:
        """テスト結果のサマリーレポートを作成"""
        if not test_results:
            return {
                "total_tests": 0,
                "successful_tests": 0,
                "failed_tests": 0,
                "success_rate": 0.0,
                "managers": {},
                "errors": []
            }
        
        total_tests = len(test_results)
        successful_tests = sum(1 for result in test_results if result.success)
        failed_tests = total_tests - successful_tests
        
        # Manager別の統計
        managers = {}
        errors = []
        
        for result in test_results:
            manager = result.manager_name
            if manager not in managers:
                managers[manager] = {
                    "total": 0,
                    "successful": 0,
                    "failed": 0,
                    "tools": []
                }
            
            managers[manager]["total"] += 1
            managers[manager]["tools"].append({
                "name": result.tool_name,
                "success": result.success,
                "execution_time": result.execution_time
            })
            
            if result.success:
                managers[manager]["successful"] += 1
            else:
                managers[manager]["failed"] += 1
                if result.error_message:
                    errors.append({
                        "manager": manager,
                        "tool": result.tool_name,
                        "error": result.error_message
                    })
        
        return {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": (successful_tests / total_tests) * 100 if total_tests > 0 else 0.0,
            "managers": managers,
            "errors": errors,
            "total_execution_time": sum(result.execution_time for result in test_results)
        }