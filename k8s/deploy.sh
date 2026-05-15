#!/bin/bash
# ============================================================
# 邮件分类系统 - Kubernetes 一键部署脚本
# 使用方法: bash deploy.sh [deploy|delete|status]
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAMESPACE="mail-system"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()  { echo -e "${RED}[ERR]${NC}   $1"; }
step() { echo -e "\n${BLUE}==== $1 ====${NC}"; }

apply() {
    local file="$1"
    if [ -f "${SCRIPT_DIR}/${file}" ]; then
        kubectl apply -f "${SCRIPT_DIR}/${file}"
        log "Applied ${file}"
    else
        warn "Skipped ${file} (not found)"
    fi
}

deploy() {
    step "1/8 创建 Namespace"
    kubectl apply -f "${SCRIPT_DIR}/namespace.yaml"
    kubectl label namespace ${NAMESPACE} istio-injection=enabled --overwrite 2>/dev/null || true
    log "Namespace ${NAMESPACE} ready (Istio injection enabled)"

    step "2/8 创建 Secrets"
    kubectl apply -f "${SCRIPT_DIR}/mysql-secret.yaml" 2>/dev/null || \
        kubectl create secret generic mysql-secret --namespace=${NAMESPACE} \
            --from-literal=password=password --dry-run=client -o yaml | kubectl apply -f -
    kubectl apply -f "${SCRIPT_DIR}/rabbitmq.yaml" 2>/dev/null || true
    kubectl apply -f "${SCRIPT_DIR}/llm-secret.yaml" 2>/dev/null || \
        kubectl create secret generic llm-secret --namespace=${NAMESPACE} \
            --from-literal=deepseek="" --from-literal=dashscope="" \
            --from-literal=openai="" --from-literal=zhipu="" \
            --dry-run=client -o yaml | kubectl apply -f -

    step "3/8 创建 ConfigMap"
    kubectl apply -f "${SCRIPT_DIR}/app-config.yaml"

    step "4/8 部署 MySQL"
    kubectl apply -f "${SCRIPT_DIR}/mysql.yaml"
    log "Waiting for MySQL to be ready..."
    kubectl wait --namespace=${NAMESPACE} --for=condition=ready pod \
        --selector=app=mysql --timeout=180s 2>/dev/null || \
        warn "MySQL may need more time, continuing..."

    step "5/8 部署 RabbitMQ"
    kubectl apply -f "${SCRIPT_DIR}/rabbitmq.yaml"
    log "Waiting for RabbitMQ to be ready..."
    kubectl wait --namespace=${NAMESPACE} --for=condition=ready pod \
        --selector=app=rabbitmq --timeout=180s 2>/dev/null || \
        warn "RabbitMQ may need more time, continuing..."

    step "6/8 部署 Acceptor 节点 (LLM Agent)"
    kubectl apply -f "${SCRIPT_DIR}/agent.yaml"
    log "Waiting for Acceptor nodes..."
    kubectl wait --namespace=${NAMESPACE} --for=condition=ready pod \
        --selector='app in (mail-acceptor-1,mail-acceptor-2,mail-acceptor-3)' \
        --timeout=120s 2>/dev/null || \
        warn "Acceptor nodes may need more time, continuing..."

    step "7/8 部署主应用 (Flask)"
    kubectl apply -f "${SCRIPT_DIR}/app.yaml"
    log "Waiting for App pods to be ready..."
    kubectl wait --namespace=${NAMESPACE} --for=condition=ready pod \
        --selector=app=mail-app --timeout=120s 2>/dev/null || \
        warn "App pods may need more time, continuing..."

    step "8/8 部署 Istio 服务网格"
    kubectl apply -f "${SCRIPT_DIR}/istio.yaml"

    step "部署完成！"
    echo ""
    kubectl get all -n ${NAMESPACE}
    echo ""
    log "查看 Ingress: kubectl get ingress -n ${NAMESPACE}"
    log "查看 Istio 路由: kubectl get vs,gw,dr -n ${NAMESPACE}"
    log "查看 RabbitMQ 管理界面: kubectl port-forward -n ${NAMESPACE} svc/rabbitmq 15672:15672"
    echo ""
    log "暴露服务 (三选一):"
    echo "  1. Ingress (需要域名解析): 添加 mail.local -> Ingress IP 到 hosts"
    echo "  2. Istio Gateway: kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80"
    echo "  3. 直接端口转发:  kubectl port-forward -n ${NAMESPACE} svc/mail-app 5000:80"
    echo ""
    warn "NLMM API Key 未设置！如需 LLM 功能，请执行:"
    echo "  kubectl edit secret llm-secret -n ${NAMESPACE}"
    echo "  将 deepseek 字段的 value 填入 Base64 编码的 API Key"
    echo "  (echo -n 'your-api-key' | base64)"
}

delete() {
    step "删除所有资源"
    kubectl delete -f "${SCRIPT_DIR}/istio.yaml" --ignore-not-found 2>/dev/null || true
    kubectl delete -f "${SCRIPT_DIR}/app.yaml" --ignore-not-found 2>/dev/null || true
    kubectl delete -f "${SCRIPT_DIR}/agent.yaml" --ignore-not-found 2>/dev/null || true
    kubectl delete -f "${SCRIPT_DIR}/rabbitmq.yaml" --ignore-not-found 2>/dev/null || true
    kubectl delete -f "${SCRIPT_DIR}/mysql.yaml" --ignore-not-found 2>/dev/null || true
    kubectl delete configmap app-config -n ${NAMESPACE} --ignore-not-found 2>/dev/null || true
    kubectl delete secret llm-secret mysql-secret rabbitmq-secret -n ${NAMESPACE} --ignore-not-found 2>/dev/null || true
    kubectl delete pvc --all -n ${NAMESPACE} --ignore-not-found 2>/dev/null || true
    kubectl delete -f "${SCRIPT_DIR}/namespace.yaml" --ignore-not-found 2>/dev/null || true
    log "所有资源已删除"
}

status() {
    step "Pod 状态"
    kubectl get pods -n ${NAMESPACE} -o wide
    echo ""
    step "Service 状态"
    kubectl get svc -n ${NAMESPACE}
    echo ""
    step "Ingress / Istio"
    kubectl get ingress -n ${NAMESPACE} 2>/dev/null || true
    kubectl get vs,gw,dr -n ${NAMESPACE} 2>/dev/null || true
    echo ""
    step "Persistent Volumes"
    kubectl get pvc -n ${NAMESPACE} 2>/dev/null || true
}

case "${1:-deploy}" in
    deploy)   deploy ;;
    delete)   delete ;;
    status)   status ;;
    *)
        echo "Usage: bash deploy.sh [deploy|delete|status]"
        exit 1
        ;;
esac