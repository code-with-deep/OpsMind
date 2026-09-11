# Build stage — leave VITE_API_BASE_URL empty so the browser uses same-origin
# paths (/auth, /investigations, …) which nginx proxies to the API container.
FROM node:22-alpine AS build
WORKDIR /app

ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package.json package-lock.json* ./
# P2-15: `npm ci` installs exactly what package-lock.json pins (and fails if the
# lockfile and package.json disagree) — `npm install` ignores the lockfile's
# guarantees and lets transitive versions drift between builds.
RUN npm ci
COPY . ./
RUN npm run build

# Production serve stage — static + API reverse proxy
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 3000
# P2-16: healthcheck against the SPA fallback route.
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -qO- http://127.0.0.1:3000/ >/dev/null 2>&1 || exit 1
CMD ["nginx", "-g", "daemon off;"]
