package hmac

import (
	"crypto/hmac"
	"crypto/sha512"
	"encoding/hex"
	"fmt"
	"os"
)

// secretKey é carregada uma vez na inicialização da aplicação
var secretKey []byte

// InitSecret carrega a chave secreta de ambiente e garante que ela exista.
func InitSecret() error {
	hmacKey := os.Getenv("WEBHOOK_HMAC_SECRET")
	if hmacKey == "" {
		// Esta é uma falha crítica, deve abortar a inicialização.
		return fmt.Errorf("WEBHOOK_HMAC_SECRET não está definida no ambiente")
	}
	secretKey = []byte(hmacKey)
	return nil
}

// ValidateHmac verifica se a assinatura da requisição está correta
func ValidateHmac(body []byte, expectedHmac string) bool {
	// 1. Calcula o HMAC do corpo da requisição com a chave secreta
	h := hmac.New(sha512.New, secretKey)
	h.Write(body)
	calculatedHmac := hex.EncodeToString(h.Sum(nil))

	// 2. Compara o resultado com o HMAC esperado
	// hmac.Equal é usado para evitar ataques de temporização
	return hmac.Equal([]byte(expectedHmac), []byte(calculatedHmac))
}