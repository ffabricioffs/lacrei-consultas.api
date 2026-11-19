"""
Clientes da API do Asaas (real e mock).

Documentação pública: https://docs.asaas.com
- Autenticação: cabeçalho `access_token` com a chave de API.
- Clientes:   POST /v3/customers
- Cobranças:  POST /v3/payments  (aceita `split: [{walletId, percentualValue}]`)
"""

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Protocol

import requests
from django.conf import settings

logger = logging.getLogger("lacrei.pagamentos")


class AsaasError(Exception):
    """Falha de comunicação ou erro de negócio retornado pelo Asaas."""


class AsaasGateway(Protocol):
    def criar_cliente(self, *, nome: str, cpf_cnpj: str, email: str | None = None) -> dict: ...

    def criar_cobranca(
        self,
        *,
        customer_id: str,
        valor: Decimal,
        vencimento: date,
        forma_pagamento: str,
        descricao: str,
        referencia_externa: str,
        split: list[dict],
    ) -> dict: ...


class AsaasClient:
    """Cliente HTTP real (sandbox ou produção, conforme `ASAAS_API_URL`)."""

    def __init__(self, api_url: str | None = None, api_key: str | None = None, timeout=None):
        self.api_url = (api_url or settings.ASAAS_API_URL).rstrip("/")
        self.api_key = api_key or settings.ASAAS_API_KEY
        self.timeout = timeout or settings.ASAAS_TIMEOUT_SECONDS

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = requests.request(
                "POST",
                f"{self.api_url}{path}",
                json=payload,
                headers={
                    "access_token": self.api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "lacrei-consultas-api",
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.error("Falha de rede ao chamar o Asaas", extra={"path": path})
            raise AsaasError("Falha de comunicação com o Asaas.") from exc

        if response.status_code >= 400:
            # Não registramos o payload (contém dados pessoais), apenas o status.
            logger.error(
                "Asaas retornou erro", extra={"path": path, "status": response.status_code}
            )
            raise AsaasError(f"Asaas retornou HTTP {response.status_code}.")
        return response.json()

    def criar_cliente(self, *, nome: str, cpf_cnpj: str, email: str | None = None) -> dict:
        payload = {"name": nome, "cpfCnpj": cpf_cnpj}
        if email:
            payload["email"] = email
        return self._post("/customers", payload)

    def criar_cobranca(
        self,
        *,
        customer_id: str,
        valor: Decimal,
        vencimento: date,
        forma_pagamento: str,
        descricao: str,
        referencia_externa: str,
        split: list[dict],
    ) -> dict:
        return self._post(
            "/payments",
            {
                "customer": customer_id,
                "billingType": forma_pagamento,
                "value": float(valor),
                "dueDate": vencimento.isoformat(),
                "description": descricao,
                "externalReference": referencia_externa,
                "split": split,
            },
        )


class AsaasMockClient:
    """
    Implementação em memória com o mesmo contrato do cliente real.
    Usada por padrão (`ASAAS_MOCK=True`) em desenvolvimento, testes e staging.
    """

    def criar_cliente(self, *, nome: str, cpf_cnpj: str, email: str | None = None) -> dict:
        return {"id": f"cus_mock_{uuid.uuid4().hex[:12]}", "name": nome}

    def criar_cobranca(
        self,
        *,
        customer_id: str,
        valor: Decimal,
        vencimento: date,
        forma_pagamento: str,
        descricao: str,
        referencia_externa: str,
        split: list[dict],
    ) -> dict:
        payment_id = f"pay_mock_{uuid.uuid4().hex[:12]}"
        return {
            "id": payment_id,
            "customer": customer_id,
            "status": "PENDING",
            "value": float(valor),
            "billingType": forma_pagamento,
            "dueDate": vencimento.isoformat(),
            "invoiceUrl": f"https://sandbox.asaas.com/i/{payment_id}",
            "externalReference": referencia_externa,
            "split": split,
        }


def get_asaas_client() -> AsaasGateway:
    return AsaasMockClient() if settings.ASAAS_MOCK else AsaasClient()
