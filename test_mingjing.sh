#!/bin/bash

echo "=== 统一测试接口 /v1/test/all ==="

# 调用统一测试接口
RESPONSE=$(curl -s -X GET http://localhost:8000/v1/test/all)

# 打印原始 JSON
echo "原始 JSON 响应："
echo "$RESPONSE" | jq .

echo
echo "=== 解析结果 ==="

# 解析非流式测试结果
NON_STREAM_STATUS=$(echo "$RESPONSE" | jq -r '.non_stream.status')
echo "非流式测试: $NON_STREAM_STATUS"

# 解析流式测试结果
STREAM_STATUS=$(echo "$RESPONSE" | jq -r '.stream.status')
echo "流式测试: $STREAM_STATUS"

# 解析伪频批量检测结果
echo
echo "伪频 + 空性三律检测结果："
echo "$RESPONSE" | jq -r '.detector[] | "输入: \(.input)\n违规类型: \(.violation_type)\n伪频规则: \(.fake_rule)\n三律规则: \(.three_laws_rule)\n结果: \(.result)\n---"'
