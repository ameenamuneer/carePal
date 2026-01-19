#!/bin/bash
BASE_URL="http://localhost:8000"

echo "1. Login"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"username":"test_patient","password":"Test@1234"}')
TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['tokens']['access'])")

echo "Token: $TOKEN"

echo -e "\n2. Dashboard Debug"
curl -v -X GET "$BASE_URL/api/v1/analytics/dashboard/" \
  -H "Authorization: Bearer $TOKEN"

echo -e "\n3. Medications Debug"
curl -v -X GET "$BASE_URL/api/v1/medications/todays-schedule/" \
  -H "Authorization: Bearer $TOKEN"
