# syntax=docker/dockerfile:1
# The dashboard: the Vite build served by nginx, which also forwards /api to the API.
# Build from the repository root:
#   docker build -f infra/docker/web.Dockerfile -t fraud-risk-web .
ARG NODE_IMAGE=node:22-bookworm-slim
ARG NGINX_IMAGE=nginx:1.29-alpine

FROM ${NODE_IMAGE} AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM ${NGINX_IMAGE}
# Run as the image's unprivileged nginx user: port 8080, and the few paths nginx writes owned by it.
RUN sed -i -e 's|^pid .*|pid /tmp/nginx.pid;|' -e '/^user /d' /etc/nginx/nginx.conf \
 && chown -R nginx:nginx /var/cache/nginx /etc/nginx/conf.d
COPY infra/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY infra/nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /src/dist /usr/share/nginx/html
# Where the API listens; the template above is filled in with it when the container starts.
ENV API_UPSTREAM=api:8000
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
