# Vercel Deployment Guide for Django Backend

## Prerequisites

1. **Vercel Account**: Sign up at [https://vercel.com](https://vercel.com)
2. **Vercel CLI**: Install the Vercel CLI tool
   ```bash
   npm install -g vercel
   ```

## Deployment Steps

### 1. Prepare Your Project

1. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Create a `.vercel` directory** (optional but recommended):
   ```bash
   mkdir -p .vercel
   ```

### 2. Configure Environment Variables

You need to set these environment variables in your Vercel dashboard:

1. **Go to your Vercel project settings**
2. **Navigate to "Environment Variables"**
3. **Add the following variables:**

| Variable Name | Description | Example Value |
|--------------|-------------|---------------|
| `DEBUG` | Django debug mode | `False` |
| `ALLOWED_HOSTS` | Allowed host names | `your-app-name.vercel.app,localhost` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgres://username:password@host:port/database` |
| `SECRET_KEY` | Django secret key | `your-strong-secret-key-here` |
| `CORS_ALLOWED_ORIGINS` | Allowed CORS origins | `https://your-app-name.vercel.app,http://localhost:5173,http://localhost:3000` |
| `DJANGO_SETTINGS_MODULE` | Django settings module | `config.settings` |

**Important:** For production, generate a strong secret key and use a secure database connection string.

### 3. Database Configuration

For production, you should use a managed PostgreSQL database. Some options:

1. **Vercel Postgres**: Use Vercel's built-in PostgreSQL database
2. **External PostgreSQL**: Use services like AWS RDS, Aiven, or Neon

Update your `backend/config/settings.py` to use the database URL:

```python
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default='postgres://...',
        conn_max_age=600,
        ssl_require=True
    )
}
```

### 4. Static and Media Files

Vercel has limitations with file uploads. For media files:

1. **Use cloud storage**: AWS S3, Google Cloud Storage, or Cloudinary
2. **Update settings**:
   ```python
   # Use AWS S3 example
   DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
   AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
   AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
   AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
   ```

### 5. Deploy to Vercel

1. **Install Vercel CLI and login**:
   ```bash
   npm install -g vercel
   vercel login
   ```

2. **Deploy your project**:
   ```bash
   cd backend
   vercel
   ```

3. **Follow the prompts** to configure your project.

### 6. Post-Deployment Setup

1. **Run migrations**:
   ```bash
   vercel env pull
   python manage.py migrate
   ```

2. **Create superuser** (if needed):
   ```bash
   python manage.py createsuperuser
   ```

## Important Notes

1. **Serverless Limitations**: Vercel has execution time limits (10s for free tier). For long-running tasks, consider:
   - Using Vercel's serverless functions with increased timeout
   - Moving heavy processing to background workers

2. **File Storage**: Vercel's serverless functions are ephemeral. Don't rely on local file storage.

3. **WebSockets**: If you need WebSocket support, you'll need to use a different hosting solution or Vercel's edge functions.

## Troubleshooting

1. **Cold starts**: First requests may be slow due to serverless nature
2. **Timeout errors**: Optimize your Django views or increase timeout settings
3. **Database connections**: Use connection pooling for better performance

## Alternative Deployment Options

If Vercel doesn't meet your needs, consider:
- **Railway.app**
- **Render.com**
- **AWS Elastic Beanstalk**
- **Google App Engine**
- **DigitalOcean App Platform**
