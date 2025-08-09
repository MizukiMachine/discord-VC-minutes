#!/bin/bash

# Discord Minutes Bot - GCP Deployment Script
# Project: discord-vc-minutes (252955676671)
# Account: negichanfumakun@gmail.com

set -e  # Exit on any error

PROJECT_ID="discord-vc-minutes"
PROJECT_NUMBER="252955676671"
REGION="asia-northeast1"
SERVICE_NAME="discord-minutes-bot"

echo "🚀 Discord Minutes Bot - GCP Deployment"
echo "Project ID: $PROJECT_ID"
echo "Project Number: $PROJECT_NUMBER"
echo "Region: $REGION"
echo ""

# Check if gcloud is authenticated
echo "📋 Checking gcloud authentication..."
if ! gcloud auth list --filter="status:ACTIVE" --format="value(account)" | grep -q "negichanfumakun@gmail.com"; then
    echo "❌ Please authenticate with gcloud first:"
    echo "   gcloud auth login"
    exit 1
fi

# Set project
echo "🔧 Setting project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔌 Enabling required APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    redis.googleapis.com

# Check environment variables
echo "🔐 Environment variables check:"
echo "Please set the following environment variables in Cloud Run after deployment:"
echo "  - DISCORD_BOT_TOKEN: Your Discord bot token"
echo "  - REDIS_URL: Redis connection URL (will be created)"
echo "  - OPENAI_API_KEY: Your OpenAI API key"
echo "  - VIBE_URL: Your Vibe server URL (e.g., http://your-ip:3022)"
echo ""

# Build and deploy using Cloud Build
echo "🏗️  Building and deploying with Cloud Build..."
gcloud builds submit --config=cloudbuild.yaml

echo ""
echo "✅ Deployment initiated!"
echo ""
echo "📋 Next steps:"
echo "1. Set up Redis instance:"
echo "   gcloud redis instances create discord-redis \\"
echo "     --region=$REGION \\"
echo "     --memory-size-gb=1 \\"
echo "     --network=default"
echo ""
echo "2. Update Cloud Run environment variables:"
echo "   gcloud run services update $SERVICE_NAME \\"
echo "     --region=$REGION \\"
echo "     --set-env-vars='DISCORD_BOT_TOKEN=your_token_here,OPENAI_API_KEY=your_key_here,VIBE_URL=http://your-vibe-server:3022'"
echo ""
echo "3. Set Redis URL after Redis instance is ready:"
echo "   REDIS_IP=\$(gcloud redis instances describe discord-redis --region=$REGION --format='value(host)')"
echo "   gcloud run services update $SERVICE_NAME \\"
echo "     --region=$REGION \\"
echo "     --set-env-vars='REDIS_URL=redis://\$REDIS_IP:6379'"
echo ""
echo "4. Check deployment status:"
echo "   gcloud run services describe $SERVICE_NAME --region=$REGION"
echo ""
echo "🎉 Ready to rock! Your Discord bot will be live on Cloud Run!"