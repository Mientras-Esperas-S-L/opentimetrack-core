"""Registering and dropping a browser for notifications.

Three calls, all about the caller's own devices and nobody else's: what the
public key is, register this browser, drop this browser. There is no listing of
somebody else's subscriptions and no way to notify a person from the API ---
what gets sent is decided by the product, not by whoever holds a token.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAuthenticatedInTenant
from apps.notifications.models import PushSubscription
from apps.notifications.push import push_is_configured


class PushKeyView(APIView):
    """The deployment's public key, and whether push is on at all.

    Unauthenticated on purpose: it is the *public* half of a key pair, the
    browser needs it before subscribing, and it says nothing about anybody.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["notifications"], responses={200: dict})
    def get(self, request):
        from django.conf import settings

        return Response(
            {
                "enabled": push_is_configured(),
                "public_key": settings.WEBPUSH_PUBLIC_KEY if push_is_configured() else "",
            }
        )


class PushSubscriptionSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=500)
    p256dh = serializers.CharField(max_length=200)
    auth = serializers.CharField(max_length=100)
    device_label = serializers.CharField(
        max_length=80, required=False, allow_blank=True, default=""
    )


class PushUnsubscribeRequestSerializer(serializers.Serializer):
    """Cuál se da de baja. Se acepta en el cuerpo o como parámetro."""

    endpoint = serializers.CharField(
        required=False,
        help_text="Sin él se dan de baja todas las suscripciones de esta persona.",
    )


class PushSubscriptionView(APIView):
    """The caller's own browsers.

    `IsAuthenticatedInTenant` rather than plain `IsAuthenticated`: it is what
    puts the company in context, and without it the tenant-scoped manager sees
    nothing --- so re-subscribing the same browser would insert a second row
    instead of updating the first.
    """

    permission_classes = [IsAuthenticatedInTenant]

    @extend_schema(
        tags=["notifications"], request=PushSubscriptionSerializer, responses={201: dict}
    )
    def post(self, request):
        form = PushSubscriptionSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        # Re-subscribing on the same browser gives the same endpoint back, and
        # its keys are rotated by the browser now and then. Updating rather than
        # inserting is what stops one laptop becoming five rows and five copies
        # of every notification.
        PushSubscription.objects.update_or_create(
            endpoint=data["endpoint"],
            defaults={
                "tenant": request.user.tenant,
                "employee": request.user,
                "p256dh": data["p256dh"],
                "auth": data["auth"],
                "device_label": data.get("device_label", ""),
            },
        )
        return Response({"subscribed": True}, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["notifications"],
        request=PushUnsubscribeRequestSerializer,
        parameters=[
            OpenApiParameter(
                "endpoint",
                str,
                description=(
                    "Cuál se da de baja. **Sin él se dan de baja todas las de esta "
                    "persona**, que a veces es lo que se quiere ---cerrar sesión en "
                    "todas partes--- y a veces no. Se acepta también en el cuerpo."
                ),
            )
        ],
        responses={204: None},
    )
    def delete(self, request):
        endpoint = request.data.get("endpoint") or request.query_params.get("endpoint")
        rows = PushSubscription.objects.filter(employee=request.user)
        # Filtered by the caller either way: an endpoint is a long opaque URL,
        # but guessing one must not let somebody silence another person's phone.
        if endpoint:
            rows = rows.filter(endpoint=endpoint)
        rows.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
