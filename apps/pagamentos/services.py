"""Regras de negócio de cobrança (independentes de HTTP)."""

import logging
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.consultas.models import Consulta
from apps.core.exceptions import Conflito, ServicoExternoIndisponivel
from apps.pagamentos.asaas import AsaasError, get_asaas_client
from apps.pagamentos.models import Cobranca

logger = logging.getLogger("lacrei.pagamentos")

# Eventos de webhook que alteram o status da cobrança.
# https://docs.asaas.com/docs/webhook-para-cobrancas
EVENTOS_STATUS = {
    "PAYMENT_CREATED",
    "PAYMENT_UPDATED",
    "PAYMENT_CONFIRMED",
    "PAYMENT_RECEIVED",
    "PAYMENT_OVERDUE",
    "PAYMENT_DELETED",
    "PAYMENT_REFUNDED",
    "PAYMENT_RECEIVED_IN_CASH_UNDONE",
    "PAYMENT_CHARGEBACK_REQUESTED",
}


def gerar_cobranca(
    consulta: Consulta,
    *,
    paciente_nome: str,
    paciente_cpf_cnpj: str,
    paciente_email: str | None = None,
    forma_pagamento: str,
    vencimento: date,
    valor: Decimal | None = None,
) -> Cobranca:
    """
    Cria cliente + cobrança no Asaas com split para a carteira da pessoa profissional.

    O percentual (`ASAAS_PERCENTUAL_PROFISSIONAL`) incide sobre o valor líquido;
    o restante permanece na conta emissora (Lacrei Saúde).
    """
    if consulta.status == Consulta.Status.CANCELADA:
        raise ValidationError({"consulta": ["Não é possível cobrar uma consulta cancelada."]})
    if Cobranca.objects.filter(consulta=consulta).exists():
        raise Conflito("Esta consulta já possui cobrança.")

    profissional = consulta.profissional
    if not profissional.asaas_wallet_id:
        raise ValidationError(
            {"profissional": ["Profissional sem carteira Asaas (asaas_wallet_id) cadastrada."]}
        )

    valor_final = valor if valor is not None else consulta.valor
    if valor_final is None or valor_final <= 0:
        raise ValidationError({"valor": ["Informe o valor ou cadastre-o na consulta."]})

    percentual = settings.ASAAS_PERCENTUAL_PROFISSIONAL
    split = [{"walletId": str(profissional.asaas_wallet_id), "percentualValue": float(percentual)}]

    client = get_asaas_client()
    try:
        cliente = client.criar_cliente(
            nome=paciente_nome, cpf_cnpj=paciente_cpf_cnpj, email=paciente_email
        )
        pagamento = client.criar_cobranca(
            customer_id=cliente["id"],
            valor=valor_final,
            vencimento=vencimento,
            forma_pagamento=forma_pagamento,
            descricao=f"Consulta com {profissional.nome_social}",
            referencia_externa=f"consulta:{consulta.pk}",
            split=split,
        )
    except AsaasError as exc:
        raise ServicoExternoIndisponivel() from exc

    with transaction.atomic():
        cobranca = Cobranca.objects.create(
            consulta=consulta,
            asaas_payment_id=pagamento["id"],
            asaas_customer_id=cliente["id"],
            valor=valor_final,
            forma_pagamento=forma_pagamento,
            vencimento=vencimento,
            percentual_profissional=percentual,
            status=pagamento.get("status", "PENDING"),
            link_pagamento=pagamento.get("invoiceUrl", ""),
        )
    logger.info(
        "Cobrança criada",
        extra={"consulta_id": consulta.pk, "asaas_payment_id": cobranca.asaas_payment_id},
    )
    return cobranca


def processar_webhook(payload: dict) -> bool:
    """
    Atualiza o status da cobrança a partir de um evento do Asaas.
    Idempotente: reprocessar o mesmo evento não muda o resultado.
    Retorna True se alguma cobrança foi atualizada.
    """
    evento = payload.get("event")
    pagamento = payload.get("payment") or {}
    payment_id = pagamento.get("id")
    novo_status = pagamento.get("status")

    if evento not in EVENTOS_STATUS or not payment_id or not novo_status:
        logger.info("Webhook Asaas ignorado", extra={"evento": evento})
        return False

    atualizadas = Cobranca.objects.filter(asaas_payment_id=payment_id).update(
        status=str(novo_status)[:40]
    )
    if not atualizadas:
        logger.warning("Webhook para cobrança desconhecida", extra={"asaas_payment_id": payment_id})
    return bool(atualizadas)
