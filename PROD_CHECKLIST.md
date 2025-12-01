# 🚀 CHECKLIST DE PRODUÇÃO (Go + Python/Django)

Este documento lista as alterações **MANDATÓRIAS** para garantir a segurança, estabilidade e performance antes do deploy em ambiente de Produção (ou Staging).

## 1. Segurança e Estabilidade do Django (Serviço django-web)

| Item | Ação em Produção | Racional |
|------|------------------|----------|
| **A. DEBUG** | Setar `DEBUG=False` no `.env` | Evita exposição de detalhes internos e chaves secretas |
| **B. Servidor** | Remover o argumento `--reload` do comando uvicorn | O `--reload` é instável e monitora arquivos, o que é um risco de falha (502/503) em produção |
| **C. Workers** | Adicionar o argumento `--workers N` no comando uvicorn | Permite que o Uvicorn utilize todos os cores da CPU para concorrência e alto desempenho |
| **D. Entrypoint** | Implementar ENTRYPOINT para executar migrate e collectstatic antes do uvicorn | Garante que o banco de dados e os estáticos (no volume staticfiles_data) estejam prontos antes do servidor iniciar |

## 2. Arquivos Estáticos (Volume Compartilhado)

**STATUS ATUAL**: O volume `staticfiles_data` está configurado corretamente no Nginx e no Docker Compose.

| Item | Status | Detalhe |
|------|--------|---------|
| **docker-compose.yml** | ✅ OK | django-web e nginx usam o volume nomeado staticfiles_data |
| **Fluxo de Escrita** | ⚠️ PENDENTE | O comando collectstatic DEVE ser incorporado ao entrypoint.sh do django-web para rodar na inicialização de produção |

# Gerenciamento de Volumes: Desenvolvimento vs. Produção

No Docker, a escolha entre **Bind Mount** (montagem de diretório local, usando `.`) e **Volume Nomeado** é crucial para equilibrar velocidade em desenvolvimento e segurança/estabilidade em produção.

## 1. O Volume de Código: `.:/app` (REMOVER em Produção)

**Volume**
- `.:/app` (em django-web e worker)

**O que é**
Um Bind Mount do diretório raiz do Host (`.`) para o diretório de trabalho do Contêiner (`/app`).

**Por que Manter (Dev)**
É o que permite o desenvolvimento em tempo real. Qualquer alteração que você faça em um arquivo Python local (ex: no Django) é vista instantaneamente pelo `uvicorn --reload` no contêiner. Sem isso, você teria que reconstruir a imagem Docker a cada pequena mudança.

**Por que Remover (Prod)**
**SEGURANÇA E PERFORMANCE**. Em produção, o código deve ser copiado para a imagem Docker (`COPY . /app` no Dockerfile) e não montado a partir de um diretório externo. Montar o código do host em produção cria riscos de permissão e pode expor arquivos sensíveis do Host.

**Ação em Produção**: O volume `- .:/app` deve ser removido do `docker-compose.yml`, dependendo da sua estratégia de deploy.

## 2. O Arquivo de Configuração: `./nginx.conf:ro` (MANTER em Produção)

**Volume**
- `./nginx.conf:/etc/nginx/conf.d/default.conf:ro` (em nginx)

**O que é**
Um Bind Mount de um único arquivo de configuração do Host (`./nginx.conf`) para o contêiner.

**Por que Manter (Dev & Prod)**
É o método mais simples, transparente e seguro para injetar configurações estáticas. O arquivo `nginx.conf` é a "planta" da sua infraestrutura de proxy, e raramente muda.

**A Vantagem do `:ro`**
O sufixo `:ro` (read-only) é fundamental. Ele garante que o contêiner Nginx só possa ler o arquivo de configuração, impedindo qualquer tentativa acidental ou maliciosa de escrita no seu disco local, mitigando o risco de segurança.

**Alternativa em Prod**
Embora seja aceitável manter o Bind Mount de um arquivo estático e read-only como este, a única alternativa seria copiar o `nginx.conf` para a imagem Nginx no Dockerfile (o que torna a imagem menos flexível para pequenas mudanças de infraestrutura).

**Conclusão**: Manter o Bind Mount para o arquivo de configuração estático e somente leitura (`./nginx.conf:ro`) é uma prática comum e segura que oferece flexibilidade e transparência, tanto em desenvolvimento quanto em produção.