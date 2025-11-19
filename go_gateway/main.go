package main

import (
	"context" 
	"io" 
	"log"
	"net/http" 
	"os"
	"go_waha_gateway/services/hmac"
	"go_waha_gateway/services/redis"
)

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

    // PASSO 2: Validação HMAC (SEGURANÇA EXTREMA)
    hmacHeader := r.Header.Get("X-Webhook-Hmac")
    
    if hmacHeader == "" || !hmac.ValidateHmac(rawBody, hmacHeader) {
        log.Println("❌ Requisição recusada: HMAC ausente ou inválido.")
        http.Error(w, "Forbidden: Invalid HMAC signature", http.StatusForbidden)
        return
    }
    
    // PASSO 3: PUBLICAR no Redis - AGORA SIMPLES E RÁPIDO
    // Apenas enfileira o payload BRUTO. O Duplicata Check e a Decodificação ficam no Worker.
    if err := redis.PublishMessage(r.Context(), rawBody); err != nil {
        log.Printf("❌ Erro ao publicar mensagem no Redis: %v", err)
        http.Error(w, "Erro de enfileiramento", http.StatusServiceUnavailable) 
        return
    }
    
    // PASSO 4: SUCESSO
    w.WriteHeader(http.StatusOK)
    log.Println("✨ Webhook processado com sucesso e mensagem enfileirada!")
}