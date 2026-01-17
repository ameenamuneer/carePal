from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import User

class UserAuthTests(APITestCase):
    def setUp(self):
        self.register_url = reverse('users:register')
        self.login_url = reverse('users:login')
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'phone_number': '+1234567890',
            'password': 'TestPassword123!',
            'password_confirm': 'TestPassword123!',
            'user_type': 'PATIENT',
            'first_name': 'Test',
            'last_name': 'User',
            'date_of_birth': '1990-01-01'
        }

    def test_registration(self):
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().username, 'testuser')

    def test_login(self):
        self.client.post(self.register_url, self.user_data)
        login_data = {
            'username': 'testuser',
            'password': 'TestPassword123!'
        }
        response = self.client.post(self.login_url, login_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data['tokens'])

    def test_login_invalid_credentials(self):
        login_data = {
            'username': 'wronguser',
            'password': 'wrongpassword'
        }
        response = self.client.post(self.login_url, login_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
