#!/usr/bin/env python3
"""
Test script for YOLOV8 integration
Run this to test if YOLOV8 is working correctly
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent / "app"))

from app.services.yolov8_service import yolov8_service
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_yolov8():
    """Test YOLOV8 service functionality"""
    
    print("🔍 Testing YOLOV8 Service Integration")
    print("=" * 50)
    
    # Test 1: Check if model loaded
    print("\n1. Checking YOLOV8 model loading...")
    if yolov8_service.model is not None:
        print("✅ YOLOV8 model loaded successfully")
        print(f"   Device: {yolov8_service.device}")
        print(f"   Model path: {yolov8_service.model_path}")
    else:
        print("❌ YOLOV8 model failed to load")
        return False
    
    # Test 2: Test with a sample image (if available)
    print("\n2. Testing object detection...")
    
    # Create a simple test image
    try:
        from PIL import Image
        import io
        
        # Create a simple test image
        test_image = Image.new('RGB', (640, 640), color='white')
        img_byte_arr = io.BytesIO()
        test_image.save(img_byte_arr, format='JPEG')
        test_image_bytes = img_byte_arr.getvalue()
        
        print("   Created test image (640x640 white image)")
        
        # Test object detection
        detections = await yolov8_service.detect_objects(test_image_bytes)
        print(f"   Detections found: {len(detections)}")
        
        for i, detection in enumerate(detections):
            print(f"   Detection {i+1}: {detection['class']} (confidence: {detection['confidence']:.2f})")
        
        # Test accessibility feature analysis
        print("\n3. Testing accessibility feature analysis...")
        features = await yolov8_service.analyze_accessibility_features(test_image_bytes)
        
        print(f"   Ramp detected: {features['ramp_detected']}")
        print(f"   Stairs detected: {features['stairs_detected']}")
        print(f"   Door detected: {features['door_detected']}")
        print(f"   Entrance detected: {features['entrance_detected']}")
        print(f"   Confidence scores: {features['confidence_scores']}")
        
        print("\n✅ YOLOV8 integration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

async def test_with_real_image(image_path: str):
    """Test with a real image file"""
    if not os.path.exists(image_path):
        print(f"❌ Image file not found: {image_path}")
        return False
    
    print(f"\n🖼️  Testing with real image: {image_path}")
    
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        # Test object detection
        detections = await yolov8_service.detect_objects(image_bytes)
        print(f"   Detections found: {len(detections)}")
        
        for i, detection in enumerate(detections):
            print(f"   Detection {i+1}: {detection['class']} (confidence: {detection['confidence']:.2f})")
            print(f"   Bounding box: {detection['bbox']}")
        
        # Test accessibility features
        features = await yolov8_service.analyze_accessibility_features(image_bytes)
        print(f"\n   Accessibility Analysis:")
        print(f"   - Ramp detected: {features['ramp_detected']}")
        print(f"   - Stairs detected: {features['stairs_detected']}")
        print(f"   - Door detected: {features['door_detected']}")
        print(f"   - Entrance detected: {features['entrance_detected']}")
        
        if features['confidence_scores']:
            print(f"   - Confidence scores: {features['confidence_scores']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing with real image: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 YOLOV8 Integration Test")
    print("=" * 50)
    
    # Run basic test
    success = asyncio.run(test_yolov8())
    
    if not success:
        print("\n❌ Basic test failed. Please check your YOLOV8 setup.")
        return
    
    # Test with real image if provided
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"\n📸 Testing with provided image: {image_path}")
        asyncio.run(test_with_real_image(image_path))
    else:
        print("\n💡 To test with a real image, run:")
        print("   python test_yolov8.py path/to/your/image.jpg")
    
    print("\n🎉 YOLOV8 integration is ready to use!")

if __name__ == "__main__":
    main()
