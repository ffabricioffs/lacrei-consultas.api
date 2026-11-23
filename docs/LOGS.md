# Política de logs: finalidade, dados, acesso e retenção

Este documento descreve os logs da API que registram dados de rede (IP e user agent), por que existem, quem pode acessá-los e por quanto tempo ficam guardados. A base legal indicada deve ser validada pelo encarregado de dados (DPO) da Lacrei Saúde.

## 1. Quais logs existem

| Logger | Quando é gerado | Conteúdo |
|---|---|---|
| `lacrei.access` | Uma linha por requisição HTTP | `timestamp`, `request_id`, `method`, `path`, `status`, `duration_ms`, `user_id`, `ip` (anonimizado), `user_agent` (até 200 caracteres) |
| `lacrei.errors` | Exceções não tratadas e respostas 5xx | Mensagem, stack trace, `request_id`, rota, método e nome da view |
| `lacrei.pagamentos` | Eventos da integração com o Asaas | IDs do Asaas e da consulta, status HTTP do Asaas |
| Proxy (Caddy) | Erros do proxy e emissão de certificados | Sem log de acesso habilitado: o proxy **não** registra IP nem user agent |

Exemplo de linha de acesso:

```json
{"timestamp": "2026-11-23T18:40:00+00:00", "level": "INFO", "logger": "lacrei.access", "message": "GET /api/v1/consultas/ 200", "request_id": "3f2a…", "method": "GET", "path": "/api/v1/consultas/", "status": 200, "duration_ms": 12.4, "user_id": 1, "ip": "203.0.113.0", "user_agent": "Mozilla/5.0 …"}
```

## 2. O que **não** é registrado

- Corpo das requisições e das respostas (nomes, e-mails, telefones, endereços, CPF/CNPJ).
- Query string (por exemplo, `?search=`), que pode conter dados pessoais.
- Cabeçalho `Authorization`, tokens JWT, senhas e o token do webhook do Asaas.
- O IP completo: só o prefixo de rede (veja a seção 4).

## 3. Finalidade

| Dado | Por que é registrado |
|---|---|
| `ip` (prefixo de rede) | Segurança: identificar abuso, força bruta no login e varreduras por faixa de rede, e calibrar o rate limiting |
| `user_agent` | Segurança e diagnóstico: distinguir clientes legítimos de scripts automatizados e reproduzir erros de clientes específicos |
| `user_id` + `request_id` | Auditoria (qual conta fez qual operação) e correlação entre o log de acesso e o log de erro da mesma requisição |
| `status`, `duration_ms`, `path` | Diagnóstico e desempenho (erros, lentidão, rotas mais usadas) |

Base legal sugerida: legítimo interesse e segurança da informação (LGPD, art. 7º, IX, e art. 46), com minimização de dados (art. 6º, III). Os registros não são usados para perfilamento, marketing nem compartilhados com terceiros.

## 4. Minimização: anonimização do IP

O `RequestLoggingMiddleware` (`apps/core/middleware.py`) grava apenas o prefixo de rede do IP:

| Tipo | Prefixo mantido | Exemplo |
|---|---|---|
| IPv4 | /24 | `203.0.113.42` → `203.0.113.0` |
| IPv6 | /48 | `2001:db8:abcd:12::1` → `2001:db8:abcd::` |

Isso preserva a utilidade para segurança (bloqueio por faixa, origem aproximada) sem registrar o endereço individual. O comportamento é controlado por `LOG_ANONYMIZE_IP` (padrão `true`) e coberto por testes em `apps/core/tests.py`. O user agent é truncado em 200 caracteres.

## 5. Onde ficam e quem acessa

- **Armazenamento:** a aplicação escreve no stdout do container. O Docker grava em `/var/lib/docker/containers/<id>/<id>-json.log` na EC2, em diretório acessível apenas a `root` e ao grupo `docker`.
- **Quem acessa:** apenas administradores da conta AWS da Lacrei. O acesso à instância é feito pelo **EC2 Instance Connect**, autenticado pelo IAM e auditado no CloudTrail. A porta 22 não fica aberta para a internet; o pipeline abre uma regra temporária só para o IP do runner durante o deploy (veja [DEPLOY_AWS.md](DEPLOY_AWS.md#segurança-de-rede)).
- **Como consultar:** `docker logs production-web-1 --since 1h`, ou `staging-web-1`.
- **GitHub Actions:** o pipeline não copia os logs de acesso. Se um deploy falhar, mostra apenas as últimas linhas de **erro** do container, sem as linhas de acesso, para diagnóstico.

## 6. Retenção

| Onde | Regra | Na prática |
|---|---|---|
| Docker na EC2 (atual) | Rotação por tamanho: 10 MB × 5 arquivos por container (`deploy/docker-compose.prod.yml`) | No máximo 50 MB por container. Os logs são apagados quando o container é recriado, o que acontece a cada deploy |
| CloudWatch Logs (recomendado ao centralizar) | Política de retenção do grupo de logs | **30 dias**, configurada no próprio grupo (`aws logs put-retention-policy --retention-in-days 30`) |

Ao fim do prazo, os registros são descartados automaticamente; não há cópia de backup dos logs. Os logs de erro seguem a mesma regra.

## 7. Revisão

Esta política deve ser revisada sempre que um novo campo for adicionado aos logs ou quando os logs passarem a ser enviados para outro destino, como CloudWatch, Sentry ou Loki.
