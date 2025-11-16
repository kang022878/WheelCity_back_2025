"""
Test script for image upload and AI evaluation flow.
Run this from the wheel_city_server directory.
"""
import requests
import json
import os
import mimetypes
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

BASE_URL = "http://127.0.0.1:8000"
API_KEY = os.getenv("API_KEY_INTERNAL", "dev-secret-key")  # From your .env file - must match server's API_KEY_INTERNAL

# Configuration - using list so it can be updated
SHOP_ID = ["6918a6ad751293593985e6ca"]  # Replace with your shop ID, or use create_shop() to create a new one
USER_ID = "6918a6ac751293593985e6c9"  # Replace with your user ID

def create_shop():
    """Create a new shop without AI prediction"""
    print("\n=== Creating Shop Without AI Prediction ===")
    if not API_KEY:
        print("❌ API_KEY_INTERNAL not found in .env file!")
        print("   Please add API_KEY_INTERNAL=your-key to your .env file")
        return None
    
    print(f"Using API Key from .env: {API_KEY[:10] if len(API_KEY) > 10 else API_KEY}...")  # Show first 10 chars for verification
    url = f"{BASE_URL}/shops/"
    payload = {
        "name": "Test Shop for AI Evaluation",
        "location": {
            "type": "Point",
            "coordinates": [126.9779451, 37.5662952]  # Seoul coordinates
        }
        # ai_prediction is optional - we're omitting it
    }
    
    headers = {
        "X-API-Key": API_KEY,  # This header name matches the alias in deps.py
        "Content-Type": "application/json"
    }
    
    print(f"Sending request with header X-API-Key: {API_KEY[:10]}...", flush=True)
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        shop = response.json()
        shop_id = shop.get("_id")
        print(f"✅ Shop created successfully!")
        print(f"   Shop ID: {shop_id}")
        print(f"   Name: {shop.get('name')}")
        print(f"   AI Prediction: {shop.get('ai_prediction', 'None')}")
        return shop_id
    else:
        print(f"❌ Error: {response.text}")
        return None

def test_upload_urls():
    """Step 1: Get S3 upload URLs"""
    print("\n=== Step 1: Getting S3 Upload URLs ===")
    s3_bucket = os.getenv("S3_BUCKET_NAME")
    if not s3_bucket:
        print("⚠️  S3_BUCKET_NAME not configured in .env file")
        print("   S3 upload URLs won't work without this.")
        print("   You can still test with existing image URLs.")
        print("   Add S3_BUCKET_NAME=your-bucket-name to your .env file")
        return None, None
    
    url = f"{BASE_URL}/reviews/{SHOP_ID[0]}/upload-urls"
    payload = {
        "files": ["test_image.jpg"]
    }
    
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Upload URL: {data['upload_urls'][0]['upload_url'][:100]}...")
        print(f"Public URL: {data['public_urls'][0]}")
        return data['upload_urls'][0]['upload_url'], data['public_urls'][0]
    else:
        print(f"Error: {response.text}")
        return None, None

