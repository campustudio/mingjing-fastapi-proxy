#!/bin/bash
# 速率限制测试脚本

echo "🧪 开始测试后端速率限制..."
echo ""

BASE_URL="${1:-http://127.0.0.1:8000}"
echo "测试目标: $BASE_URL"
echo ""

# 测试聊天接口限流（30次/分钟）
echo "📝 测试聊天接口限流（限制: 30次/分钟）"
echo "发送35个请求，预期第31-35个返回429..."
echo ""

success_count=0
rate_limited_count=0

for i in {1..35}; do
  response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"test"}]}' 2>/dev/null)
  
  status_code=$(echo "$response" | tail -n1)
  
  if [ "$status_code" = "200" ]; then
    success_count=$((success_count + 1))
    echo "  ✅ 请求 #$i: 成功 (200)"
  elif [ "$status_code" = "429" ]; then
    rate_limited_count=$((rate_limited_count + 1))
    echo "  🚫 请求 #$i: 被限流 (429)"
  else
    echo "  ❌ 请求 #$i: 错误 ($status_code)"
  fi
  
  # 稍微延迟避免网络拥塞
  sleep 0.05
done

echo ""
echo "结果统计:"
echo "  成功: $success_count"
echo "  被限流: $rate_limited_count"
echo ""

if [ $rate_limited_count -gt 0 ]; then
  echo "✅ 速率限制工作正常！"
else
  echo "⚠️  未检测到速率限制，请检查配置"
fi

echo ""
echo "💡 提示: 等待60秒后限流计数器会重置"
