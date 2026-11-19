from django.contrib import admin

from apps.profissionais.models import Profissional


@admin.register(Profissional)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = ["id", "nome_social", "profissao", "cidade", "uf", "email"]
    search_fields = ["nome_social", "profissao", "email"]
    list_filter = ["uf", "profissao"]
