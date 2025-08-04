#!/bin/bash
set -e

URL="http://localhost:8000/v1/test/all"

echo "=== 统一测试接口 /v1/test/all ==="
echo "请求 URL: $URL"
echo

# 获取 JSON
json=$(curl -s "$URL")
echo "原始 JSON 响应："
echo "$json" | jq .
echo

# 解析关键字段
timestamp=$(echo "$json" | jq -r '.timestamp // empty')
api_key_loaded=$(echo "$json" | jq -r '.connection.api_key_loaded // empty')
openai_reachable=$(echo "$json" | jq -r '.connection.openai_reachable // empty')
non_stream_status=$(echo "$json" | jq -r '.non_stream.status // empty')
stream_status=$(echo "$json" | jq -r '.stream.status // empty')

sig_status=$(echo "$json" | jq -r '.signature_verification.status // empty')
sig_reason=$(echo "$json" | jq -r '.signature_verification.reason // empty')

freq_score=$(echo "$json" | jq -r '.frequency_shift.score // empty')
freq_desc=$(echo "$json" | jq -r '.frequency_shift.description // empty')

firewall_status=$(echo "$json" | jq -r '.firewall.status // empty')
firewall_reason=$(echo "$json" | jq -r '.firewall.reason // empty')
sig_ok=$(echo "$json" | jq -r '.firewall.signature_ok // empty')
freq_score_fw=$(echo "$json" | jq -r '.firewall.freq_score // empty')

all_passed=$(echo "$json" | jq -r '.summary.all_passed // empty')

# 彩色函数
green=$(tput setaf 2)
red=$(tput setaf 1)
reset=$(tput sgr0)

# 打印解析结果
echo "=== 解析结果 ==="
echo "测试时间: $timestamp"
echo "API Key 加载: $api_key_loaded"
echo "OpenAI 连通性: $openai_reachable"
echo "非流式测试: $non_stream_status"
echo "流式测试: $stream_status"
echo "签名验证: $sig_status ($sig_reason)"
echo "频率偏移: $freq_desc (得分: $freq_score)"

# 防火墙结果彩色显示
if [[ "$firewall_status" == "通过" ]]; then
    echo "防火墙结果: ${green}${firewall_status}${reset} (${firewall_reason}) | 签名=$sig_ok, 偏移=$freq_score_fw"
else
    echo "防火墙结果: ${red}${firewall_status}${reset} (${firewall_reason}) | 签名=$sig_ok, 偏移=$freq_score_fw"
fi

# 总体结果
if [[ "$all_passed" == "true" ]]; then
    echo "${green}🎉 所有测试通过${reset}"
else
    echo "${red}❌ 部分测试失败${reset}"
fi

echo
echo "伪频 + 空性三律检测结果："
echo "$json" | jq -r '.detector[] | "输入: \(.input)\n违规类型: \(.violation_type)\n伪频规则: \(.fake_rule)\n三律规则: \(.three_laws_rule)\n结果: \(.result)\n---"'
