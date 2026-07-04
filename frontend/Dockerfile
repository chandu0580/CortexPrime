# ==============================================================
# CORTEXPRIME FRONTEND — Multi-stage Dockerfile
# Node.js 20 | Next.js 16 | TypeScript | TailwindCSS
#
# Stages:
#   base          Alpine base with Node.js 20
#   development   Dev target (source mounted via volume)
#   deps          Production npm dependencies
#   builder       Next.js production build
#   production    Minimal standalone runtime image
# ==============================================================

# --------------------------------------------------------------
# BASE
# --------------------------------------------------------------
FROM node:20-alpine AS base

ENV NODE_ENV=production
WORKDIR /app

# Install OS-level utilities used during build
RUN apk add --no-cache libc6-compat curl wget

# --------------------------------------------------------------
# DEVELOPMENT — Hot-reload, source code mounted via volume
# --------------------------------------------------------------
FROM node:20-alpine AS development

ENV NODE_ENV=development
WORKDIR /app

# Install dependencies so node_modules exist in image layer
# (docker-compose preserves these via anonymous volume: /app/node_modules)
COPY package.json package-lock.json ./
RUN npm install

EXPOSE 3000

# next dev handles compilation; WATCHPACK_POLLING set in docker-compose
CMD ["npm", "run", "dev"]

# --------------------------------------------------------------
# DEPS — Production dependencies only
# --------------------------------------------------------------
FROM base AS deps

COPY package.json package-lock.json ./
RUN npm ci --omit=dev --legacy-peer-deps

# --------------------------------------------------------------
# BUILDER — Full build (includes devDependencies for CSS/TS tooling)
# --------------------------------------------------------------
FROM base AS builder

# base inherits NODE_ENV=production. npm ci respects that and skips
# devDependencies, so we override NODE_ENV inline for the install step only.
# The actual `next build` still runs under NODE_ENV=production (inherited).

WORKDIR /app

COPY package.json package-lock.json ./
RUN NODE_ENV=development npm ci --legacy-peer-deps

COPY . .

# Build the Next.js app (standalone output enabled in next.config.ts)
RUN npm run build

# --------------------------------------------------------------
# PRODUCTION — Minimal standalone runtime
# --------------------------------------------------------------
FROM node:20-alpine AS production

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

WORKDIR /app

# Non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

# Copy standalone build output
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static     ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public           ./public

USER nextjs

EXPOSE 3000

# next build --output=standalone produces server.js
CMD ["node", "server.js"]
