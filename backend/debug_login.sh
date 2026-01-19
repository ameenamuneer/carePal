#!/bin/bash
BASE_URL="http://localhost:8000"

echo "Attempting login for test_patient..."
curl -v -X POST "$BASE_URL/api/v1/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"username":"test_patient","password":"Test@1234"}'
