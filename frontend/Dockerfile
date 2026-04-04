# AccountSafe Frontend Dockerfile
# Multi-stage build: Build with Node, Serve with Nginx

# ===== Stage 1: Build =====
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci --silent

# Copy source code
COPY . .

# React env vars must be present at build time (CRA inlines them)
ARG REACT_APP_API_URL
ARG REACT_APP_PROJECT_NAME=AccountSafe
ARG REACT_APP_LOGO_URL=/account-safe-logo.png
ARG REACT_APP_TURNSTILE_SITE_KEY
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_PROJECT_NAME=$REACT_APP_PROJECT_NAME
ENV REACT_APP_LOGO_URL=$REACT_APP_LOGO_URL
ENV REACT_APP_TURNSTILE_SITE_KEY=$REACT_APP_TURNSTILE_SITE_KEY

# Build the production application
RUN npm run build

# ===== Stage 2: Production =====
FROM nginx:alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder stage
COPY --from=builder /app/build /usr/share/nginx/html

# Create non-root user for security
RUN addgroup -g 1001 -S nginx-group && \
    adduser -S -D -H -u 1001 -h /var/cache/nginx -s /sbin/nologin -G nginx-group nginx-user && \
    chown -R nginx-user:nginx-group /var/cache/nginx /var/run /var/log/nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html && \
    touch /var/run/nginx.pid && \
    chown nginx-user:nginx-group /var/run/nginx.pid

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
