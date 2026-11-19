from django.contrib import admin

from apps.pagamentos.models import Cobranca


@admin.register(Cobranca)
class CobrancaAdmin(admin.ModelAdmin):
    list_display = ["asaas_payment_id", "consulta", "valor", "forma_pagamento", "status"]
    list_filter = ["status", "forma_pagamento"]
    readonly_fields = ["asaas_payment_id", "asaas_customer_id", "criado_em", "atualizado_em"]
