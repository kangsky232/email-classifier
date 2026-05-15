# ============================================================
# 邮件分类系统 - Kubernetes 一键部署脚本 (Windows PowerShell)
# 使用方法: .\deploy.ps1 [deploy|delete|status]
# ============================================================

param(
    [ValidateSet("deploy", "delete", "status")]
    [string]$Action = "deploy"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Namespace = "mail-system"

function Write-Step($msg) {
    Write-Host "`n==== $msg =====" -ForegroundColor Blue
}

function Write-Info($msg) {
    Write-Host "[INFO]  $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "[WARN]  $msg" -ForegroundColor Yellow
}

function Invoke-KubectlApply($file) {
    $path = Join-Path $ScriptDir $file
    if (Test-Path $path) {
        kubectl apply -f $path
        Write-Info "Applied $file"
    } else {
        Write-Warn "Skipped $file (not found)"
    }
}

function Deploy-All {
    Write-Step "1/8 创建 Namespace"
    kubectl apply -f (Join-Path $ScriptDir "namespace.yaml")
    kubectl label namespace $Namespace istio-injection=enabled --overwrite 2>$null
    Write-Info "Namespace $Namespace ready (Istio injection enabled)"

    Write-Step "2/8 创建 Secrets"
    Invoke-KubectlApply "rabbitmq.yaml"
    Invoke-KubectlApply "llm-secret.yaml"

    Write-Step "3/8 创建 ConfigMap"
    Invoke-KubectlApply "app-config.yaml"

    Write-Step "4/8 部署 MySQL"
    Invoke-KubectlApply "mysql.yaml"
    Write-Info "Waiting for MySQL to be ready..."
    kubectl wait --namespace=$Namespace --for=condition=ready pod `
        --selector=app=mysql --timeout=180s 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Warn "MySQL may need more time, continuing..." }

    Write-Step "5/8 部署 RabbitMQ"
    Invoke-KubectlApply "rabbitmq.yaml"
    Write-Info "Waiting for RabbitMQ to be ready..."
    kubectl wait --namespace=$Namespace --for=condition=ready pod `
        --selector=app=rabbitmq --timeout=180s 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Warn "RabbitMQ may need more time, continuing..." }

    Write-Step "6/8 部署 Acceptor 节点 (LLM Agent)"
    Invoke-KubectlApply "agent.yaml"
    Write-Info "Waiting for Acceptor nodes..."
    kubectl wait --namespace=$Namespace --for=condition=ready pod `
        --selector='app in (mail-acceptor-1,mail-acceptor-2,mail-acceptor-3)' `
        --timeout=120s 2>$null

    Write-Step "7/8 部署主应用 (Flask)"
    Invoke-KubectlApply "app.yaml"
    Write-Info "Waiting for App pods to be ready..."
    kubectl wait --namespace=$Namespace --for=condition=ready pod `
        --selector=app=mail-app --timeout=120s 2>$null

    Write-Step "8/8 部署 Istio 服务网格"
    Invoke-KubectlApply "istio.yaml"

    Write-Step "部署完成！"
    Write-Host ""
    kubectl get all -n $Namespace
    Write-Host ""
    Write-Info "查看 Ingress: kubectl get ingress -n $Namespace"
    Write-Info "查看 Istio 路由: kubectl get vs,gw,dr -n $Namespace"
    Write-Info "查看 RabbitMQ 管理界面: kubectl port-forward -n $Namespace svc/rabbitmq 15672:15672"
    Write-Host ""
    Write-Info "暴露服务 (三选一):"
    Write-Host "  1. Ingress (需要域名解析): 添加 mail.local -> Ingress IP 到 hosts"
    Write-Host "  2. Istio Gateway: kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80"
    Write-Host "  3. 直接端口转发:  kubectl port-forward -n $Namespace svc/mail-app 5000:80"
    Write-Host ""
    Write-Warn "LLM API Key 未设置！如需 LLM 功能，请编辑 llm-secret:"
    Write-Host "  kubectl edit secret llm-secret -n $Namespace"
}

function Delete-All {
    Write-Step "删除所有资源"
    kubectl delete -f (Join-Path $ScriptDir "istio.yaml") --ignore-not-found 2>$null
    kubectl delete -f (Join-Path $ScriptDir "app.yaml") --ignore-not-found 2>$null
    kubectl delete -f (Join-Path $ScriptDir "agent.yaml") --ignore-not-found 2>$null
    kubectl delete -f (Join-Path $ScriptDir "rabbitmq.yaml") --ignore-not-found 2>$null
    kubectl delete -f (Join-Path $ScriptDir "mysql.yaml") --ignore-not-found 2>$null
    kubectl delete configmap app-config -n $Namespace --ignore-not-found 2>$null
    kubectl delete secret llm-secret mysql-secret rabbitmq-secret -n $Namespace --ignore-not-found 2>$null
    kubectl delete pvc --all -n $Namespace --ignore-not-found 2>$null
    kubectl delete -f (Join-Path $ScriptDir "namespace.yaml") --ignore-not-found 2>$null
    Write-Info "所有资源已删除"
}

function Show-Status {
    Write-Step "Pod 状态"
    kubectl get pods -n $Namespace -o wide
    Write-Host ""
    Write-Step "Service 状态"
    kubectl get svc -n $Namespace
    Write-Host ""
    Write-Step "Ingress / Istio"
    kubectl get ingress,vs,gw,dr -n $Namespace 2>$null
    Write-Host ""
    Write-Step "Persistent Volumes"
    kubectl get pvc -n $Namespace 2>$null
}

switch ($Action) {
    "deploy" { Deploy-All }
    "delete" { Delete-All }
    "status" { Show-Status }
}