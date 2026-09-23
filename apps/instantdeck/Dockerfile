FROM node:20-bookworm-slim AS build

WORKDIR /app
ENV NODE_ENV=development

COPY package*.json ./
RUN npm ci

COPY . ./
RUN npm run build

FROM node:20-bookworm-slim AS runtime

WORKDIR /app
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000
ENV BODY_SIZE_LIMIT=210M

COPY package*.json ./
RUN npm ci --omit=dev
COPY --from=build /app/build ./build

ARG DECK_BUILD_COMMIT=development
RUN printf '%s\n' "$DECK_BUILD_COMMIT" > /app/BUILD_REVISION

EXPOSE 3000
CMD ["npm", "start"]
