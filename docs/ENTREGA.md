# Evidências da entrega

Este arquivo reúne o que a devolutiva pediu para conferir: o commit avaliado, a execução do pipeline, as versões no ar e a segregação entre staging e produção.

## Commit avaliado

O **commit avaliado é o commit que adicionou este arquivo**, o último de `main` na data de envio. Como um arquivo não consegue citar o próprio hash, o SHA completo e o link direto da execução seguem no e-mail de resposta. Também dá para conferir sem o e-mail:

1. Abra [Actions → CI/CD na branch main](https://github.com/ffabricioffs/lacrei-consultas.api/actions/workflows/ci-cd.yml?query=branch%3Amain).
2. A execução mais recente é a do commit avaliado, com os 5 jobs em verde.
3. A imagem publicada e a versão do `/health/` usam a tag `sha-<7 primeiros caracteres do commit>`.

## O que a execução mostra

Cada job escreve um resumo na página da execução e publica artefatos para download.

| Job | O que comprova | Onde ver |
|---|---|---|
| Lint | `ruff check` e `ruff format --check` sem apontamentos | Resumo "Lint" |
| Testes e cobertura | 106 testes `APITestCase` contra PostgreSQL 16, cobertura de 96% | Resumo com a tabela de cobertura; artefato `testes-e-cobertura` |
| Build da imagem Docker | Imagem multi-stage, usuário não root, publicada no GHCR com a tag do commit | Resumo "Build"; registro do build |
| Staging / Deploy staging | Deploy, migrações, healthcheck interno e smoke tests externos | Resumo com a tabela de smoke tests; artefato `evidencias-staging-deploy` |
| Produção / Deploy production | Só começa depois do staging com sucesso **e** da aprovação manual; repete os smoke tests e gera o relatório de segregação | Resumo com smoke tests e relatório; artefato `evidencias-production-deploy` |

### Smoke tests (staging e produção)

Executados de fora da AWS, pelo runner do GitHub, contra a URL pública de cada ambiente ([`scripts/smoke-test.sh`](../scripts/smoke-test.sh)):

| Verificação | Esperado |
|---|---|
| `GET /health/` | `status: ok`, `database: ok` e a versão do commit em deploy |
| Certificado TLS | Válido (Let's Encrypt) |
| `http://` | Redireciona para `https://` |
| `GET /api/v1/profissionais/` sem token | `401` |
| Login com credenciais inválidas | `401` |
| `GET /api/schema/` | `200` |
| Cabeçalhos de segurança | `X-Content-Type-Options: nosniff` e `X-Frame-Options: DENY` |

Se algum smoke test falhar, o pipeline executa o rollback para a imagem anterior e o job termina em erro. No caso do staging, a produção não é executada.

## Ambientes

| Ambiente | URL | Verificação de saúde |
|---|---|---|
| Produção | https://15-229-49-123.sslip.io | https://15-229-49-123.sslip.io/health/ |
| Staging | https://staging.15-229-49-123.sslip.io | https://staging.15-229-49-123.sslip.io/health/ |

Os dois respondem em HTTPS na porta 443. O `/health/` mostra a versão em execução, por exemplo:

```json
{"status": "ok", "database": "ok", "version": "sha-xxxxxxx", "environment": "production"}
```

Documentação interativa: `/api/docs/` (Swagger) e `/api/redoc/` em cada ambiente.

> Ferramentas que bloqueiam domínios curinga de DNS (como `sslip.io`) podem não acessar as URLs. Nesse caso, a evidência fica nos smoke tests do pipeline, executados de fora da AWS, e no artefato `smoke-health.json`, que guarda a resposta do `/health/`.

## Segregação na mesma EC2

Staging e produção rodam **na mesma instância EC2** (`t3.micro`, sa-east-1), cada um como um projeto Docker Compose separado. A tabela completa está no [README](../README.md#ambientes-staging-e-produção-na-mesma-ec2). Resumo:

| Item | Staging | Produção |
|---|---|---|
| Diretório | `/opt/lacrei/staging` | `/opt/lacrei/production` |
| Banco de dados | Container e volume `staging_pgdata` próprios | Container e volume `production_pgdata` próprios |
| Rede do banco | `staging_backend` (interna, sem saída) | `production_backend` (interna, sem saída) |
| Segredos e configuração | `.env` próprio, modo `600` | `.env` próprio, modo `600` |
| Acesso público | `staging.15-229-49-123.sslip.io` | `15-229-49-123.sslip.io` |

O único componente compartilhado é o proxy Caddy (`/opt/lacrei/edge`), que recebe as portas 80 e 443 e encaminha por nome de host. Ele não acessa nenhum banco.

O job de produção executa [`scripts/segregation-report.sh`](../scripts/segregation-report.sh) e publica no resumo:

- containers, redes e volumes de cada ambiente;
- dono e permissão de cada `.env`;
- comparação de cada segredo entre os ambientes, mostrando só "diferente" ou "igual", nunca o valor;
- teste de rede: o `web` de cada ambiente alcança o próprio banco e **não** alcança o banco do outro.

## Segurança de rede (security group)

Regras de entrada após o ajuste:

| Porta | Origem | Motivo |
|---|---|---|
| 80/tcp | `0.0.0.0/0` | Redirecionar para HTTPS e renovar certificados |
| 443/tcp | `0.0.0.0/0` | API de produção e staging |
| 22/tcp | Lista de prefixos `com.amazonaws.sa-east-1.ec2-instance-connect` | Acesso administrativo pelo console da AWS |
| 22/tcp | IP do runner `/32`, **só durante o deploy** | Aberta e revogada pelo pipeline via OIDC |

A porta 22 deixou de aceitar `0.0.0.0/0`, e a porta 8080, usada antes pelo staging, foi removida. Detalhes em [DEPLOY_AWS.md](DEPLOY_AWS.md#segurança-de-rede).

## Logs com IP e user agent

Finalidade, campos, anonimização do IP, acesso e retenção estão em [LOGS.md](LOGS.md).
