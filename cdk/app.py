#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk.cdk_stack import HealthManagerMCPStack


app = cdk.App()

# HealthManagerMCPスタックを作成
HealthManagerMCPStack(
    app, 
    "HealthManagerMCPStack",
    # 現在のAWS CLIの設定（アカウント、リージョン）を使用
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'), 
        region=os.getenv('CDK_DEFAULT_REGION')
    ),
    description="HealthManagerMCP - Health Information Management MCP Server for Healthmate Ecosystem"
)

app.synth()
