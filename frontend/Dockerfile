# ---------- 构建阶段 ----------
FROM node:20-alpine AS builder
WORKDIR /app

COPY frontend/package*.json ./
# 优先走 npm ci（快 + 可复现），lock 文件不同步时自动回退 npm install
RUN npm ci || npm install

COPY frontend/ ./
RUN npm run build

# ---------- 运行阶段 ----------
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
