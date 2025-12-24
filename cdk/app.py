#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk.cdk_stack import HealthmateHealthManagerStack
from cdk.environment import ConfigurationProvider


app = cdk.App()

# 環境設定の初期化
config_provider = ConfigurationProvider("healthmate-healthmanager")

# Healthmate-HealthManagerスタックを作成
HealthmateHealthManagerStack(
    app, 
    config_provider.get_stack_name("Healthmate-HealthManagerStack"),
    # 現在のAWS CLIの設定（アカウント、リージョン）を使用
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'), 
        region=config_provider.get_aws_region()
    ),
    description="Healthmate-HealthManager - Health Information Management MCP Server for Healthmate Ecosystem"
)

app.synth()