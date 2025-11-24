# WhatsApp Session Manager: Arquitetura Híbrida de Microserviços

**Protótipo de Produção Ativa:** Otimizado para **Resiliência**, **Segurança** (HMAC/ID Check), **Observabilidade** e **Alta Concorrência**.

Este sistema gerencia sessões e interações de WhatsApp (via WAHA) através de uma arquitetura híbrida de microserviços (Go + Python/Django). O foco principal é a **Garantia de Entrega** e a execução confiável de **LLM Agents (Tool Calling)** para tarefas de negócio.

---

## Arquitetura e Ganhos de Engenharia

O projeto utiliza um **pipeline de processamento assíncrono (Go Way)** para desacoplar a ingestão da lógica de negócios, garantindo latência quase zero na borda.

| Pilar | Funcionalidade | Detalhes Técnicos e Ganhos de Performance |
| :--- | :--- | :--- |
| **Ingestão/Borda** | **Go Webhook Gateway** | Serviço em **Golang** (I/O Bound). Aplica **Validação HMAC Criptograficamente Segura** para máxima concorrência. |
| **Segurança/Integridade** | **Blindagem de Mensagem** | Worker Python utiliza **Redis SETNX** (TTL 60s) para **prevenir o processamento duplicado** de webhooks (`message_id` check). |
| **Resiliência de Rede** | **Reverse Proxy Robusto (NGINX)** | Implementa **Rate Limiting** (burst/nodelay) e utiliza **Resolução Dinâmica de DNS** (`resolve` a cada 5s). |
| **Comunicação/Fila** | **Mensageria Persistente** | Uso do **Redis List/LPUSH** para fila persistente, garantindo a **não-perda de mensagens** (Garantia de Entrega). |
| **Lógica/IA** | **LLM Agents (Tool Calling)** | Implementação de Agentes LLM (Groq/Llama3) usando o padrão **Tool Calling**. Agentes especializados são roteados por intenção. |
| **Lógica/Segurança** | **Gestão de Sessão (LGPD)** | Gerencia o estado de sessão para **forçar o fluxo de consentimento LGPD** e controlar o diálogo de agendamento. |
| **Qualidade** | **Observabilidade (Ready)** | Infraestrutura pronta com **Prometheus** e **Grafana** para coletar métricas do Go Gateway e Worker Python. |

---

## Fluxo e Stack Tecnológica

### Fluxo de Mensagens (Assíncrono)
A arquitetura assíncrona permite o **escalamento horizontal imediato** dos Workers Python, otimizando o *throughput* de processamento.

**WhatsApp Webhook** → **NGINX** (Rate Limit) → **Go Webhook Gateway** (HMAC/LPUSH) → **Redis Queue** → **Worker Python** (BLPOP/LLM Agents) → **WAHA API**

### Stack Tecnológica

| Camada | Tecnologia | Função Principal |
| :--- | :--- | :--- |
| **Gateway/Ingestão** | **Go (Golang)** | Performance I/O, Validação HMAC. |
| **Proxy/Borda** | **NGINX** | Rate Limiting, Segurança, Roteamento. |
| **Lógica/Negócios** | **Django 4.2+ (Python)** | Gerenciamento de Estado, LLM Agents. |
| **Mensageria/Fila** | **Redis** | Fila de Trabalho (LPUSH/BLPOP) e Gestão de Estado. |
| **APIs/IA** | **WAHA API, Groq** | Comunicação com WhatsApp, Motor de Inferência LLM. |

---

## Roadmap de Agentes e Próximos Passos

O projeto está focado em consolidar a funcionalidade completa da IA antes de instrumentar a observabilidade.

### 1. Agentes LLM (Foco Atual)

| Agente | Status | Descrição |
| :--- | :--- | :--- |
| **Agente de Registro** | ✅ Funcional | Gerencia o fluxo de consentimento LGPD e registra o nome do usuário. |
| **Agente Roteador** | ✅ Funcional | Detecta a intenção do usuário e direciona para o agente especializado. |
| **Agente de Agendamento/Verificação** | ✅ Funcional | Gerencia a verificação de horários disponíveis e a marcação de novas consultas no Google Calendar (requer Tool Calling). |
| **Agente de Consulta/Cancelamento** | ✅ Funcional | Consultará consultas existentes e executará o cancelamento. |

### 2. Observabilidade (Próxima Fase)

* **Instrumentação Fina:** Adicionar métricas (tempo de execução do LLM, latência do Worker) no Go Gateway e Worker Python usando *Prometheus Clients*.
* **Visualização:** Criação de dashboards no Grafana para monitorar o SLA e diagnosticar gargalos de performance.