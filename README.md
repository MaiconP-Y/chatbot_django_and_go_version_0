# WhatsApp Session Manager

**Protótipo Ativo - Mantido e Atualizado Regularmente**

## Escopo do Protótipo

Este é um protótipo funcional de um sistema de gerenciamento de sessões e filas para WhatsApp API (com WAHA, mas customizável), focado em estabilidade, resiliência e **escalabilidade via arquitetura híbrida (Go + Python)**.

## ⚡ NOVA ARQUITETURA E FUNCIONALIDADES PRINCIPAIS (Out/2025)

A arquitetura foi atualizada para um sistema de mensageria assíncrona, garantindo o desacoplamento de serviços e o processamento instantâneo das mensagens.

| Funcionalidade | Detalhes |
|----------------|-----------|
| **Gateway de Ingestão (Go)** | **Novo serviço em Golang** dedicado a receber o tráfego I/O Bound do Webhook, aplicando validação HMAC (segurança) e garantindo uma resposta ultrarrápida ao WAHA. |
| **Comunicação Estável** | Uso do Redis Pub/Sub para desacoplar a ingestão (Go) do processamento (Python), garantindo o acionamento instantâneo e resiliente do Worker. |
| **Gestão de Estado** | Persistência do estado da conversa por usuário (onde o usuário parou). |
| **Atendimento Organizado** | Controle de Estado, Histórico e Gerenciamento de Fila que ordena as conversas e envia notificações de posição na fila para o usuário. |
| **Histórico de Conversas** | Armazenamento completo do histórico de mensagens. |

## Arquitetura Atual (Híbrida: Go + Python)

O sistema opera com um fluxo de comunicação assíncrono, dividido em microserviços que exploram o melhor de cada linguagem: a concorrência do Go e a produtividade do ecossistema Python/Django.

**Fluxo de Mensagens:** `WhatsApp Webhook → Go Webhook Gateway → Redis (Pub/Sub) → Worker (Processamento) → WAHA API`

**Nota Técnica sobre o Go Gateway:**
A ingestão dos Webhooks foi movida para um Gateway dedicado em **Golang**. Esta mudança garante que o sistema de recebimento de mensagens seja **I/O Bound**, altamente concorrente e resiliente, respondendo ao WAHA em milissegundos e liberando o Worker Python para focar exclusivamente na lógica de negócios e IA.

**Nota sobre Escalabilidade:**
Atualmente, o Worker é configurado para atender 1 usuário por vez, mas a arquitetura já está pronta e provada para escalar com múltiplos Workers (processos) consumindo o Redis Pub/Sub simultaneamente.

## Stack Tecnológica

- **Backend (Processamento/Lógica):** Django 4.2+ (Python)
- **Backend (Ingestão/Gateway):** **Go (Golang)**
- **Banco de Sessão:** Redis
- **Mensageria:** Redis Pub/Sub e Sistema de Filas integrado
- **API WhatsApp:** WAHA (WhatsApp HTTP API)
- **Containerização:** Docker & Docker Compose