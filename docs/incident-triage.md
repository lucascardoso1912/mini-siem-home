# Análise simulada 001: falhas de login seguidas de sucesso

> Exercício inteiramente sintético. Nenhum host, usuário, pacote de rede ou conta real foi monitorado. Os endereços abaixo pertencem a faixas reservadas para documentação.

## Resumo executivo

O cenário `compromised`, seed `2026`, gerou 16 eventos de autenticação. Cinco falhas para `admin`, vindas de `203.0.113.66`, ocorreram entre `12:30` e `12:34 UTC`. Um login bem-sucedido do mesmo IP e usuário foi registrado em `12:35 UTC`.

O sistema criou dois alertas para a mesma sequência: `multiple_failed_logins` com severidade `medium` e `successful_login_after_failures` com severidade `high`. O segundo foi colocado em `investigating` pela API, com uma nota identificada como simulação. O primeiro permanece `open`. Isso é uma decisão didática do laboratório, não uma confirmação de comprometimento.

## Escopo e reprodução

- Cenário: `compromised`
- Seed: `2026`
- Eventos: 16 (10 de atividade-base sintética e 6 na sequência de teste)
- Host fictício: `auth-server-01`
- Execução armazenada: `ac958c2bb9d5494b921fd16a81719abc`
- Regra de correlação: pelo menos 5 falhas do mesmo IP/usuário em 10 minutos, seguidas de sucesso em até 5 minutos

Para reproduzir as detecções sem escrever no banco principal:

```bash
./.venv/bin/python -m soc_lab.simulator \
	--scenario compromised --seed 2026 \
	--output /tmp/soc-lab-compromised-2026.jsonl
./.venv/bin/python -m soc_lab.cli \
	--input /tmp/soc-lab-compromised-2026.jsonl \
	--db /tmp/soc-lab-analysis.sqlite
```

## Evidências observadas

| Horário UTC | Evento sintético | Interpretação da regra |
| --- | --- | --- |
| 12:30 | Falha para `admin` de `203.0.113.66` | Primeira falha da sequência |
| 12:31–12:33 | Mais três falhas do mesmo IP/usuário | A contagem se aproxima do limiar |
| 12:34 | Quinta falha do mesmo IP/usuário | A regra de falhas repetidas atinge 5 em 10 min |
| 12:35 | Sucesso para `admin` do mesmo IP | A regra de correlação eleva a severidade |

Há dez eventos sintéticos de contexto antes da sequência. Eles não satisfazem as regras do cenário `compromised` e não foram usados para inferir uma origem real.

## O que cada campo significa

| Campo | Valor neste caso | Significado e limite |
| --- | --- | --- |
| `timestamp` | 12:30–12:35 UTC | Momento fictício do evento. UTC permite ordenar fontes com fusos diferentes. |
| `event_type` | `authentication` | Classifica o registro como autenticação; não é captura de pacote. |
| `source_ip` | `203.0.113.66` | IP de origem sintético, reservado para documentação; não identifica uma pessoa. |
| `username` | `admin` | Conta-alvo fictícia. O nome da conta, sozinho, não prova quem tentou autenticar. |
| `outcome` | `failure` ou `success` | Resultado registrado pelo simulador, não confirmado por um provedor real. |
| `hostname` | `auth-server-01` | Host fictício que teria observado a autenticação. |
| `event_id` | `evt-0011` a `evt-0016` | Identificador sequencial útil para referenciar cada evento do conjunto. |
| `scenario` | `compromised` | Rótulo do cenário gerado, não uma classificação de incidente real. |

## Como cada regra avaliou os dados

1. `multiple_failed_logins` agrupou as falhas pelo IP e contou cinco eventos em uma janela móvel de dez minutos. Isso gerou severidade `medium`; essa regra não precisa saber o usuário.
2. `successful_login_after_failures` agrupou por IP **e** usuário, encontrou cinco falhas em dez minutos e um sucesso um minuto após a última falha. Como um minuto está dentro da janela de correlação de cinco minutos, gerou severidade `high`.
3. A regra não lê senhas, não decodifica tráfego e não decide que uma conta foi comprometida. Ela compara timestamps, IP, usuário e resultado já presentes nos eventos.

## Por que existem dois alertas?

As regras respondem a perguntas diferentes. `multiple_failed_logins` pergunta se houve muitas falhas do mesmo IP e gera um alerta `medium`. `successful_login_after_failures` pergunta se o mesmo IP e usuário conseguiram entrar logo após essas falhas; por isso gera `high`.

Os dois alertas referenciam os mesmos cinco eventos de falha. Eles não significam que ocorreram dois ataques diferentes. Em um SIEM mais completo, poderíamos agrupar alertas relacionados em um único caso para reduzir duplicidade.

## Avaliação do analista

**Observação:** o conjunto de eventos corresponde exatamente às condições das duas regras. A ordem temporal é consistente: falhas, depois sucesso, para o mesmo IP e usuário.

**Hipótese:** se esses fossem logs reais, a sequência justificaria investigar possível uso de credenciais após tentativas repetidas.

**O que não se pode concluir:** os dados são fabricados pelo simulador; não provam que uma senha foi descoberta, que uma conta real foi acessada ou que houve atividade maliciosa. Também não identificam uma pessoa por trás do endereço IP.

**Possíveis explicações benignas em um ambiente real:** usuário errando a senha antes de acertar, automação de teste autorizada, sistema intermediário compartilhado ou atividade de suporte. As regras não conhecem o contexto organizacional e podem gerar falsos positivos.

## Decisão e próximos passos

O alerta `high` está marcado como `investigating`; a nota armazenada também identifica explicitamente a simulação. Num ambiente autorizado, o analista deveria:

1. Confirmar o endereço, host, método de autenticação e identidade nos logs originais do sistema ou provedor de identidade.
2. Verificar se o login bem-sucedido e o dispositivo/sessão eram esperados.
3. Examinar a atividade posterior à autenticação e verificar MFA, origem e histórico da conta.
4. Se as evidências reais confirmarem risco, seguir o procedimento da organização para revogar sessões e proteger a conta. Não bloquear automaticamente com base apenas neste alerta.

## Estado do laboratório

- `multiple_failed_logins`: `open`
- `successful_login_after_failures`: `investigating`
- Resposta automática: nenhuma
- Impacto em sistemas reais: nenhum