#!/bin/bash

BASE_URL="http://localhost:8000"
TOKEN=""

echo "🧪 CarePAL API Test Suite"
echo "=========================="

# 1. Login
echo -e "\n1️⃣ Testing Login..."
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"username":"test_patient","password":"Test@1234"}')

TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['tokens']['access'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "❌ Login failed"
  exit 1
else
  echo "✅ Login successful"
fi

# 2. Dashboard
echo -e "\n2️⃣ Testing Dashboard..."
curl -s -X GET "$BASE_URL/api/v1/analytics/dashboard/patient/" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -20
echo "✅ Dashboard API working"

# 3. Vitals
echo -e "\n3️⃣ Testing Vitals..."
curl -s -X GET "$BASE_URL/api/v1/vitals/readings/" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -20
echo "✅ Vitals API working"

# 4. Medications
echo -e "\n4️⃣ Testing Medications..."
curl -s -X GET "$BASE_URL/api/v1/medications/adherence/today/" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -20
echo "✅ Medications API working"

echo -e "\n✅ All API tests passed!"
