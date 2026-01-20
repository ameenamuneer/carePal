#!/bin/bash

echo "🔍 CarePAL Debug Output"
echo "======================="

echo -e "\n📦 Backend Status:"
cd ../backend
python3 -c "
import django
import os
import sys

# Add backend to path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carepal.settings')
django.setup()
from django.contrib.auth import get_user_model
print(f'Users: {get_user_model().objects.count()}')
" 2>/dev/null

echo -e "\n📱 Flutter Status:"
cd ../carepal_app
flutter doctor 2>/dev/null | grep -E "Flutter|Android toolchain|Xcode|Chrome" || echo "Flutter doctor failed or suppressed"

echo -e "\n🌐 Backend Port Check:"
lsof -i :8000 | head -n 2 

echo -e "\n🌐 Frontend/Chrome Port Check (3000-ish?):"
# Flutter web usually runs on arbitrary ports unless specified, checking standard dev ranges
lsof -i :3000 | head -n 2 || echo "Port 3000 not in use"

echo -e "\nDone!"
