#!/bin/bash
set -e

API_URL="http://localhost:8000/v1/test/all"

# 检查 jq 是否安装
if ! command -v jq &> /dev/null; then
    echo "❌ 缺少 jq，请先安装："
    echo "macOS: brew install jq"
    echo "Ubuntu/Debian: sudo apt-get install jq"
    exit 1
fi

echo "=== 统一测试接口 /v1/test/all ==="

# 调用接口
RESPONSE=$(curl -s $API_URL)

# 检查返回是否为空或错误
if [ -z "$RESPONSE" ]; then
    echo "❌ 无响应，请检查后端服务是否启动"
    exit 1
fi

# 尝试解析 JSON，若失败直接输出原始内容
if ! echo "$RESPONSE" | jq . >/dev/null 2>&1; then
    echo "❌ 返回内容不是合法 JSON："
    echo "$RESPONSE"
    exit 1
fi

echo "原始 JSON 响应："
echo "$RESPONSE" | jq .

echo
echo "=== 解析结果 ==="

# 解析连接状态
API_KEY_LOADED=$(echo "$RESPONSE" | jq -r '.connection.api_key_loaded')
OPENAI_REACHABLE=$(echo "$RESPONSE" | jq -r '.connection.openai_reachable')

echo "API Key 已加载: $API_KEY_LOADED"
echo "OpenAI API 可连通: $OPENAI_REACHABLE"

# 解析非流式结果
NON_STREAM=$(echo "$RESPONSE" | jq -r '.non_stream')
echo "非流式测试: $NON_STREAM"

# 解析流式结果
STREAM=$(echo "$RESPONSE" | jq -r '.stream')
echo "流式测试: $STREAM"

echo
echo "伪频 + 空性三律检测结果："
echo "------------------------"

# 遍历 detector 数组
echo "$RESPONSE" | jq -c '.detector[]' | while read -r item; do
    INPUT=$(echo "$item" | jq -r '.input')
    VIOLATION=$(echo "$item" | jq -r '.violation_type')
    FAKE_RULE=$(echo "$item" | jq -r '.fake_rule')
    THREE_RULE=$(echo "$item" | jq -r '.three_laws_rule')
    RESULT=$(echo "$item" | jq -r '.result')

    echo "输入: $INPUT"
    echo "违规类型: $VIOLATION"
    echo "伪频规则: $FAKE_RULE"
    echo "三律规则: $THREE_RULE"
    echo "结果: $RESULT"
    echo "---"
done
