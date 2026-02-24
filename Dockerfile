# Build openclaw from source to avoid npm packaging gaps
FROM node:22-bookworm AS openclaw-build

# Dependencies needed for openclaw build
RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    curl \
    python3 \
    make \
    g++ \
  && rm -rf /var/lib/apt/lists/*

# Install Bun (openclaw build uses it)
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:${PATH}"

RUN corepack enable

WORKDIR /openclaw

# Pin to the version indicated in your recent status report
ARG OPENCLAW_GIT_REF=v2026.2.23
RUN git clone --depth 1 --branch "${OPENCLAW_GIT_REF}" https://github.com/openclaw/openclaw.git .

# Patch: relax version requirements for workspace packages
RUN set -eux; \
  find ./extensions -name 'package.json' -type f | while read -r f; do \
    sed -i -E 's/"openclaw"[[:space:]]*:[[:space:]]*">=[^"]+"/"openclaw": "*"/g' "$f"; \
    sed -i -E 's/"openclaw"[[:space:]]*:[[:space:]]*"workspace:[^"]+"/"openclaw": "*"/g' "$f"; \
  done

RUN pnpm install --no-frozen-lockfile
RUN pnpm build
ENV OPENCLAW_PREFER_PNPM=1
RUN pnpm ui:install && pnpm ui:build


# Runtime image
FROM node:22-bookworm
ENV NODE_ENV=production

RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    tini \
    python3 \
    python3-venv \
    openjdk-17-jre-headless \
    curl \
    wget \
  && rm -rf /var/lib/apt/lists/*

# Install signal-cli binary for native linking (v0.13.24 fixes config version compatibility)
RUN wget https://github.com/AsamK/signal-cli/releases/download/v0.13.24/signal-cli-0.13.24.tar.gz \
  && tar xzf signal-cli-0.13.24.tar.gz -C /opt \
  && ln -s /opt/signal-cli-0.13.24/bin/signal-cli /usr/local/bin/signal-cli \
  && rm signal-cli-0.13.24.tar.gz

# Provide pnpm in the runtime image for openclaw updates/plugin management
RUN corepack enable && corepack prepare pnpm@10.23.0 --activate

# Persist user-installed tools and setup persistent paths
ENV NPM_CONFIG_PREFIX=/data/npm
ENV NPM_CONFIG_CACHE=/data/npm-cache
ENV PNPM_HOME=/data/pnpm
ENV PNPM_STORE_DIR=/data/pnpm-store
ENV PATH="/data/npm/bin:/data/pnpm:${PATH}"

WORKDIR /app

# Wrapper dependencies
COPY package.json ./
RUN npm install --omit=dev && npm cache clean --force

# Copy built openclaw from build stage
COPY --from=openclaw-build /openclaw /openclaw

# Provide the openclaw executable
RUN printf '%s\n' '#!/usr/bin/env bash' 'exec node /openclaw/dist/entry.js "$@"' > /usr/local/bin/openclaw \
  && chmod +x /usr/local/bin/openclaw

COPY src ./src

# Railway injects PORT at runtime; default wrapper typically uses 8080
EXPOSE 8080

# Use tini to manage signal forwarding and zombie processes
ENTRYPOINT ["tini", "--"]
CMD ["node", "src/server.js"]
