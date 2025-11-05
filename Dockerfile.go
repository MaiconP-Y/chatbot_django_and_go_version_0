FROM golang:1.24-alpine AS builder


ENV CGO_ENABLED=0 \
    GOOS=linux \
    GOARCH=amd64

WORKDIR /build

RUN apk update && \
    apk upgrade && \
    rm -rf /var/cache/apk/*

COPY go.mod go.sum ./

COPY . .

RUN go mod download
RUN go mod tidy

RUN go build -o /app/go-webhook-gateway ./main.go

FROM alpine:latest AS final

WORKDIR /app

RUN apk --no-cache add ca-certificates

COPY --from=builder /app/go-webhook-gateway .

EXPOSE 8080


CMD ["./go-webhook-gateway"]
