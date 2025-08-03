#!/bin/bash

# ============ 颜色定义 ============
GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
CYAN="\033[36m"
BOLD="\033[1m"
RESET="\033[0m"

API_URL="http://localhost:8000/v1/test/all"

echo -e "${CYAN}=== 统一测试接口 /v1/test/all ===${RESET}"
echo "请求 URL: $API_URL"
echo

# 调用 API
RESPONSE=$(curl -s $API_URL)

# 检查返回是否是 JSON
if ! echo "$RESPONSE" | jq . >/dev/null 2>&1; then
  echo -e "${RED}错误：返回的不是 JSON${RESET}"
  echo "$RESPONSE"
  exit 1
fi

echo "原始 JSON 响应："
echo "$RESPONSE" | jq .
echo

# ============ 解析关键字段 ============
TIMESTAMP=$(echo "$RESPONSE" | jq -r '.timestamp')
API_KEY_LOADED=$(echo "$RESPONSE" | jq -r '.connection.api_key_loaded')
OPENAI_REACHABLE=$(echo "$RESPONSE" | jq -r '.connection.openai_reachable')
NON_STREAM_STATUS=$(echo "$RESPONSE" | jq -r '.non_stream.status')
STREAM_STATUS=$(echo "$RESPONSE" | jq -r '.stream.status')
SIGN_STATUS=$(echo "$RESPONSE" | jq -r '.signature_verification.status')
ALL_PASSED=$(echo "$RESPONSE" | jq -r '.summary.all_passed')

# 彩色打印函数
print_status() {
  local label="$1"
  local status="$2"
  if [[ "$status" == "true" || "$status" == "包含签注" || "$status" == "有效" ]]; then
    echo -e "${GREEN}${label}: ${status}${RESET}"
  else
    echo -e "${RED}${label}: ${status}${RESET}"
  fi
}

# ============ 汇总显示 ============
echo -e "${CYAN}=== 解析结果 ===${RESET}"
echo "测试时间: $TIMESTAMP"
print_status "API Key 加载" "$API_KEY_LOADED"
print_status "OpenAI 连通性" "$OPENAI_REACHABLE"
print_status "非流式测试" "$NON_STREAM_STATUS"
print_status "流式测试" "$STREAM_STATUS"
print_status "签名验证" "$SIGN_STATUS"

if [[ "$ALL_PASSED" == "true" ]]; then
  echo -e "${BOLD}${GREEN}🎉 所有测试通过${RESET}"
else
  echo -e "${BOLD}${RED}❌ 部分测试失败${RESET}"
  FAILED=$(echo "$RESPONSE" | jq -r '.summary.failed_modules[]')
  echo -e "${RED}失败模块: $FAILED${RESET}"
fi

# ============ 伪频检测详细 ============
echo
echo -e "${CYAN}伪频 + 空性三律检测结果：${RESET}"

echo "$RESPONSE" | jq -c '.detector[]' | while read -r item; do
  input=$(echo "$item" | jq -r '.input')
  violation_type=$(echo "$item" | jq -r '.violation_type')
  fake_rule=$(echo "$item" | jq -r '.fake_rule')
  three_laws_rule=$(echo "$item" | jq -r '.three_laws_rule')
  result=$(echo "$item" | jq -r '.result')

  # 彩色高亮违规类型
  if [[ "$violation_type" == "正常" ]]; then
    echo -e "${GREEN}输入: $input${RESET}"
    echo "违规类型: $violation_type"
  else
    echo -e "${RED}输入: $input${RESET}"
    echo "违规类型: $violation_type"
  fi
  echo "伪频规则: $fake_rule"
  echo "三律规则: $three_laws_rule"
  echo "结果: $result"
  echo "---"
done
