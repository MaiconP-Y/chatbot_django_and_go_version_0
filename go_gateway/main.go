// ./main.go
package main

import (
	"context" 
	"io" 
	"log"
	"net/http" 
	"os"

	// Importamos os novos pacotes, usando o nome do módulo 'go_waha_gateway'
	"go_waha_gateway/services/hmac"
	"go_waha_gateway/services/redis"
)

// Variável global para o contexto base da aplicação
var ctx = context.Background() 

func main() {
	// 1. Inicializa o Serviço HMAC
	if err := hmac.InitSecret(); err != nil {
		log.Fatalf("❌ Falha crítica ao carregar a chave HMAC: %v", err)
	}

	// 2. Inicializa o Serviço Redis (com teste de conexão e timeout)
	if err := redis.InitClient(ctx); err != nil {
		log.Fatalf("❌ Falha crítica ao inicializar o Redis: %v", err)
	}
	log.Println("✅ Conexão Redis estabelecida com sucesso!")

	// 3. Configuração do Servidor HTTP
	http.HandleFunc("/webhook", webhookHandler) 

	port := os.Getenv("PORT") 
	if port == "" {
		port = "8080"
	}
	log.Printf("🚀 Gateway Go INICIADO na porta :%s", port)

	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("❌ Erro fatal ao iniciar o servidor: %v", err)
	}
}

// Handler Principal do Webhook
func webhookHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Método não permitido", http.StatusMethodNotAllowed)
		return
	}
	
	// PASSO 1: LER o corpo da requisição BRUTO (RAW BODY)
	rawBody, err := io.ReadAll(r.Body)
	if err != nil {
		log.Printf("❌ Erro ao ler body da requisição: %v", err)
		http.Error(w, "Erro ao ler body", http.StatusInternalServerError)
		return
	}
	defer r.Body.Close() 

	// PASSO 2: Validação HMAC (Segurança - USANDO PACOTE EXTERNO)
	hmacHeader := r.Header.Get("X-Webhook-Hmac")
	
	if hmacHeader == "" || !hmac.ValidateHmac(rawBody, hmacHeader) {
		log.Println("❌ Requisição recusada: HMAC ausente ou inválido.")
		http.Error(w, "Forbidden: Invalid HMAC signature", http.StatusForbidden)
		return
	}
	
	// PASSO 3: PUBLICAR no Redis (AGORA COM LPUSH E TIMEOUT)
	// r.Context() é o Contexto da Requisição HTTP
	if err := redis.PublishMessage(r.Context(), rawBody); err != nil {
		// Se der erro, o motivo mais provável é o Timeout de 100ms no Redis
		log.Printf("❌ Erro de publicação no Redis (Timeout provável): %v", err)
        
        // Retorna 503 para que o WAHA tente novamente mais tarde
		http.Error(w, "Service Temporarily Unavailable (Redis Timeout)", http.StatusServiceUnavailable)
		return
	}
	
	log.Println("✅ Mensagem LPush/publicada no Redis com sucesso!")
	w.WriteHeader(http.StatusOK) 
	w.Write([]byte(`{"status":"ok"}`))
}