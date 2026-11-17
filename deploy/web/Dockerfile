FROM node:24.15.0-bookworm-slim AS build

WORKDIR /src/frontend
ARG NPM_REGISTRY=https://registry.npmmirror.com
ENV npm_config_registry=${NPM_REGISTRY} \
    COREPACK_NPM_REGISTRY=${NPM_REGISTRY}
RUN corepack enable && corepack prepare pnpm@11.5.1 --activate

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
COPY exchange/ /src/exchange/
RUN pnpm run build

FROM nginx:1.27-alpine
COPY --from=build /src/frontend/dist /usr/share/nginx/html
COPY deploy/web/nginx-image.conf /etc/nginx/conf.d/default.conf
