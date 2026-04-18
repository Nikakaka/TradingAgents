#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
同花顺iFinD数据源集成测试

测试场景：
1. 检查iFinD SDK是否安装
2. 测试HTTP API连接（需要配置IFIND_REFRESH_TOKEN）
3. 测试数据获取功能
"""

import os
import sys
from datetime import datetime, timedelta

def test_sdk_availability():
    """测试SDK是否可用"""
    print("\n" + "="*60)
    print("【测试1】iFinD SDK可用性检查")
    print("="*60)

    try:
        from iFinDPy import THS_iFinDLogin, THS_BD, THS_DS, THS_HQ
        print("   OK: iFinD SDK 已安装")
        return True
    except ImportError as e:
        print(f"   INFO: iFinD SDK 未安装: {e}")
        print("   安装方法: pip install iFinDAPI")
        print("   或从 https://quantapi.10jqka.com.cn 下载安装包")
        return False


def test_http_api():
    """测试HTTP API连接"""
    print("\n" + "="*60)
    print("【测试2】HTTP API连接测试")
    print("="*60)

    refresh_token = os.environ.get("IFIND_REFRESH_TOKEN", "")
    username = os.environ.get("IFIND_USERNAME", "")
    password = os.environ.get("IFIND_PASSWORD", "")

    if not refresh_token and not (username and password):
        print("   INFO: 未配置iFinD认证信息")
        print("   请设置以下环境变量之一：")
        print("   - IFIND_REFRESH_TOKEN (HTTP API)")
        print("   - IFIND_USERNAME + IFIND_PASSWORD (SDK)")
        print("\n   获取方式：")
        print("   1. 访问 https://quantapi.10jqka.com.cn")
        print("   2. 申请试用账号或购买正式账号")
        print("   3. 获取refresh_token或账号密码")
        return False

    # 测试HTTP API
    if refresh_token:
        print(f"   检测到 IFIND_REFRESH_TOKEN: {refresh_token[:20]}...")
        try:
            import requests
            url = "https://quantapi.51ifind.com/api/v1/get_access_token"
            headers = {
                "Content-Type": "application/json",
                "refresh_token": refresh_token
            }
            resp = requests.post(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                access_token = data.get("access_token", "")
                if access_token:
                    print(f"   OK: 获取access_token成功: {access_token[:20]}...")
                    return True
                else:
                    print(f"   ERROR: 响应中无access_token: {data}")
            else:
                print(f"   ERROR: HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"   ERROR: 连接失败: {e}")

    return False


def test_data_module():
    """测试数据模块导入"""
    print("\n" + "="*60)
    print("【测试3】数据模块导入测试")
    print("="*60)

    try:
        from tradingagents.dataflows.ifind_data import (
            IFindClient,
            get_stock_data_ifind,
            get_financial_indicators_ifind,
            get_capital_flow_ifind,
        )
        print("   OK: ifind_data 模块导入成功")

        # 测试客户端初始化
        client = IFindClient()
        print(f"   OK: IFindClient 初始化成功")
        print(f"   INFO: SDK可用: {client._sdk_available}")

        return True
    except Exception as e:
        print(f"   ERROR: 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_interface_integration():
    """测试接口集成"""
    print("\n" + "="*60)
    print("【测试4】数据路由集成测试")
    print("="*60)

    try:
        from tradingagents.dataflows.interface import (
            VENDOR_METHODS,
            VENDOR_LIST,
            TOOLS_CATEGORIES,
        )

        print(f"   OK: interface 模块导入成功")
        print(f"   INFO: 数据源列表: {VENDOR_LIST}")

        # 检查iFinD是否在vendor方法中
        if "ifind" in VENDOR_LIST:
            print("   OK: ifind 已添加到数据源列表")

        if "get_capital_flow" in TOOLS_CATEGORIES.get("capital_flow", {}).get("tools", []):
            print("   OK: capital_flow 工具类别已添加")

        # 检查vendor方法映射
        methods_with_ifind = []
        for method, vendors in VENDOR_METHODS.items():
            if "ifind" in vendors:
                methods_with_ifind.append(method)

        print(f"   INFO: iFinD支持的方法: {methods_with_ifind}")

        return True
    except Exception as e:
        print(f"   ERROR: 接口集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config():
    """测试配置文件"""
    print("\n" + "="*60)
    print("【测试5】配置文件测试")
    print("="*60)

    try:
        from tradingagents.default_config import DEFAULT_CONFIG

        data_vendors = DEFAULT_CONFIG.get("data_vendors", {})
        print(f"   OK: 配置文件加载成功")
        print(f"   INFO: 数据源配置:")

        for category, vendors in data_vendors.items():
            print(f"      - {category}: {vendors}")

        # 检查iFinD是否在配置中
        if any("ifind" in v for v in data_vendors.values()):
            print("   OK: ifind 已配置到数据源优先级中")
        else:
            print("   INFO: ifind 未在配置中（将使用默认数据源）")

        return True
    except Exception as e:
        print(f"   ERROR: 配置文件测试失败: {e}")
        return False


def main():
    print("="*60)
    print("同花顺iFinD数据源集成测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    results = {}

    # 运行测试
    results["SDK可用性"] = test_sdk_availability()
    results["HTTP API连接"] = test_http_api()
    results["数据模块导入"] = test_data_module()
    results["接口集成"] = test_interface_integration()
    results["配置文件"] = test_config()

    # 总结
    print("\n" + "="*60)
    print("【测试结果总结】")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, success in results.items():
        status = "OK" if success else "SKIP"
        print(f"   [{status}] {name}")

    print(f"\n通过率: {passed}/{total}")

    # 使用说明
    print("\n" + "="*60)
    print("【使用说明】")
    print("="*60)
    print("""
1. 免费使用（不配置iFinD）：
   系统会自动使用 efinance、akshare、yfinance 等免费数据源

2. 配置iFinD（获取更全面数据）：
   方式一（HTTP API）：
   export IFIND_REFRESH_TOKEN="your_refresh_token"

   方式二（SDK）：
   pip install iFinDAPI
   export IFIND_USERNAME="your_username"
   export IFIND_PASSWORD="your_password"

3. iFinD数据优势：
   - 资金流向数据（主力/散户资金动向）
   - 更全面的财务指标
   - 问财自然语言选股
   - 更稳定的API服务
    """)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
