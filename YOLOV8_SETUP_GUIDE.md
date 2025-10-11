# YOLOV8 Setup Guide for Wheel City Server

This guide will help you set up YOLOV8 for your accessibility analysis system.

## 🚀 Quick Setup

### 1. Install Dependencies

```bash
cd wheel_city_server
pip install -r requirements.txt
```

The requirements now include:
- `ultralytics==8.0.196` - YOLOV8 framework
- `torch>=1.8.0` - PyTorch for deep learning
- `torchvision>=0.9.0` - Computer vision utilities

### 2. Environment Configuration

Add these variables to your `.env` file:

```env
# YOLOV8 Configuration
YOLOV8_MODEL_PATH=models/yolov8.pt
YOLOV8_CONFIDENCE=0.5
YOLOV8_DEVICE=cpu
```

### 3. Model Setup Options

#### Option A: Use Default YOLOV8 Model (Recommended for testing)
The system will automatically download `yolov8n.pt` (nano version) if no custom model is found.

#### Option B: Use Your Custom Model
1. Place your trained YOLOV8 model file in the `models/` directory
2. Update `YOLOV8_MODEL_PATH` in your `.env` file
3. The system will use your custom model for inference

#### Option C: Train a Custom Model for Accessibility
If you want to train a model specifically for accessibility features:

```python
from ultralytics import YOLO

# Load a pre-trained model
model = YOLO('yolov8n.pt')

# Train on your accessibility dataset
results = model.train(
    data='path/to/your/accessibility_dataset.yaml',
    epochs=100,
    imgsz=640,
    device='cpu'  # or 'cuda' if you have GPU
)
```

## 🧪 Testing YOLOV8 Integration

### Run the Test Script

```bash
# Basic test
python test_yolov8.py

# Test with a real image
python test_yolov8.py path/to/your/image.jpg
```

### Expected Output

```
🔍 Testing YOLOV8 Service Integration
==================================================

1. Checking YOLOV8 model loading...
✅ YOLOV8 model loaded successfully
   Device: cpu
   Model path: models/yolov8.pt

2. Testing object detection...
   Created test image (640x640 white image)
   Detections found: 0

3. Testing accessibility feature analysis...
   Ramp detected: False
   Stairs detected: False
   Door detected: False
   Entrance detected: False
   Confidence scores: {}

✅ YOLOV8 integration test completed successfully!
```

## 🔧 Configuration Options

### Device Configuration

```env
# For CPU (default, works everywhere)
YOLOV8_DEVICE=cpu

# For GPU (faster inference, requires CUDA)
YOLOV8_DEVICE=cuda

# For Apple Silicon (M1/M2 Macs)
YOLOV8_DEVICE=mps
```

### Confidence Threshold

```env
# Lower = more detections (including false positives)
YOLOV8_CONFIDENCE=0.3

# Higher = fewer detections (more confident results)
YOLOV8_CONFIDENCE=0.7
```

## 🏗️ How It Works

### 1. Image Processing Pipeline

```
Image Upload → YOLOV8 Detection → Feature Analysis → Gemini Analysis
```

### 2. YOLOV8 Detection Process

1. **Image Preprocessing**: Resize and format image for YOLOV8
2. **Object Detection**: Run YOLOV8 inference to detect objects
3. **Feature Analysis**: Identify accessibility-related objects:
   - Ramps and slopes
   - Stairs and steps
   - Doors and entrances
   - Buildings

### 3. Integration with Gemini

- YOLOV8 detects and extracts entrance regions
- Gemini analyzes the entrance region for accessibility
- Results are combined for comprehensive analysis

## 📊 Custom Model Training

### Dataset Preparation

Create a YAML file for your accessibility dataset:

```yaml
# accessibility_dataset.yaml
path: /path/to/your/dataset
train: images/train
val: images/val
test: images/test

# Classes for accessibility analysis
names:
  0: ramp
  1: stairs
  2: door
  3: entrance
  4: building
```

### Training Command

```python
from ultralytics import YOLO

# Load base model
model = YOLO('yolov8n.pt')

# Train on accessibility dataset
results = model.train(
    data='accessibility_dataset.yaml',
    epochs=100,
    imgsz=640,
    batch=16,
    device='cpu'
)
```

## 🚨 Troubleshooting

### Common Issues

1. **Model Loading Errors**
   ```
   Error: Failed to load YOLOV8 model
   ```
   - Check if ultralytics is installed: `pip install ultralytics`
   - Verify PyTorch installation: `python -c "import torch; print(torch.__version__)"`

2. **CUDA/GPU Issues**
   ```
   Error: CUDA not available
   ```
   - Install CUDA version of PyTorch: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118`
   - Or use CPU: `YOLOV8_DEVICE=cpu`

3. **Memory Issues**
   ```
   Error: Out of memory
   ```
   - Use smaller model: `yolov8n.pt` instead of `yolov8l.pt`
   - Reduce image size in preprocessing
   - Use CPU instead of GPU

### Performance Optimization

1. **For Production**
   - Use GPU if available (`YOLOV8_DEVICE=cuda`)
   - Use larger model for better accuracy (`yolov8m.pt` or `yolov8l.pt`)
   - Batch process multiple images

2. **For Development**
   - Use CPU (`YOLOV8_DEVICE=cpu`)
   - Use nano model (`yolov8n.pt`) for faster inference
   - Lower confidence threshold for more detections

## 📈 Monitoring and Logging

The YOLOV8 service includes comprehensive logging:

```python
# Check logs for YOLOV8 operations
import logging
logging.getLogger('app.services.yolov8_service').setLevel(logging.DEBUG)
```

Log messages include:
- Model loading status
- Detection results
- Processing times
- Error messages

## 🔄 Next Steps

1. **Test the integration** with the test script
2. **Train a custom model** for your specific accessibility use case
3. **Optimize performance** for your deployment environment
4. **Monitor results** and adjust confidence thresholds
5. **Integrate with your frontend** to display accessibility information

## 📞 Support

For YOLOV8-specific issues:
- [Ultralytics Documentation](https://docs.ultralytics.com/)
- [YOLOV8 GitHub](https://github.com/ultralytics/ultralytics)
- [PyTorch Documentation](https://pytorch.org/docs/)

Your YOLOV8 integration is now ready to detect accessibility features in building entrances! 🎉
