
from django.db import close_old_connections
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model

@database_sync_to_async
def get_user(user_id):
    try:
        User = get_user_model()
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()

class QueryAuthMiddleware:
    """
    Custom middleware to authenticate users via JWT token in query string.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        close_old_connections()
        
        # Get the token from query string
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            try:
                # Validate the token and get payload
                validated_token = UntypedToken(token)
                user_id = validated_token["user_id"]
                
                # Get the user
                scope["user"] = await get_user(user_id)
                
            except (InvalidToken, TokenError, Exception) as e:
                # Token is invalid
                # print(f"JWT Auth Error: {e}")
                scope["user"] = AnonymousUser()
        else:
            # If no token, leave it as is (AuthMiddlewareStack might have set it, or it defaults to Anonymous)
            # Generally, AuthMiddlewareStack sets scope['user'] to AnonymousUser if session auth fails.
            pass

        return await self.app(scope, receive, send)
