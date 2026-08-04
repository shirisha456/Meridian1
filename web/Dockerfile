FROM node:22-slim AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# NEXT_PUBLIC_* variables are inlined into the client bundle at build time,
# not read at container start — they're browser-visible/not-secret, so
# baking this in here (rather than templating it at container startup) is
# the correct place to set it.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

FROM node:22-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production

RUN groupadd --system --gid 1001 nodejs \
  && useradd --system --uid 1001 --gid nodejs nextjs

COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=build --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
