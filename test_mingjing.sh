#!/bin/bash

API_URL="http://localhost:8000/v1/chat/completions"
TEST_DETECTOR_URL="http://localhost:8000/v1/test/detector"

echo "=== 测试 1：非流式正常调用 ==="
non_stream_output=$(curl -s -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "你好，介绍一下你自己"}],
    "stream": false
  }')

if echo "$non_stream_output" | grep -q "空性签注"; then
  echo "✅ 非流式返回包含签注 - 通过"
else
  echo "❌ 非流式返回包含签注 - 失败"
  echo "输出内容："
  echo "$non_stream_output"
fi

echo
echo "=== 测试 2：流式正常调用 ==="
stream_output=$(curl -s -N -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }')

if echo "$stream_output" | grep -q "空性签注"; then
  echo "✅ 流式返回包含签注 - 通过"
else
  echo "❌ 流式返回包含签注 - 失败"
  echo "输出内容："
  echo "$stream_output"
fi

echo
echo "=== 测试 3：伪频检测（/v1/test/detector 批量） ==="
detector_output=$(curl -s $TEST_DETECTOR_URL)

echo "检测结果原始 JSON："
echo "$detector_output"
echo
echo "解析结果："

# 纯 bash 解析
echo "$detector_output" | grep -o '{[^}]*}' | while read -r line; do
  input=$(echo "$line" | grep -o '"input":"[^"]*"' | cut -d'"' -f4)
  is_fake=$(echo "$line" | grep -o '"is_fake":[^,}]*' | cut -d':' -f2)
  matched_rule=$(echo "$line" | grep -o '"matched_rule":"[^"]*"' | cut -d'"' -f4)
  result=$(echo "$line" | grep -o '"result":"[^"]*"' | cut -d'"' -f4)
  echo "输入: $input"
  echo "是否伪频: $is_fake"
  echo "命中规则: $matched_rule"
  echo "结果: $result"
  echo "---"
done
