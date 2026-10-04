FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG GOOGLE_MAPS_BROWSER_API_KEY
ENV GOOGLE_MAPS_BROWSER_API_KEY=$GOOGLE_MAPS_BROWSER_API_KEY
RUN npm test && npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
