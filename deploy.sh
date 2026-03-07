#!/usr/bin/env bash
set -euo pipefail

# Prevent manual paging through outputs.
export AWS_PAGER=""

REGION="eu-west-2"
CLUSTER="cress"
SERVICE="cress-backend"

# Read infra values from Terraform outputs
cd "$(dirname "$0")/terraform"
ECR_REPO=$(terraform output -raw ecr_repo_url)
S3_BUCKET=$(terraform output -raw s3_bucket_name)
CF_DISTRIBUTION_ID=$(terraform output -raw cloudfront_distribution_id)
cd ..

DEPLOY_BACKEND=false
DEPLOY_FRONTEND=false

usage() {
    echo "Usage: $0 [--backend] [--frontend] [--all]"
    exit 1
}

if [[ $# -eq 0 ]]; then usage; fi

for arg in "$@"; do
    case $arg in
        --backend) DEPLOY_BACKEND=true ;;
        --frontend) DEPLOY_FRONTEND=true ;;
        --all) DEPLOY_BACKEND=true; DEPLOY_FRONTEND=true ;;
        *) usage ;;
    esac
done

# Authenticate to ECR (token lasts 12 hours)
echo "--- Authenticating to ECR..."
aws ecr get-login-password --region "$REGION" | \
    docker login --username AWS --password-stdin "$ECR_REPO"

if $DEPLOY_BACKEND; then
    echo "--- Building backend image..."
    docker build -t cress-backend ./backend

    echo "--- Pushing backend image..."
    docker tag cress-backend:latest "$ECR_REPO:latest"
    docker push "$ECR_REPO:latest"

    echo "--- Triggering ECS redeployment..."
    aws ecs update-service \
        --cluster "$CLUSTER" \
        --service "$SERVICE" \
        --force-new-deployment \
        --region "$REGION" \

    echo "Backend deployed."
fi

if $DEPLOY_FRONTEND; then
    echo "--- Building frontend..."
    cd frontend
    npm run build
    cd ..

    echo "--- Syncing to S3..."
    aws s3 sync frontend/dist/ "s3://$S3_BUCKET/" --delete

    echo "--- Invalidating CloudFront cache..."
    aws cloudfront create-invalidation \
        --distribution-id "$CF_DISTRIBUTION_ID" \
        --paths "/*" \

    echo "Frontend deployed."
fi
