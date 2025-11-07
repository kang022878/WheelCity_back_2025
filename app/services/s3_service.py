import os
import uuid
from datetime import datetime
from typing import Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
        self.region = os.getenv("AWS_REGION", "us-east-1")
        
        if not self.bucket_name:
            raise ValueError("AWS_S3_BUCKET_NAME environment variable is required")
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=self.region
            )
        except NoCredentialsError:
            raise ValueError("AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
    
    async def upload_image(self, file_content: bytes, filename: str, content_type: str) -> dict:
        """
        Upload image to S3 and return metadata
        """
        try:
            # Generate unique key for the image
            image_id = str(uuid.uuid4())
            file_extension = filename.split('.')[-1] if '.' in filename else 'jpg'
            s3_key = f"images/{image_id}.{file_extension}"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type,
                Metadata={
                    'original_filename': filename,
                    'uploaded_at': datetime.utcnow().isoformat(),
                    'image_id': image_id
                }
            )
            
            # Generate S3 URL
            s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            return {
                "image_id": image_id,
                "s3_key": s3_key,
                "s3_url": s3_url,
                "filename": filename,
                "content_type": content_type,
                "size": len(file_content),
                "uploaded_at": datetime.utcnow()
            }
            
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload image to S3: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    async def get_image_url(self, s3_key: str, expiration: int = 3600) -> str:
        """
        Generate presigned URL for image access
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate image URL")
    
    async def delete_image(self, s3_key: str) -> bool:
        """
        Delete image from S3
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            logger.error(f"Error deleting image from S3: {e}")
            return False
    
    async def check_bucket_exists(self) -> bool:
        """
        Check if the S3 bucket exists and is accessible
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError:
            return False

# Provider (singleton) for dependency injection
_s3_service_instance = None

def get_s3_service() -> "S3Service":
    global _s3_service_instance
    if _s3_service_instance is None:
        _s3_service_instance = S3Service()
    return _s3_service_instance
