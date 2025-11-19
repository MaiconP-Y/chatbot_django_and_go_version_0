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

func PublishMessage(ctx context.Context, rawBody []byte) error {
    publishCtx, cancel := context.WithTimeout(ctx, 100*time.Millisecond)
    defer cancel()
    
    // ➡️ RPUSH (Right Push) para garantir FIFO. Apenas enfileira o payload BRUTO.
    if err := Client.RPush(publishCtx, ChannelName, rawBody).Err(); err != nil {
        return fmt.Errorf("erro ao RPush na fila principal: %w", err)
    }
    
    return nil
}