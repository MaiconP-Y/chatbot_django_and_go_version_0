package main

import (
	"context" // Essencial para concorrência e operações distribuídas
	"crypto/hmac" // Para a validação HMAC
	"crypto/sha512" // Algoritmo SHA512
	"encoding/hex" // Para converter o hash de bytes para string hexadecimal
	"fmt"
	"io" // Para ler o corpo da requisição
	"log"
	"net/http" // Pacote nativo para servidores web de alta performance
	"os"

	"github.com/go-redis/redis/v8" // Importa o cliente Redis
)

// Constantes e Variáveis Globais
const redisChannel = "new_user_queue" // <--- Canal de comunicação com o Worker Python
var redisClient *redis.Client
var ctx = context.Background()

func main() {
	// 1. Configuração do Cliente Redis
	redisHost := os.Getenv("REDIS_HOST")
	if redisHost == "" {
		redisHost = "redis" // Default Docker Compose
	}

	redisClient = redis.NewClient(&redis.Options{
		Addr: fmt.Sprintf("%s:%s", redisHost, "6379"),
		DB:   0, // Usa o DB 0 (configurado no .env)
	})
	log.Println("✅ Conexão Redis estabelecida com sucesso!")

	// 2. Configuração do Servidor HTTP
	http.HandleFunc("/webhook", webhookHandler) // Mapeia o caminho /webhook

	port := "8080"
	log.Printf("🚀 Gateway Go INICIADO na porta :%s", port)

	// Inicia o servidor, cada requisição é tratada em uma goroutine
	log.Fatal(http.ListenAndServe(":"+port, nil))
}

// ------------------------------------------------------------------
// Funções de Utilitário
// ------------------------------------------------------------------

func validateHmac(rawBody []byte, hmacHeader string) bool {
	secret := os.Getenv("WEBHOOK_HMAC_SECRET")
	if secret == "" {
		// Em produção, isso deve ser um erro fatal. Para Dev, deixamos um aviso.
		log.Println("❌ AVISO: WEBHOOK_HMAC_SECRET não configurada.") 
		return true 
	}

	// Cria o novo objeto HMAC (SHA512) usando a chave secreta
	hasher := hmac.New(sha512.New, []byte(secret))
	
	// Escreve o corpo da requisição (os bytes brutos) no hasher
	hasher.Write(rawBody)
	
	// Calcula o hash e o codifica para string hexadecimal (como no Python)
	expectedHmac := hex.EncodeToString(hasher.Sum(nil))

	// Compara o HMAC recebido no header com o HMAC calculado (constante tempo para segurança)
	return hmac.Equal([]byte(expectedHmac), []byte(hmacHeader))
}

// ------------------------------------------------------------------
// Handler Principal do Webhook
// ------------------------------------------------------------------
func webhookHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Método não permitido", http.StatusMethodNotAllowed)
		return
	}

	// PASSO 1: LER o corpo da requisição BRUTO (RAW BODY)
	// io.ReadAll lê a stream de entrada (r.Body) e retorna todos os bytes.
	rawBody, err := io.ReadAll(r.Body)
	if err != nil {
		log.Printf("❌ Erro ao ler body da requisição: %v", err)
		http.Error(w, "Erro ao ler body", http.StatusInternalServerError)
		return
	}
	defer r.Body.Close() 

	// PASSO 2: Validação HMAC (Segurança)
	hmacHeader := r.Header.Get("X-Webhook-Hmac")
	
	if hmacHeader == "" || !validateHmac(rawBody, hmacHeader) {
		log.Println("❌ Requisição recusada: HMAC ausente ou inválido.")
		http.Error(w, "Forbidden: Invalid HMAC signature", http.StatusForbidden)
		return
	}
	
	// PASSO 3: PUBLICAR o corpo BRUTO no canal Redis
	// Publica o JSON completo (rawBody) no canal "new_user_queue"
	err = redisClient.Publish(ctx, redisChannel, rawBody).Err()
	if err != nil {
		log.Printf("❌ Erro ao publicar mensagem no Redis: %v", err)
		http.Error(w, "Erro interno: Falha ao enfileirar mensagem", http.StatusInternalServerError)
		return
	}

	// PASSO 4: RESPONDER 200 OK IMEDIATAMENTE
	w.WriteHeader(http.StatusOK)
	fmt.Fprint(w, `{"status": "queued_by_go"}`)
	log.Printf("✅ Mensagem enfileirada e 200 OK enviado.")
}