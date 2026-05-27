# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --prefer-offline

COPY . .
RUN npm run build

# ── Stage 2: serve (nginx) ────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runner

# Config nginx per Single-Page App (react-router fallback su index.html)
COPY --from=builder /app/dist /usr/share/nginx/html

RUN cat > /etc/nginx/conf.d/default.conf << 'EOF'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml application/xml+rss text/javascript
               image/svg+xml;
    gzip_min_length 1000;

    # Cache assets (contenuto hash-busted da Vite)
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?|ttf)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Service Worker: no cache
    location = /sw.js {
        add_header Cache-Control "no-cache";
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy verso il backend
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # WebSocket proxy
    location /ws/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
EOF

EXPOSE 80
