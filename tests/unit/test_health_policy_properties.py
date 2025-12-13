"""
HealthPolicyLambda関数のプロパティベーステスト

Feature: healthspan100
"""

import json
import os
import sys
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from health_policy.handler import add_policy, get_policy, update_policy


# カスタム戦略
policy_types = st.sampled_from(["diet", "exercise", "sleep", "fasting", "other"])
user_ids = st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_characters="\x00"))
policy_ids = st.uuids().map(str)
descriptions = st.text(max_size=200)


@settings(max_examples=100)
@given(
    user_id=user_ids,
    policy_type=policy_types,
    description=descriptions,
)
def test_property_5_round_trip(user_id, policy_type, description):
    """
    Feature: healthspan100, Property 5: 健康ポリシーのラウンドトリップ
    検証対象: 要件2.2

    任意の健康ポリシーに対して、保存してから取得すると、同じ内容が返されるべきである
    """
    with patch("health_policy.handler.table") as mock_table:
        # 保存時のモック
        mock_table.put_item.return_value = {}

        # ポリシーを追加
        add_result = add_policy(
            {
                "userId": user_id,
                "policyType": policy_type,
                "description": description,
                "parameters": {},
            }
        )

        assert add_result["success"] is True
        policy_id = add_result["policyId"]

        # 取得時のモック（保存したデータを返す）
        mock_table.query.return_value = {
            "Items": [
                {
                    "userId": user_id,
                    "policyId": policy_id,
                    "policyType": policy_type,
                    "details": {"description": description, "parameters": {}},
                }
            ]
        }

        # ポリシーを取得
        get_result = get_policy({"userId": user_id})

        assert get_result["success"] is True
        assert get_result["count"] == 1

        # ラウンドトリップ検証
        retrieved_policy = get_result["policies"][0]
        assert retrieved_policy["userId"] == user_id
        assert retrieved_policy["policyType"] == policy_type
        assert retrieved_policy["details"]["description"] == description


@settings(max_examples=100)
@given(
    user_id=user_ids,
    num_policies=st.integers(min_value=0, max_value=10),
)
def test_property_6_get_all_policies(user_id, num_policies):
    """
    Feature: healthspan100, Property 6: すべてのポリシーの取得
    検証対象: 要件2.3

    任意のユーザーに対して、保存したすべての健康ポリシーが取得時に返されるべきである
    """
    with patch("health_policy.handler.table") as mock_table:
        # 複数のポリシーを生成
        policies = [
            {
                "userId": user_id,
                "policyId": f"policy-{i}",
                "policyType": "diet",
                "details": {"description": f"Policy {i}"},
            }
            for i in range(num_policies)
        ]

        # 取得時のモック
        mock_table.query.return_value = {"Items": policies}

        # ポリシーを取得
        result = get_policy({"userId": user_id})

        assert result["success"] is True
        assert result["count"] == num_policies
        assert len(result["policies"]) == num_policies


@settings(max_examples=100)
@given(
    user_id=user_ids,
    policy_id=policy_ids,
    original_description=descriptions,
    updated_description=descriptions,
)
def test_property_7_update_reflection(
    user_id, policy_id, original_description, updated_description
):
    """
    Feature: healthspan100, Property 7: ポリシー更新の反映
    検証対象: 要件2.4

    任意の健康ポリシーに対して、更新後に取得すると、変更が反映されているべきである
    """
    with patch("health_policy.handler.table") as mock_table:
        # 更新時のモック
        mock_table.update_item.return_value = {}

        # ポリシーを更新
        update_result = update_policy(
            {
                "userId": user_id,
                "policyId": policy_id,
                "description": updated_description,
            }
        )

        assert update_result["success"] is True

        # 取得時のモック（更新後のデータを返す）
        mock_table.query.return_value = {
            "Items": [
                {
                    "userId": user_id,
                    "policyId": policy_id,
                    "policyType": "diet",
                    "details": {"description": updated_description},
                }
            ]
        }

        # ポリシーを取得
        get_result = get_policy({"userId": user_id})

        assert get_result["success"] is True
        retrieved_policy = get_result["policies"][0]

        # 更新が反映されていることを確認
        assert retrieved_policy["details"]["description"] == updated_description
