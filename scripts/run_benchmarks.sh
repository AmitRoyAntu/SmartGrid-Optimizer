#!/usr/bin/env bash
# ==============================================================================
# GridWise LLM Smart Campus Energy Optimizer - Benchmark & Verification Runner
# Developed by Member 4 (DevOps, Quality & Presentation Lead)
# ==============================================================================

set -eo pipefail

BASE_URL="${1:-http://localhost:8000}"
PAYLOADS_FILE="$(dirname "$0")/../tests/sample_payloads.json"

# Text Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}  ⚡ GridWise LLM API Automated Benchmark & Verification Runner             ${NC}"
echo -e "${BLUE}  Target Endpoint: ${CYAN}${BASE_URL}${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""

# ------------------------------------------------------------------------------
# 1. Test GET /health
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[1/3] Probing GET /health readiness...${NC}"

HEALTH_START=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
HEALTH_RESP=$(curl -s -w "\n%{http_code}" "${BASE_URL}/health" || echo -e "\n000")
HEALTH_CODE=$(echo "$HEALTH_RESP" | tail -n 1)
HEALTH_BODY=$(echo "$HEALTH_RESP" | sed '$d')
HEALTH_END=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')

HEALTH_MS=$(( (HEALTH_END - HEALTH_START) / 1000000 ))

if [ "$HEALTH_CODE" -eq 200 ] && [[ "$HEALTH_BODY" =~ "ok" ]]; then
    echo -e "  ${GREEN}✓ GET /health PASSED${NC} (HTTP 200, Latency: ${HEALTH_MS}ms)"
    echo -e "  Response: ${HEALTH_BODY}"
else
    echo -e "  ${RED}✗ GET /health FAILED${NC} (HTTP ${HEALTH_CODE})"
    echo -e "  Response: ${HEALTH_BODY}"
    echo -e "${RED}Aborting: Service is not healthy or unreachable.${NC}"
    exit 1
fi

echo ""

# ------------------------------------------------------------------------------
# 2. Test POST /optimize-energy across Scenarios
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[2/3] Running POST /optimize-energy on Sample Scenarios...${NC}"

if [ ! -f "$PAYLOADS_FILE" ]; then
    echo -e "${RED}Error: Payloads file not found at ${PAYLOADS_FILE}${NC}"
    exit 1
fi

# Extract scenario count using python
TOTAL_SCENARIOS=$(python3 -c "import json; data=json.load(open('$PAYLOADS_FILE')); print(len(data['sample_scenarios']))")

for (( i=0; i<$TOTAL_SCENARIOS; i++ )); do
    SCENARIO_JSON=$(python3 -c "import json; data=json.load(open('$PAYLOADS_FILE')); print(json.dumps(data['sample_scenarios'][$i]))")
    SCENARIO_ID=$(python3 -c "import json; print(json.loads('''$SCENARIO_JSON''')['scenario_id'])")

    echo -e "  Testing Scenario: ${CYAN}${SCENARIO_ID}${NC}..."

    OPT_START=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
    OPT_RESP=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/optimize-energy" \
        -H "Content-Type: application/json" \
        -d "$SCENARIO_JSON" || echo -e "\n000")
    OPT_CODE=$(echo "$OPT_RESP" | tail -n 1)
    OPT_BODY=$(echo "$OPT_RESP" | sed '$d')
    OPT_END=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')

    OPT_MS=$(( (OPT_END - OPT_START) / 1000000 ))

    if [ "$OPT_CODE" -eq 200 ]; then
        # Validate required response keys using python
        VALIDATION=$(python3 -c "
import json, sys
try:
    resp = json.loads('''$OPT_BODY''')
    req_keys = ['scenario_id', 'directive_interpretation', 'hourly_plan', 'total_grid_kwh', 'total_cost_bdt', 'peak_grid_kwh', 'plan_summary']
    missing = [k for k in req_keys if k not in resp]
    if missing:
        print(f'MISSING_KEYS:{missing}')
        sys.exit(1)
    if len(resp.get('hourly_plan', [])) != 24:
        print('HOURLY_PLAN_LENGTH_ERROR')
        sys.exit(1)
    print(f\"TOTAL_COST:{resp.get('total_cost_bdt', 0):.2f}|TOTAL_GRID:{resp.get('total_grid_kwh', 0):.2f}|PEAK:{resp.get('peak_grid_kwh', 0):.2f}\")
except Exception as e:
    print(f'PARSING_ERROR:{e}')
    sys.exit(1)
")
        if [[ "$VALIDATION" =~ "TOTAL_COST" ]]; then
            echo -e "    ${GREEN}✓ SUCCESS${NC} (HTTP 200, Latency: ${OPT_MS}ms)"
            echo -e "    Metrics: ${VALIDATION}"
            if [ "$OPT_MS" -le 5000 ]; then
                echo -e "    Latency Check: ${GREEN}PASS (<= 5000ms)${NC}"
            else
                echo -e "    Latency Check: ${YELLOW}WARN (> 5000ms)${NC}"
            fi
        else
            echo -e "    ${RED}✗ FAILED VALIDATION${NC}: ${VALIDATION}"
        fi
    else
        echo -e "    ${RED}✗ FAILED (HTTP ${OPT_CODE})${NC}"
        echo -e "    Response preview: ${OPT_BODY:0:300}..."
    fi
    echo ""
done

# ------------------------------------------------------------------------------
# 3. Summary
# ------------------------------------------------------------------------------
echo -e "${BLUE}==============================================================================${NC}"
echo -e "${GREEN}✓ Benchmark run completed successfully.${NC}"
echo -e "${BLUE}==============================================================================${NC}"
