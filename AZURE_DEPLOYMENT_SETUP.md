# GitHub Actions Azure Deployment Setup Guide

## Overview
This guide explains how to set up GitHub Actions workflow for automated deployment to Azure App Service.

## Prerequisites
1. Azure Subscription
2. Azure App Service created
3. GitHub repository with admin access
4. Azure CLI installed locally

## Setup Steps

### 1. Generate Azure Credentials
Run this command in your local terminal:
```bash
az ad sp create-for-rbac --name "github-actions-sp" --role contributor --scopes /subscriptions/{subscription-id}
```

This will output JSON credentials. Save this entire JSON object.

### 2. Create GitHub Secrets
Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:

#### Required Secrets:
- **AZURE_CREDENTIALS**: Paste the full JSON from step 1
- **AZURE_APP_NAME**: Your Azure App Service name (e.g., "lexaio-chatbot")
- **AZURE_RESOURCE_GROUP**: Your Azure resource group name
- **AZURE_APP_URL**: Your Azure App Service URL (e.g., "https://lexaio-chatbot.azurewebsites.net")

#### Application Secrets (from your .env file):
- **OPENAI_API_KEY**: Your OpenAI API key
- **AZURE_SEARCH_KEY**: Azure Cognitive Search API key
- **AZURE_SEARCH_ENDPOINT**: Azure Cognitive Search endpoint URL
- **AZURE_SEARCH_INDEX**: Index name (e.g., "legal-documents")
- **LEGAL_DICTIONARY_PATH**: Path to legal dictionary in storage
- **ECOURTS_API_URL**: eCourts API base URL
- **ECOURTS_API_KEY**: eCourts API authentication key

### 3. Prepare Azure App Service

#### Create App Service
```bash
az appservice plan create \
  --name lexaio-plan \
  --resource-group {resource-group} \
  --sku B1 \
  --is-linux

az webapp create \
  --resource-group {resource-group} \
  --plan lexaio-plan \
  --name {app-name} \
  --runtime "PYTHON|3.11"
```

#### Enable GitHub Deployments
1. In Azure Portal → App Service → Deployment Center
2. Select "GitHub" as source
3. Authenticate and select your repository
4. Select main branch

### 4. Configure Startup Command
In Azure Portal → App Service → Configuration → General settings:
```
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app:app
```

### 5. Test Deployment
Push a commit to `main` branch:
```bash
git add .
git commit -m "Add deployment workflow"
git push origin main
```

Monitor deployment:
1. GitHub → Actions tab - view workflow execution
2. Azure Portal → Deployment Center - view app deployments

## Workflow Triggers

The workflow automatically runs on:
- Push to `main` or `develop` branches
- Pull requests to `main` branch
- Manual trigger via GitHub Actions UI (workflow_dispatch)

## Health Check

After deployment, the workflow runs a health check against `/health` endpoint.
Customize this endpoint in `app.py` as needed.

## Troubleshooting

### Common Issues

**Deployment fails with credential errors:**
- Verify all AZURE_* secrets are correctly set
- Check AZURE_CREDENTIALS JSON is valid

**App fails after deployment:**
- Check Azure App Service logs: `az webapp log tail --name {app-name} --resource-group {resource-group}`
- Verify startup command is correct
- Ensure all application secrets are set in App Settings

**Health check fails:**
- The endpoint `/health` may not be implemented
- Temporarily disabled in workflow (continue-on-error: true)
- Implement it in `app.py` to enable full monitoring

### View Logs

Local logs:
```bash
az webapp log tail --name {app-name} --resource-group {resource-group}
```

GitHub Actions logs:
- Repository → Actions → Select workflow run → View logs

## File Structure

```
.github/
  workflows/
    azure-deploy.yml          ← Main deployment workflow
requirements.txt             ← Python dependencies
app.py                       ← FastAPI application entry point
.env.example                 ← Environment variables template
```

## CI/CD Best Practices

1. **Use branch protection**: Require PR reviews before merge to main
2. **Test before merge**: Add pytest to workflow for automated testing
3. **Use environments**: Set production environment secrets separately
4. **Monitor deployments**: Check Azure Application Insights for errors
5. **Backup database**: Configure automated backups for any data stores

## Next Steps

1. Add automated tests to workflow
2. Configure Application Insights monitoring
3. Set up rollback procedure
4. Add deployment notifications (Slack/Teams)
5. Implement blue-green deployments for zero-downtime updates

## Related Documentation

- [Azure App Service Deployment](https://docs.microsoft.com/azure/app-service/deploy-github-actions)
- [GitHub Actions - Azure Login](https://github.com/Azure/login)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/concepts/#deployment-concepts)
- [Gunicorn Configuration](https://gunicorn.org/source/21.2/docs/source/configure.html)
