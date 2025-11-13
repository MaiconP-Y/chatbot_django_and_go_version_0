# WhatsApp Session Manager

## Protótipo Ativo: Otimizado para Resiliência, Segurança e Alta Concorrência

Este é um protótipo funcional de um sistema de gerenciamento de sessões para WhatsApp API (via WAHA, customizável), focado em **estabilidade, concorrência e escalabilidade** via uma arquitetura híbrida de microserviços.

---

## ARQUITETURA DE ALTA PERFORMANCE (Go Way)

A arquitetura foi atualizada para um **pipeline de processamento assíncrono** com foco total no desacoplamento de serviços. O **Gateway em Go** garante que a latência de ingestão seja quase zero, enquanto o Worker Python foca no processamento complexo e IA.

### Ganhos de Engenharia e Funcionalidades Principais

| Pilar | Funcionalidade | Detalhes Técnicos e Ganhos de Performance |
| :--- | :--- | :--- |
| **Ingestão/Segurança** | **Go Webhook Gateway (Fast Path)** | Serviço em Golang para tráfego I/O Bound. Aplica **Validação HMAC Criptograficamente Segura** (`hmac.Equal` para prevenir **Timing Attacks**). Resposta garantida em **<100ms** (via Redis Timeout Crítico) para máxima concorrência. |
| **Resiliência de Rede** | **Reverse Proxy Robusto (NGINX)** | Implementa **Rate Limiting** (`burst`/`nodelay`) e **Headers de Segurança** (`X-Frame-Options`). Utiliza **Resolução Dinâmica de DNS** (`resolve` a cada 5s) para garantir roteamento contínuo em ambientes Docker voláteis. |
| **Comunicação** | **Mensageria Assíncrona** | Uso do **Redis List/LPUSH** para fila persistente. Desacopla a ingestão (Go) do processamento (Python), garantindo a **não-perda de mensagens** e o acionamento **BLPOP** do Worker (baixo consumo de CPU). |
| **Lógica de Negócios** | **Gestão de Sessão (Python)** | Gerenciamento de estado de conversa, controle de Fila de Atendimento e execução de **LLM Agents (Groq)** para lógica de negócios e integrações. |
| **Observabilidade** | **Monitoramento Ativo (Prometheus)** | Infraestrutura preparada com Prometheus e Grafana. O `prometheus.yml` já mapeia os *targets* `go-gateway:8080` e `whatsapp-worker:9091` para coleta de dados de saúde e performance. |

---

## FLUXO E STACK TECNOLÓGICA

### Fluxo de Mensagens:

`WhatsApp Webhook → NGINX (Rate Limit) → Go Webhook Gateway (HMAC/LPUSH) → Redis Queue → Worker Python (BLPOP/LLM) → WAHA API`

### Nota sobre Escalabilidade:

A arquitetura assíncrona com fila Redis permite o **escalamento horizontal imediato** dos *Workers Python*, aumentando o *throughput* de processamento conforme a demanda cresce.

### Stack Tecnológica

| Camada | Tecnologia | Função Principal |
| :--- | :--- | :--- |
| **Gateway/Ingestão** | **Go (Golang)** | Performance I/O, Validação HMAC, Resposta Rápida (Non-blocking) |
| **Proxy/Borda** | **NGINX** | Rate Limiting, Segurança, Roteamento Dinâmico |
| **Lógica/Negócios** | **Django 4.2+ (Python)** | Gerenciamento de Estado, Integrações, LLM Agents |
| **Mensageria/Fila** | **Redis** | Fila de Trabalho (LPUSH/BLPOP) e Gestão de Estado de Sessão |
| **APIs** | **WAHA API, Groq** | Comunicação com WhatsApp, Motor de Inferência LLM |

### PRÓXIMOS PASSOS (OBSERVABILIDADE)

**Aviso:** O sistema está configurado para o **Pull de Métricas** via Prometheus. Em breve, a instrumentação no código (Go-Gateway e Worker Python) será completada para que os dados de **Latência Crítica, Throughput e Erros** comecem a ser coletados e visualizados no Grafana.