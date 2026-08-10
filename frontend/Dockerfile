# syntax=docker/dockerfile:1
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm npm ci


# --- dev: Vite dev server + HMR, code mount qua volume trong docker-compose ---
FROM deps AS dev
ENV NODE_ENV=development
EXPOSE 5173
CMD ["npm", "run", "dev"]


# --- build + phục vụ tĩnh bằng nginx ---
FROM deps AS build
COPY . .
# VITE_* được nhúng vào bundle lúc BUILD (không đọc được lúc chạy), nên URL API phải
# truyền vào từ đây thay vì qua environment của container.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
# SPA: mọi route không khớp file tĩnh đều trả index.html cho react-router xử lý.
RUN printf 'server {\n\
  listen 5173;\n\
  root /usr/share/nginx/html;\n\
  index index.html;\n\
  location /assets/ { expires 1y; add_header Cache-Control "public, immutable"; }\n\
  location / { try_files $uri $uri/ /index.html; }\n\
}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
