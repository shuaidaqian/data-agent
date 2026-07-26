#!/bin/bash

# 创建 Docker 网络
docker network create dataherald_network

# 使用 Docker Compose 启动服务
docker-compose -p dataherald -f services/engine/docker-compose.yml up --build -d
docker-compose -p dataherald -f services/enterprise/docker-compose.yml up --build -d
docker-compose -p dataherald -f services/slackbot/docker-compose.yml up --build -d
docker-compose -p dataherald -f services/admin-console/docker-compose.yml up --build -d