def upload_to_s3(upload_url, image_path):
    """Step 2: Upload image to S3"""
    print("\n=== Step 2: Uploading Image to S3 ===")
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        # Determine content type from file extension
        content_type, _ = mimetypes.guess_type(image_path)
        if not content_type:
            # Fallback based on extension
            ext = os.path.splitext(image_path)[1].lower()
            content_type_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            content_type = content_type_map.get(ext, "image/jpeg")
        
        print(f"Uploading {len(image_data)} bytes to S3...")
        print(f"Content-Type: {content_type}")
        print(f"Upload URL: {upload_url[:100]}...")
        response = requests.put(upload_url, data=image_data, headers={"Content-Type": content_type})
        print(f"Status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        if response.status_code in [200, 204]:
            print("✅ Image uploaded successfully!")
            print(f"   Uploaded {len(image_data)} bytes")
            return True
        else:
            print(f"❌ Upload failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except FileNotFoundError:
        print(f"❌ Image file not found: {image_path}")
        print("   Please provide a valid image path or skip this step")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_initial_ai_evaluation(public_url):
    """Step 3: Test initial AI evaluation"""
    print("\n=== Step 3: Testing Initial AI Evaluation ===")
    url = f"{BASE_URL}/reviews/{SHOP_ID[0]}"
    payload = {
        "user_id": USER_ID,
        "enter": True,
        "alone": False,
        "comfort": True,
        "ai_correct": {
            "ramp": True,
            "curb": False
        },
        "photo_urls": [public_url],
        "review_text": "Test review with image for initial AI evaluation"
    }
    
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Review submitted successfully!")
        print("   Check server logs for [REVIEW] Initial AI evaluation messages")
        return True
    else:
        print(f"❌ Error: {response.text}")
        return False

def check_shop_ai_prediction():
    """Check shop's AI prediction"""
    print("\n=== Checking Shop AI Prediction ===")
    url = f"{BASE_URL}/shops/{SHOP_ID[0]}"
    response = requests.get(url)
    if response.status_code == 200:
        shop = response.json()
        ai_pred = shop.get("ai_prediction")
        if ai_pred:
            print(f"✅ Shop has AI prediction: ramp={ai_pred.get('ramp')}, curb={ai_pred.get('curb')}")
            return ai_pred
        else:
            print("⚠️  Shop has no AI prediction yet")
            return None
    else:
        print(f"❌ Error: {response.text}")
        return None

def test_reevaluation(public_url):
    """Step 4: Test reevaluation with 3 disagreeing reviews"""
    print("\n=== Step 4: Testing Reevaluation ===")
    
    # Get current AI prediction
    ai_pred = check_shop_ai_prediction()
    if not ai_pred:
        print("❌ Shop needs an AI prediction first. Run Step 3.")
        return
    
    # Create disagreeing reviews
    disagreeing_ai_correct = {
        "ramp": not ai_pred.get("ramp", False),  # Opposite of AI
        "curb": not ai_pred.get("curb", False)   # Opposite of AI
    }
    
    print(f"AI says: ramp={ai_pred.get('ramp')}, curb={ai_pred.get('curb')}")
    print(f"Submitting reviews with: ramp={disagreeing_ai_correct['ramp']}, curb={disagreeing_ai_correct['curb']}")
    
    # Submit 3 reviews (using the same user_id - reevaluation checks for 3 disagreeing reviews, not different users)
    for i in range(1, 4):
        print(f"\nSubmitting review {i}/3...")
        url = f"{BASE_URL}/reviews/{SHOP_ID[0]}"
        payload = {
            "user_id": USER_ID,  # Use the same user_id (valid ObjectId)
            "enter": True,
            "alone": False,
            "comfort": True,
            "ai_correct": disagreeing_ai_correct,
            "photo_urls": [public_url],
            "review_text": f"Disagreeing review {i}"
        }
        
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"✅ Review {i} submitted")
        else:
            print(f"❌ Review {i} failed: {response.text}")
    
    print("\n✅ All 3 reviews submitted!")
    print("   Check server logs for [REEVAL] messages")
    print("   Wait a moment, then check the shop's AI prediction again")

if __name__ == "__main__":
    print("🧪 Testing Image Upload and AI Evaluation Flow")
    print("=" * 50)
    
    # Option to create a new shop
    create_new = input("Create a new shop without AI prediction? (y/n): ").strip().lower()
    if create_new == 'y':
        new_shop_id = create_shop()
        if new_shop_id:
            SHOP_ID[0] = new_shop_id  # Update the shop ID for this run
            print(f"\n✅ Using new shop ID: {SHOP_ID[0]}")
        else:
            print("\n⚠️  Failed to create shop. Using existing SHOP_ID.")
    
    # Step 1: Get upload URLs
    upload_url, public_url = test_upload_urls()
    if not upload_url:
        print("\n❌ Failed to get upload URLs. Check your shop ID and server.")
        exit(1)
    
    # Step 2: Upload image (optional - you can skip if you already have an image URL)
    image_path = input("\nEnter path to image file (or press Enter to skip): ").strip()
    if image_path:
        upload_to_s3(upload_url, image_path)
    else:
        print("⏭️  Skipping upload. Using provided public_url.")
        # If you already have an image in S3, you can use that URL instead
        use_existing = input("Do you have an existing S3 image URL? (y/n): ").strip().lower()
        if use_existing == 'y':
            public_url = input("Enter the S3 public URL: ").strip()
        else:
            print("⚠️  You need an image URL to continue. Please upload an image first.")
            exit(1)
    
    # Step 3: Test initial AI evaluation
    test_initial_ai_evaluation(public_url)
    
    # Wait a bit for AI processing
    input("\nPress Enter after checking server logs for initial AI evaluation...")
    
    # Check shop AI prediction
    check_shop_ai_prediction()
    
    # Step 4: Test reevaluation
    proceed = input("\nProceed with reevaluation test? (y/n): ").strip().lower()
    if proceed == 'y':
        test_reevaluation(public_url)
        input("\nPress Enter after checking server logs for reevaluation...")
        check_shop_ai_prediction()
    
    print("\n✅ Testing complete! Check server logs for detailed information.")

