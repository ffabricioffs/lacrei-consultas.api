# Decisões técnicas, problemas encontrados e melhorias

## Decisões

### Arquitetura da aplicação

| Decisão | Justificativa |
|---|---|
| **Apps por domínio** (`profissionais`, `consultas`, `pagamentos`) + `core` transversal | Fronteiras claras, cada app com modelo, serializers, views e testes. O `core` concentra o que é transversal (sanitização, logs, erros) |
| **`ModelViewSet` + `DefaultRouter`** | CRUD REST completo e padronizado com pouco código, paginação e busca prontas |
| **Endereço/contato aninhados na API, colunas planas no banco** (`source="*"`) | Payload semântico para quem consome a API, sem JOINs nem tabelas extras para dados 1:1 |
| **Regras de negócio no serializer** (data futura, horário único) **e no banco** (`UniqueConstraint` condicional, `UniqueConstraint(Lower("email"))`) | O serializer dá mensagens amigáveis; o banco garante consistência mesmo sob concorrência |
| **`on_delete=PROTECT`** em consultas e cobranças | Dado de saúde e financeiro não pode sumir em cascata. Remover um profissional com histórico retorna 409, e não um 500 genérico |
| **Serviço de domínio** em `pagamentos/services.py` | Regras de cobrança testáveis sem HTTP; a view só orquestra |
| **Gateway Asaas com interface (`Protocol`) + mock** | Desenvolvimento e testes sem depender de rede; trocar mock por real é configuração |
| **Validação explícita de query params** (`profissional_id`) | Erro 400 claro em vez de resultado vazio ou 500, e defesa em profundidade contra injeção |

### Segurança

| Decisão | Justificativa |
|---|---|
| **JWT (simplejwt)** | Expira sozinho, identifica a pessoa usuária nos logs (auditoria) e é o padrão para SPAs e apps. API Key fixa seria mais simples, mas não expira nem identifica quem fez cada ação |
| **`IsAuthenticated` global** | Seguro por padrão: endpoints públicos são exceções explícitas |
| **Sanitização na borda (serializer)** | Dados chegam limpos ao banco. Remover HTML protege contra XSS armazenado caso algum painel renderize o conteúdo sem escapar |
| **Somente `JSONParser`/`JSONRenderer`** | Superfície menor (sem form/multipart) e garante que toda resposta é JSON |
| **CORS com lista explícita** | `CORS_ALLOW_ALL_ORIGINS` permitiria qualquer site chamar a API a partir do navegador de uma pessoa usuária |
| **Rate limiting** | Mitiga força bruta no `/auth/token/` e abuso em geral |
| **Ruff com regras Bandit (`S`)** | Análise estática de segurança a cada push, sem ferramenta extra |

### Infraestrutura

| Decisão | Justificativa |
|---|---|
| **Poetry 2 + `package-mode = false`** | Dependências declaradas no padrão PEP 621 e lockfile reprodutível; o projeto é uma aplicação, não uma biblioteca |
| **Dockerfile multi-stage, usuário sem root, HEALTHCHECK** | Imagem menor, sem Poetry na final, menor superfície de ataque; o healthcheck alimenta o rollback |
| **Settings únicos via variáveis de ambiente** | 12-factor: a mesma imagem roda em qualquer ambiente; não há `settings_prod.py` divergente |
| **EC2 + Docker Compose** em vez de ECS/Beanstalk | Atende "staging e produção na AWS" com custo baixo (free tier) e o mesmo `docker compose` do desenvolvimento. É fácil explicar e depurar |
| **Caddy** como proxy reverso | HTTPS automático (Let's Encrypt) sem certbot nem cron, e configuração de poucas linhas |
| **GHCR** como registry | Autenticação com o `GITHUB_TOKEN` do próprio job, sem credenciais AWS no pipeline |
| **Mesma imagem promovida** staging → produção, com aprovação manual | O que foi testado em staging é exatamente o que vai para produção |
| **Gunicorn** | Servidor WSGI maduro; o `runserver` não é próprio para produção |
| **WhiteNoise** | Serve os estáticos do admin e do Swagger sem configurar volume no proxy |

## Problemas encontrados e como foram resolvidos

| Problema | Solução |
|---|---|
| `UniqueValidator` dentro do serializer aninhado de contato não tem acesso à instância, então acusava "e-mail duplicado" ao editar o próprio profissional | Verificação de unicidade feita no `validate()` do serializer pai, excluindo a própria instância, com constraint `Lower(email)` no banco como garantia final |
| Validadores automáticos do DRF para `UniqueConstraint` com `condition` (horário único só para consultas não canceladas) se comportam de forma diferente entre versões do DRF | `Meta.validators = []` na `ConsultaSerializer` e regra explícita no `validate()`, considerando o status |
| Texto como `"<b></b>"` passava pela validação de "não vazio" e virava string vazia após a sanitização | `SanitizedCharField` revalida se o valor ficou vazio depois de sanitizar |
| PostgreSQL rejeita o caractere nulo (`\x00`) em campos texto, o que gerava erro 500 | A sanitização remove caracteres de controle antes de chegar ao banco (há teste para isso) |
| `str.isdigit()` aceita dígitos Unicode (`"²"`), que quebram `int()` | Validação com `isascii() and isdigit()` |
| Exceções `ProtectedError`/`IntegrityError` viravam 500 | Handler central converte em 409 com mensagem clara |
| JWT é autenticado na view do DRF, não no middleware, e o log de acesso saía sem usuário | O log é emitido na volta da resposta, quando o DRF já populou `request.user` |
| Rollback do pipeline poderia reverter duas versões (o `deploy.sh` já tinha revertido sozinho) | Step de rollback condicionado a `steps.smoke.outcome == 'failure'` |
| Rate limiting derrubava testes com muitas requisições | Throttling desativado só durante `manage.py test` |
| Logs dos testes poluíam a saída do CI | Nível `CRITICAL` durante os testes; os testes de log usam `assertLogs`, que reativa o logger temporariamente |

## Melhorias propostas

**Produto e domínio**
- Entidade **Paciente** (com consentimento LGPD explícito e criptografia de campos sensíveis).
- Disponibilidade/agenda do profissional (janelas de atendimento, duração da consulta, conflito por intervalo e não só por horário exato).
- Soft delete com trilha de auditoria (`django-simple-history`) para consultas.

**Segurança**
- Permissões por papel (ex.: profissional só vê as próprias consultas) com `django-guardian` ou regras em `get_queryset`.
- Blacklist de refresh tokens no logout (`rest_framework_simplejwt.token_blacklist`).
- WAF da AWS na frente da instância e SSM no lugar de SSH aberto.
- Scan da imagem (Trivy) e `pip-audit` no pipeline.

**Operação**
- RDS com backups automáticos e point-in-time recovery.
- Métricas (Prometheus/CloudWatch) e alertas sobre taxa de 5xx e latência p95, usando os campos dos logs JSON.
- Sentry para rastrear exceções com o `request_id`.
- Blue/green real com dois containers e troca no Caddy (zero downtime).
- Preview deploys por pull request.
