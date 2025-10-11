# Wheel City Server - Accessibility Analysis Setup Guide

This guide will help you set up the backend server for automatic accessibility information generation using YOLOV8 and Gemini API.

## 🏗️ System Architecture

The system follows the architecture shown in your diagram:

1. **User uploads review/campaign photos** → FastAPI receives images
2. **Images saved to AWS S3** → boto3 handles S3 uploads
3. **YOLOV8 preprocessing** → Detects entrance regions and accessibility features
4. **Gemini API analysis** → Analyzes accessibility for wheelchair users
5. **Results stored in MongoDB** → Ready for frontend display

## 📋 Prerequisites

- Python 3.8+
- MongoDB instance
- AWS Account with S3 access
- Google Cloud Account with Gemini API access

## 🚀 Quick Setup

### 1. Install Dependencies

```bash
cd wheel_city_server
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the environment template and configure your settings:

```bash
cp env.example .env
```

Edit `.env` with your actual values:

```env
# MongoDB Configuration
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=wheelcity

# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=us-east-1
AWS_S3_BUCKET_NAME=your-bucket-name

# Google Gemini API Configuration
GOOGLE_API_KEY=your_google_api_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TIMEOUT=60.0

# Internal API Key (for internal endpoints)
INTERNAL_API_KEY=your_internal_api_key
```

### 3. AWS S3 Setup

#### Create S3 Bucket:
1. Go to AWS S3 Console
2. Create a new bucket (e.g., `wheelcity-images`)
3. Configure bucket permissions for public read access to uploaded images
4. Note the bucket name for your `.env` file

#### Create IAM User:
1. Go to AWS IAM Console
2. Create a new user (e.g., `wheelcity-s3-user`)
3. Attach policy: `AmazonS3FullAccess` (or create custom policy for your bucket only)
4. Generate access keys and add to `.env`

### 4. Google Gemini API Setup

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Add the key to your `.env` file

### 5. YOLOV8 Model Integration

The YOLOV8 service is set up as a placeholder. To integrate your actual model:

1. Update `app/services/yolov8_service.py`
2. Replace the placeholder code with your YOLOV8 model loading
3. Set `YOLOV8_MODEL_PATH` in your `.env` file

Example integration:
```python
# In yolov8_service.py
from ultralytics import YOLO

def _load_model(self):
    self.model = YOLO(self.model_path)
```

## 🚀 Running the Server

```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 📡 API Endpoints

### Image Upload & Analysis

- `POST /images/upload` - Upload review/campaign photos
- `POST /images/analyze` - Analyze uploaded images for accessibility
- `GET /images/{image_id}` - Get image metadata and analysis results
- `GET /images/` - List uploaded images
- `DELETE /images/{image_id}` - Delete image (internal use)

### Existing Endpoints

- `GET /health/` - Health check
- `GET /places/nearby/` - Find nearby places
- `POST /places/` - Create new place (internal use)

## 🔧 API Usage Examples

### Upload Image
```bash
curl -X POST "http://localhost:8000/images/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@entrance_photo.jpg" \
  -F "place_id=optional_place_id" \
  -F "user_id=optional_user_id"
```

### Analyze Image
```bash
curl -X POST "http://localhost:8000/images/analyze" \
  -H "Content-Type: application/json" \
  -d '{"image_id": "your_image_id", "force_reanalyze": false}'
```

### Get Analysis Results
```bash
curl -X GET "http://localhost:8000/images/your_image_id"
```

## 🗄️ Database Collections

The system uses these MongoDB collections:

- `images` - Image metadata and S3 references
- `image_analyses` - Accessibility analysis results
- `places` - Existing places data (unchanged)

## 🔍 Monitoring & Debugging

### Logs
The application logs important events:
- Image upload success/failures
- S3 operations
- Gemini API calls
- YOLOV8 processing
- Analysis results

### Health Checks
- `GET /health/` - Basic health check
- Check MongoDB connection
- Verify S3 bucket access
- Test Gemini API connectivity

## 🚨 Troubleshooting

### Common Issues

1. **S3 Upload Failures**
   - Check AWS credentials
   - Verify bucket permissions
   - Ensure bucket exists

2. **Gemini API Errors**
   - Verify API key is correct
   - Check quota limits
   - Ensure image format is supported

3. **YOLOV8 Model Issues**
   - Verify model file exists
   - Check model loading code
   - Ensure dependencies are installed

### Environment Variables
Make sure all required environment variables are set:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_S3_BUCKET_NAME`
- `GOOGLE_API_KEY`
- `MONGODB_URL`

## 🔄 Next Steps

1. **Integrate your YOLOV8 model** in `app/services/yolov8_service.py`
2. **Test the complete pipeline** with sample images
3. **Configure production settings** (logging, monitoring, etc.)
4. **Set up monitoring** for API usage and costs
5. **Implement rate limiting** if needed

## 📞 Support

For issues with:
- **AWS S3**: Check AWS documentation and IAM permissions
- **Gemini API**: Check Google AI Studio documentation
- **YOLOV8**: Refer to Ultralytics documentation
- **FastAPI**: Check FastAPI documentation

The system is now ready to receive images, process them with YOLOV8, analyze accessibility with Gemini, and store results in MongoDB for your frontend to display!
