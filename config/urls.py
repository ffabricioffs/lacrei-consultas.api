from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.consultas.views import ConsultaViewSet
from apps.core.views import health_check
from apps.pagamentos.views import AsaasWebhookView, CobrancaConsultaView
from apps.profissionais.views import ProfissionalViewSet

router = DefaultRouter()
router.register("profissionais", ProfissionalViewSet, basename="profissional")
router.register("consultas", ConsultaViewSet, basename="consulta")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health"),
    # Autenticação (JWT)
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Pagamentos (Asaas)
    path(
        "api/v1/consultas/<int:consulta_id>/cobranca/",
        CobrancaConsultaView.as_view(),
        name="consulta-cobranca",
    ),
    path(
        "api/v1/pagamentos/webhook/asaas/",
        AsaasWebhookView.as_view(),
        name="asaas-webhook",
    ),
    # Recursos principais
    path("api/v1/", include(router.urls)),
    # Documentação da API
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Respostas de erro em JSON também fora do DRF.
handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"
