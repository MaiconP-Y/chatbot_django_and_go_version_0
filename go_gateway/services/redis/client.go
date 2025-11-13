package redis

import (
	"context"
	"fmt"
	"os"
	"time" // Necessário para o WithTimeout

	"github.com/go-redis/redis/v8"
)

// ChannelName agora é o nome da nossa LISTA/FILA
const ChannelName = "new_user_queue" 

// Client (será inicializado uma vez)
var Client *redis.Client

// InitClient configura e testa a conexão com o Redis
func InitClient(ctx context.Context) error {
	redisHost := os.Getenv("REDIS_HOST")
	if redisHost == "" {
		redisHost = "redis" // Default Docker Compose
	}

	Client = redis.NewClient(&redis.Options{
		Addr: fmt.Sprintf("%s:%s", redisHost, "6379"),
		DB:   0, 
	})

	// Teste de conexão: PING com um timeout seguro de 3 segundos
	pingCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	
	_, err := Client.Ping(pingCtx).Result()
	if err != nil {
		return fmt.Errorf("falha ao conectar e pingar o Redis: %w", err)
	}
	
	return nil
}

// PublishMessage insere (LPUSH) a mensagem na fila, usando o contexto de requisição
func PublishMessage(ctx context.Context, rawBody []byte) error {
    // ----------------------------------------------------
    // TIMEOUT CRÍTICO DE 100ms para a operação de Redis
    // Garante que o Go Gateway não trave esperando por Redis lento.
    // ----------------------------------------------------
    publishCtx, cancel := context.WithTimeout(ctx, 100*time.Millisecond)
    defer cancel()
    
    // LPUSH empilha na lista (fila persistente)
    err := Client.LPush(publishCtx, ChannelName, rawBody).Err()
    if err != nil {
        // Retorna o erro, que o handler verificará se é um timeout
        return fmt.Errorf("erro ao LPush/publicar mensagem no Redis: %w", err)
    }
    return nil
}