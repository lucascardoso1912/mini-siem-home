# SOC Home Lab

**English:** [Read the English overview](README.en.md)

Um mini SOC local e reproduzível para praticar geração e normalização de eventos, regras de detecção, persistência, monitoramento e triagem. A interface e as regras trabalham com dados locais; o simulador não gera tráfego de rede.

## Arquitetura

`simulador -> JSONL -> CLI/regras -> SQLite <-> FastAPI <-> frontend estático`

O frontend em `frontend/` consome somente a API HTTP; o backend FastAPI acessa `data/soc_lab.sqlite`. O FastAPI também serve os arquivos estáticos na mesma origem. Não é preciso Node para desenvolver ou executar esta interface. Eventos e alertas gerados são dados de runtime ignorados pelo Git; os eventos de exemplo versionados são sintéticos.

## Capturas do dashboard

![Resumo do dashboard SOC com métricas do laboratório](docs/screenshots/soc-dashboard.png)

![Fila de alertas sintéticos com severidades e estados de triagem](docs/screenshots/alert-queue.png)

## Regras

| Regra | Condição padrão | Severidade |
| --- | --- | --- |
| `multiple_failed_logins` | 5 falhas do mesmo IP em 10 min | medium |
| `successful_login_after_failures` | 5 falhas do mesmo IP/usuário e sucesso em até 5 min | high |
| `password_spraying` | Falhas contra 5 usuários distintos do mesmo IP em 10 min | high |
| `firewall_port_sweep` | 10 portas distintas negadas em 10 min | medium |
| `encoded_powershell_command` | Criação de processo PowerShell com argumento de comando codificado | high |

## Instalar e executar

Requer Python 3.10 ou superior. FastAPI e Uvicorn são dependências externas; a instalação inicial precisa de acesso ao índice de pacotes Python.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Gere os dados e analise-os para gravar a execução no SQLite:

```bash
.venv/bin/python -m soc_lab.simulator --scenario full-suite --seed 42
.venv/bin/python -m soc_lab.cli --input data/generated_events.jsonl
```

Inicie a API e a interface:

```bash
.venv/bin/python -m uvicorn soc_lab.api:app --host 127.0.0.1 --port 8000 --limit-concurrency 50 --backlog 128 --timeout-keep-alive 5
```

Acesse `http://127.0.0.1:8000` para abrir a interface e `http://127.0.0.1:8000/docs` para explorar a API. O painel mostra métricas, filtra alertas, exibe evidências e permite mudar o status e salvar notas de triagem. Use `--output` no simulador e `--db` na CLI para alterar os destinos. A mesma semente do simulador reproduz os mesmos eventos.

Endpoints principais: `GET /api/health`, `GET /api/overview`, `GET /api/runs`, `GET /api/alerts`, `GET /api/events` e `PATCH /api/alerts/{alert_id}/triage`.

## Segurança da API

A configuração padrão é para laboratório local: inicie em `127.0.0.1`, aceite hosts `127.0.0.1` e `localhost`, limite leituras a 120/minuto por IP, gravações a 20/minuto por IP e o total a 600/minuto por processo. Corpos HTTP têm limite de 64 KiB; parâmetros de paginação e IDs têm tamanho/formato limitado; headers de proteção e CSP same-origin para o frontend são adicionados às respostas. As consultas SQLite usam parâmetros, e o modelo de triagem rejeita campos inesperados.

O comando Uvicorn limita a 50 conexões simultâneas e reduz o keep-alive para 5 segundos. Esses controles complementam o rate limit da aplicação; não são proteção contra DDoS distribuído.

Os limites em memória são deliberadamente para um processo local: reiniciar a API zera as janelas, e múltiplos workers não compartilham contadores. Não exponha o servidor à rede pública. Para produção, adicione autenticação, TLS e reverse proxy com rate limiting compartilhado (por exemplo, Redis) e limites de conexão/concorrência.

Os valores podem ser ajustados com `SOC_API_RATE_PER_MINUTE`, `SOC_API_WRITE_RATE_PER_MINUTE`, `SOC_API_GLOBAL_RATE_PER_MINUTE`, `SOC_API_MAX_BODY_BYTES` e `SOC_ALLOWED_HOSTS` (lista separada por vírgulas). O serviço não confia em `X-Forwarded-For`; atrás de proxy, configure corretamente o proxy confiável antes de usar a identidade do cliente.

Para analisar outro JSONL, cada linha precisa ser um objeto com `timestamp` contendo fuso horário. Os campos adicionais dependem do tipo: autenticação usa `source_ip`, `username` e `outcome`; firewall usa `source_ip`, `destination_port` e `outcome`; criação de processo usa `process_name` e `command_line`.

## Cenários

`normal`, `brute-force`, `compromised`, `password-spray`, `port-scan`, `encoded-powershell` e `full-suite`. Os IPs usam blocos reservados para documentação. O simulador não executa PowerShell, não testa senhas e não se conecta a hosts.

## Triagem de exemplo

Veja [docs/incident-triage.md](docs/incident-triage.md). O caso está marcado como simulado e demonstra evidência, decisão e próximos passos de investigação sem afirmar que veio de um ambiente real.

Para exportar a análise detalhada em PDF, instale a dependência documental separada e execute:

```bash
.venv/bin/python -m pip install -r requirements-report.txt
.venv/bin/python scripts/export_incident_report.py
```

O arquivo é criado em `docs/reports/incident-triage-001.pdf`.

## Limites e próxima etapa

Este projeto não é um SIEM completo: ainda não coleta Windows Event Logs, syslog ou firewall de hosts reais e não substitui ferramentas como Splunk ou Elastic. Para integrar uma VM, normalize os logs para o esquema JSONL e use somente máquinas e redes que você controla. Consulte as notas de evolução em [docs/roadmap.md](docs/roadmap.md).

Não publique logs reais, credenciais, tokens, dumps do banco ou dados pessoais. Faça a triagem manual; o lab não bloqueia contas nem executa respostas automáticas.
