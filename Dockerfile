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
    lsof \
    cron \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libatspi2.0-0 \
    libdrm2 \
    libgbm1 \
    libxi6 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxkbcommon0 \
    libxcb-dri3-0 \
    fonts-liberation \
  && rm -rf /var/lib/apt/lists/*

# Install signal-cli binary for native linking (v0.13.24 fixes config version compatibility)
RUN wget https://github.com/AsamK/signal-cli/releases/download/v0.13.24/signal-cli-0.13.24.tar.gz \
  && tar xzf signal-cli-0.13.24.tar.gz -C /opt \
  && ln -s /opt/signal-cli-0.13.24/bin/signal-cli /usr/local/bin/signal-cli \
  && rm signal-cli-0.13.24.tar.gz

# Provide pnpm in the runtime image for openclaw updates/plugin management
# Retry on transient registry errors (503, rate limit)
RUN corepack enable && \
  for i in 1 2 3 4 5; do corepack prepare pnpm@10.23.0 --activate && exit 0; sleep 15; done; exit 1

# Persist user-installed tools and setup persistent paths
ENV NPM_CONFIG_PREFIX=/data/npm
ENV NPM_CONFIG_CACHE=/data/npm-cache
ENV PNPM_HOME=/data/pnpm
ENV PNPM_STORE_DIR=/data/pnpm-store
ENV PATH="/data/npm/bin:/data/pnpm:${PATH}"
# Playwright browser binaries stored on persistent volume (survives restarts)
ENV PLAYWRIGHT_BROWSERS_PATH=/data/playwright-browsers

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

# Daily job search cron — 09:00 IST = 03:30 UTC
RUN echo "30 3 * * * root bash /data/workspace/job_search/scripts/run_daily.sh >> /data/workspace/job_search/daily.log 2>&1" \
    > /etc/cron.d/job-search \
 && chmod 0644 /etc/cron.d/job-search

# Railway injects PORT at runtime; default wrapper typically uses 8080
EXPOSE 8080

# Use tini to manage signal forwarding and zombie processes
ENTRYPOINT ["tini", "--"]
CMD ["bash", "src/start.sh"]
