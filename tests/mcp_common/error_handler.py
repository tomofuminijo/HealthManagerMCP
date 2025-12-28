"""
統一エラーハンドリングモジュール

MCPエラー、認証エラー、ネットワークエラーの統一処理と
詳細なエラーログ記録機能を提供します。
"""

import traceback
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum


class ErrorType(Enum):
    """エラータイプの定義"""
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    MCP_PROTOCOL_ERROR = "MCP_PROTOCOL_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    DATA_ERROR = "DATA_ERROR"


class ErrorSeverity(Enum):
    """エラー重要度の定義"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ErrorHandler:
    """統一エラーハンドリングクラス"""
    
    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.error_log = []
    
    def handle_mcp_error(self, error: Exception, context: str, tool_name: str = None) -> Dict[str, Any]:
        """MCPエラーの統一処理"""
        error_info = {
            "type": ErrorType.MCP_PROTOCOL_ERROR.value,
            "severity": ErrorSeverity.HIGH.value,
            "context": context,
            "tool_name": tool_name,
            "timestamp": datetime.now().isoformat(),
            "error_message": str(error),
            "error_class": error.__class__.__name__
        }
        
        # エラーメッセージの詳細解析
        error_message = str(error).lower()
        
        if "timeout" in error_message:
            error_info["type"] = ErrorType.TIMEOUT_ERROR.value
            error_info["severity"] = ErrorSeverity.MEDIUM.value
            error_info["suggested_action"] = "リクエストタイムアウトを延長するか、後で再試行してください"
            
        elif "authentication" in error_message or "unauthorized" in error_message:
            error_info["type"] = ErrorType.AUTHENTICATION_ERROR.value
            error_info["severity"] = ErrorSeverity.HIGH.value
            error_info["suggested_action"] = "認証トークンを確認し、必要に応じて再認証してください"
            
        elif "connection" in error_message or "network" in error_message:
            error_info["type"] = ErrorType.NETWORK_ERROR.value
            error_info["severity"] = ErrorSeverity.MEDIUM.value
            error_info["suggested_action"] = "ネットワーク接続を確認し、後で再試行してください"
            
        elif "validation" in error_message or "invalid" in error_message:
            error_info["type"] = ErrorType.VALIDATION_ERROR.value
            error_info["severity"] = ErrorSeverity.MEDIUM.value
            error_info["suggested_action"] = "リクエストパラメータを確認してください"
        
        # デバッグ情報の追加
        if self.debug_mode:
            error_info["traceback"] = traceback.format_exc()
        
        # エラーログに記録
        self.log_error(error_info)
        
        return {
            "success": False,
            "error": error_info["type"],
            "message": error_info["error_message"],
            "context": context,
            "suggested_action": error_info.get("suggested_action"),
            "timestamp": error_info["timestamp"]
        }
    
    def handle_auth_error(self, error: Exception, auth_type: str = "M2M") -> Dict[str, Any]:
        """認証エラーの処理"""
        error_info = {
            "type": ErrorType.AUTHENTICATION_ERROR.value,
            "severity": ErrorSeverity.CRITICAL.value,
            "context": f"{auth_type} Authentication",
            "timestamp": datetime.now().isoformat(),
            "error_message": str(error),
            "error_class": error.__class__.__name__,
            "auth_type": auth_type
        }
        
        # 認証エラーの詳細分析
        error_message = str(error).lower()
        
        if "client_secret" in error_message or "secret" in error_message:
            error_info["suggested_action"] = "Client Secretの設定を確認してください"
            error_info["details"] = "Client Secret関連のエラーです"
            
        elif "client_id" in error_message:
            error_info["suggested_action"] = "Client IDの設定を確認してください"
            error_info["details"] = "Client ID関連のエラーです"
            
        elif "user_pool" in error_message or "pool" in error_message:
            error_info["suggested_action"] = "Cognito User Poolの設定を確認してください"
            error_info["details"] = "User Pool関連のエラーです"
            
        elif "expired" in error_message or "invalid" in error_message:
            error_info["suggested_action"] = "認証情報が期限切れまたは無効です。再認証してください"
            error_info["details"] = "認証情報の有効性に問題があります"
        
        else:
            error_info["suggested_action"] = "認証設定全般を確認してください"
            error_info["details"] = "一般的な認証エラーです"
        
        if self.debug_mode:
            error_info["traceback"] = traceback.format_exc()
        
        self.log_error(error_info)
        
        return {
            "success": False,
            "error": error_info["type"],
            "message": error_info["error_message"],
            "auth_type": auth_type,
            "suggested_action": error_info["suggested_action"],
            "details": error_info.get("details"),
            "timestamp": error_info["timestamp"]
        }
    
    def handle_network_error(self, error: Exception, retry_count: int = 0, max_retries: int = 3) -> Dict[str, Any]:
        """ネットワークエラーの処理"""
        error_info = {
            "type": ErrorType.NETWORK_ERROR.value,
            "severity": ErrorSeverity.MEDIUM.value,
            "context": "Network Communication",
            "timestamp": datetime.now().isoformat(),
            "error_message": str(error),
            "error_class": error.__class__.__name__,
            "retry_count": retry_count,
            "max_retries": max_retries
        }
        
        # ネットワークエラーの詳細分析
        error_message = str(error).lower()
        
        if "timeout" in error_message:
            error_info["type"] = ErrorType.TIMEOUT_ERROR.value
            error_info["suggested_action"] = "タイムアウト値を増やすか、後で再試行してください"
            error_info["details"] = "リクエストタイムアウトが発生しました"
            
        elif "connection refused" in error_message:
            error_info["severity"] = ErrorSeverity.HIGH.value
            error_info["suggested_action"] = "サーバーが起動しているか確認してください"
            error_info["details"] = "接続が拒否されました"
            
        elif "dns" in error_message or "name resolution" in error_message:
            error_info["severity"] = ErrorSeverity.HIGH.value
            error_info["suggested_action"] = "エンドポイントURLを確認してください"
            error_info["details"] = "DNS解決に失敗しました"
            
        elif "ssl" in error_message or "certificate" in error_message:
            error_info["severity"] = ErrorSeverity.HIGH.value
            error_info["suggested_action"] = "SSL証明書の設定を確認してください"
            error_info["details"] = "SSL/TLS関連のエラーです"
        
        else:
            error_info["suggested_action"] = "ネットワーク接続を確認してください"
            error_info["details"] = "一般的なネットワークエラーです"
        
        # リトライ可能性の判定
        error_info["can_retry"] = retry_count < max_retries
        if error_info["can_retry"]:
            error_info["next_retry_in"] = 2 ** retry_count  # 指数バックオフ
        
        if self.debug_mode:
            error_info["traceback"] = traceback.format_exc()
        
        self.log_error(error_info)
        
        return {
            "success": False,
            "error": error_info["type"],
            "message": error_info["error_message"],
            "retry_count": retry_count,
            "can_retry": error_info["can_retry"],
            "suggested_action": error_info["suggested_action"],
            "details": error_info.get("details"),
            "timestamp": error_info["timestamp"]
        }
    
    def handle_configuration_error(self, error: Exception, config_type: str) -> Dict[str, Any]:
        """設定エラーの処理"""
        error_info = {
            "type": ErrorType.CONFIGURATION_ERROR.value,
            "severity": ErrorSeverity.HIGH.value,
            "context": f"Configuration: {config_type}",
            "timestamp": datetime.now().isoformat(),
            "error_message": str(error),
            "error_class": error.__class__.__name__,
            "config_type": config_type
        }
        
        # 設定エラーの詳細分析
        error_message = str(error).lower()
        
        if "cloudformation" in error_message:
            error_info["suggested_action"] = "CloudFormationスタックが正常にデプロイされているか確認してください"
            error_info["details"] = "CloudFormation関連の設定エラーです"
            
        elif "environment" in error_message or "env" in error_message:
            error_info["suggested_action"] = "環境変数の設定を確認してください"
            error_info["details"] = "環境変数関連の設定エラーです"
            
        elif "missing" in error_message or "not found" in error_message:
            error_info["suggested_action"] = "必要な設定値が不足しています。設定を確認してください"
            error_info["details"] = "設定値が見つかりません"
        
        else:
            error_info["suggested_action"] = f"{config_type}の設定を確認してください"
            error_info["details"] = "一般的な設定エラーです"
        
        if self.debug_mode:
            error_info["traceback"] = traceback.format_exc()
        
        self.log_error(error_info)
        
        return {
            "success": False,
            "error": error_info["type"],
            "message": error_info["error_message"],
            "config_type": config_type,
            "suggested_action": error_info["suggested_action"],
            "details": error_info.get("details"),
            "timestamp": error_info["timestamp"]
        }
    
    def log_error(self, error_info: Dict[str, Any]):
        """エラーログの統一出力"""
        self.error_log.append(error_info)
        
        # コンソール出力
        timestamp = error_info.get("timestamp", "Unknown")
        error_type = error_info.get("type", "UNKNOWN")
        severity = error_info.get("severity", "UNKNOWN")
        context = error_info.get("context", "Unknown")
        message = error_info.get("error_message", "Unknown error")
        
        severity_icon = {
            "LOW": "ℹ️",
            "MEDIUM": "⚠️",
            "HIGH": "❌",
            "CRITICAL": "🚨"
        }.get(severity, "❓")
        
        print(f"{severity_icon} [{timestamp}] {error_type} in {context}: {message}")
        
        # 推奨アクションがある場合は表示
        if "suggested_action" in error_info:
            print(f"   💡 推奨アクション: {error_info['suggested_action']}")
        
        # デバッグモードの場合、詳細情報を表示
        if self.debug_mode and "traceback" in error_info:
            print(f"   🔍 詳細トレースバック:")
            for line in error_info["traceback"].split('\n'):
                if line.strip():
                    print(f"      {line}")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """エラーサマリーを取得"""
        if not self.error_log:
            return {
                "total_errors": 0,
                "by_type": {},
                "by_severity": {},
                "recent_errors": []
            }
        
        # エラータイプ別集計
        by_type = {}
        by_severity = {}
        
        for error in self.error_log:
            error_type = error.get("type", "UNKNOWN")
            severity = error.get("severity", "UNKNOWN")
            
            by_type[error_type] = by_type.get(error_type, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        # 最新のエラー（最大5件）
        recent_errors = self.error_log[-5:] if len(self.error_log) > 5 else self.error_log
        
        return {
            "total_errors": len(self.error_log),
            "by_type": by_type,
            "by_severity": by_severity,
            "recent_errors": [
                {
                    "timestamp": error.get("timestamp"),
                    "type": error.get("type"),
                    "severity": error.get("severity"),
                    "context": error.get("context"),
                    "message": error.get("error_message", "")[:100]  # 最初の100文字
                }
                for error in recent_errors
            ]
        }
    
    def clear_error_log(self):
        """エラーログをクリア"""
        self.error_log.clear()
    
    def export_error_log(self, filename: str = None) -> str:
        """エラーログをJSONファイルにエクスポート"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mcp_test_errors_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.error_log, f, indent=2, ensure_ascii=False)
            
            print(f"✅ エラーログをエクスポートしました: {filename}")
            return filename
            
        except Exception as e:
            print(f"❌ エラーログエクスポート失敗: {str(e)}")
            return None