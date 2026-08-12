# syntax=docker/dockerfile:1
FROM docker.io/library/node:24-alpine

WORKDIR /app

COPY package.json package-lock.json ./
# `ci` y no `install`: instala exactamente lo del lock, así la imagen de
# desarrollo trae las mismas versiones que la CI y que producción.
RUN npm ci

COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
