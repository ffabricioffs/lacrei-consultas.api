from django.contrib import admin

from apps.consultas.models import Consulta


@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    list_display = ["id", "profissional", "data_hora", "status", "valor"]
    list_filter = ["status"]
    list_select_related = ["profissional"]
    raw_id_fields = ["profissional"]
