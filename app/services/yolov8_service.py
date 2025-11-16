import os
import io
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image
import logging
import numpy as np

# Load .env file BEFORE importing anything that might use environment variables
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
print(f"[YOLOV8] Loaded .env from: {env_path}", flush=True)

# Monkey-patch torch.load to disable weights_only for YOLOv8 models
# This is needed because PyTorch 2.6+ defaults to weights_only=True
import torch
_original_torch_load = torch.load

def _patched_torch_load(*args, **kwargs):
    """Patched torch.load that always uses weights_only=False for model files."""
    # If weights_only is not explicitly set, default to False for model files
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)

# Apply the patch
torch.load = _patched_torch_load
print(f"[YOLOV8] ✅ Patched torch.load to use weights_only=False", flush=True)

# Check if ultralytics is available
try:
    from ultralytics import YOLO
    from torch.serialization import add_safe_globals
    import ultralytics.nn.tasks as ul_tasks
    YOLO_AVAILABLE = True
    print(f"[YOLOV8] ✅ ultralytics imported successfully", flush=True)
except ImportError as e:
    print(f"[YOLOV8] ❌ CRITICAL: Cannot import ultralytics: {e}", flush=True)
    print(f"[YOLOV8] Please install: pip install ultralytics", flush=True)
    YOLO_AVAILABLE = False
    YOLO = None
    add_safe_globals = None
    ul_tasks = None

logger = logging.getLogger(__name__)

class YOLOV8Service:
    """
    YOLOV8 service for image preprocessing and object detection
    This is a placeholder implementation - you'll need to integrate your actual YOLOV8 model
    """
    
    def __init__(self):
        print(f"[YOLOV8] Initializing YOLOV8Service...", flush=True)
        # Get the project root directory (wheel_city_server)
        # This file is at: wheel_city_server/app/services/yolov8_service.py
        # So project root is 2 levels up
        self.project_root = Path(__file__).parent.parent.parent
        print(f"[YOLOV8] Project root: {self.project_root}", flush=True)
        
        # Try to get model path from env, or use default locations
        env_model_path = os.getenv("YOLOV8_MODEL_PATH")
        print(f"[YOLOV8] YOLOV8_MODEL_PATH from env: {env_model_path}", flush=True)
        if env_model_path:
            self.model_path = Path(env_model_path)
            if not self.model_path.is_absolute():
                self.model_path = self.project_root / self.model_path
            print(f"[YOLOV8] Using model path from env: {self.model_path}", flush=True)
            print(f"[YOLOV8] Resolved path exists: {self.model_path.exists()}", flush=True)
        else:
            # Try common locations - check project root first (most likely location)
            possible_paths = [
                self.project_root / "yolov8n.pt",  # Most common - check first
                self.project_root / "yolov8.pt",
                self.project_root / "models" / "yolov8n.pt",
                self.project_root / "models" / "yolov8.pt",
            ]
            self.model_path = None
            for path in possible_paths:
                path_str = str(path)
                exists = path.exists()
                print(f"[YOLOV8] Checking path: {path_str} (exists: {exists})", flush=True)
                if exists:
                    self.model_path = path
                    print(f"[YOLOV8] ✅ Found model at: {self.model_path}", flush=True)
                    break
            
            if not self.model_path:
                print(f"[YOLOV8] ⚠️  No model file found in common locations", flush=True)
                print(f"[YOLOV8] Will try to download from Ultralytics or use default", flush=True)
        
        self.confidence_threshold = float(os.getenv("YOLOV8_CONFIDENCE", "0.5"))
        self.device = os.getenv("YOLOV8_DEVICE", "cpu")  # cpu, cuda, mps
        self.model = None
        print(f"[YOLOV8] About to load model...", flush=True)
        print(f"[YOLOV8] Model path before load: {self.model_path}", flush=True)
        print(f"[YOLOV8] Project root: {self.project_root}", flush=True)
        try:
            self._load_model()
        except Exception as e:
            print(f"[YOLOV8] CRITICAL ERROR during model loading: {e}", flush=True)
            import traceback
            print(f"[YOLOV8] Traceback:\n{traceback.format_exc()}", flush=True)
            raise
        print(f"[YOLOV8] Model load complete. Model is None: {self.model is None}", flush=True)
        if self.model is None:
            print(f"[YOLOV8] ⚠️⚠️⚠️ WARNING: Model failed to load! This will cause empty detections!", flush=True)
    
    def _load_model(self):
        """
        Load YOLOV8 model
        """
        if not YOLO_AVAILABLE:
            logger.error("YOLO is not available - ultralytics package not installed")
            print(f"[YOLOV8] ❌ Cannot load model: ultralytics package not available", flush=True)
            self.model = None
            return
        
        try:
            # Allowlist required classes for torch.load under PyTorch 2.6+
            # PyTorch 2.6+ requires explicit allowlisting of classes used in model files
            try:
                import torch.nn.modules.container
                import torch.nn.modules.conv
                import torch.nn.modules.batchnorm
                import torch.nn.modules.activation
                import ultralytics.nn.modules
                
                if add_safe_globals and ul_tasks:
                    # Add all required classes for YOLOv8 model loading
                    safe_classes = [
                        ul_tasks.DetectionModel,
                        torch.nn.modules.container.Sequential,
                        torch.nn.modules.conv.Conv2d,
                        torch.nn.modules.batchnorm.BatchNorm2d,
                        torch.nn.modules.activation.SiLU,
                    ]
                    
                    # Add all ultralytics.nn.modules classes dynamically
                    try:
                        for attr_name in dir(ultralytics.nn.modules):
                            if not attr_name.startswith('_'):
                                attr = getattr(ultralytics.nn.modules, attr_name)
                                if isinstance(attr, type):  # Only add classes
                                    safe_classes.append(attr)
                        print(f"[YOLOV8] Found {len([c for c in safe_classes if hasattr(c, '__module__') and 'ultralytics' in str(c.__module__)])} ultralytics module classes", flush=True)
                    except Exception as e:
                        print(f"[YOLOV8] Warning: Could not auto-detect ultralytics modules: {e}", flush=True)
                        # Fallback: add known classes manually
                        try:
                            safe_classes.extend([
                                ultralytics.nn.modules.Conv,
                                ultralytics.nn.modules.Bottleneck,
                                ultralytics.nn.modules.C2f,
                                ultralytics.nn.modules.SPPF,
                            ])
                        except AttributeError:
                            pass
                    
                    add_safe_globals(safe_classes)
                    print(f"[YOLOV8] ✅ Added {len(safe_classes)} safe globals for PyTorch 2.6+", flush=True)
                # Also set environment variable as fallback (disable weights_only mode)
                # This is the most reliable way to handle PyTorch 2.6+ compatibility
                os.environ["TORCH_LOAD_WEIGHTS_ONLY"] = "0"
                print(f"[YOLOV8] Set TORCH_LOAD_WEIGHTS_ONLY=0", flush=True)
            except Exception as e:
                print(f"[YOLOV8] Warning: Could not set safe globals: {e}", flush=True)
                print(f"[YOLOV8] Will try to set TORCH_LOAD_WEIGHTS_ONLY=0", flush=True)
                # Fallback: disable weights_only mode
                os.environ["TORCH_LOAD_WEIGHTS_ONLY"] = "0"
                pass
            
            # Always try project root first (most reliable location)
            model_loaded = False
            default_model = self.project_root / "yolov8n.pt"
            default_model_str = str(default_model)
            default_model_exists = default_model.exists()
            print(f"[YOLOV8] First checking project root: {default_model_str}", flush=True)
            print(f"[YOLOV8] File exists: {default_model_exists}", flush=True)
            if default_model_exists:
                logger.info(f"Loading YOLOV8 model from: {default_model}")
                print(f"[YOLOV8] ✅ File exists! Attempting to load from: {default_model}", flush=True)
                print(f"[YOLOV8] Full path: {default_model.absolute()}", flush=True)
                try:
                    print(f"[YOLOV8] Calling YOLO('{str(default_model)}')...", flush=True)
                    self.model = YOLO(str(default_model))
                    print(f"[YOLOV8] YOLO() call succeeded! Model object: {type(self.model)}", flush=True)
                    model_loaded = True
                    print(f"[YOLOV8] ✅ Successfully loaded model from project root!", flush=True)
                except ImportError as import_error:
                    logger.error(f"Import error loading YOLO model: {import_error}")
                    print(f"[YOLOV8] ❌ IMPORT ERROR: {import_error}", flush=True)
                    print(f"[YOLOV8] Make sure ultralytics is installed: pip install ultralytics", flush=True)
                    import traceback
                    print(f"[YOLOV8] Traceback:\n{traceback.format_exc()}", flush=True)
                except FileNotFoundError as file_error:
                    logger.error(f"File not found: {file_error}")
                    print(f"[YOLOV8] ❌ FILE NOT FOUND: {file_error}", flush=True)
                    import traceback
                    print(f"[YOLOV8] Traceback:\n{traceback.format_exc()}", flush=True)
                except Exception as load_error:
                    logger.error(f"Failed to load model from {default_model}: {load_error}")
                    print(f"[YOLOV8] ❌ FAILED TO LOAD: {type(load_error).__name__}: {load_error}", flush=True)
                    import traceback
                    print(f"[YOLOV8] Full traceback:\n{traceback.format_exc()}", flush=True)
            
            # If not loaded, try the configured model_path (if different from default)
            if not model_loaded and self.model_path and self.model_path != default_model:
                print(f"[YOLOV8] Trying configured path: {self.model_path} (exists: {self.model_path.exists()})", flush=True)
                if self.model_path.exists():
                    logger.info(f"Loading YOLOV8 model from: {self.model_path}")
                    print(f"[YOLOV8] Loading from configured path: {self.model_path}", flush=True)
                    try:
                        self.model = YOLO(str(self.model_path))
                        model_loaded = True
                        print(f"[YOLOV8] ✅ Successfully loaded model from configured path!", flush=True)
                    except Exception as load_error:
                        logger.error(f"Failed to load model from {self.model_path}: {load_error}")
                        print(f"[YOLOV8] ❌ Failed to load from {self.model_path}: {load_error}", flush=True)
            
            # If still not loaded, fall back to downloading from Ultralytics
            if not model_loaded:
                logger.warning(f"YOLOV8 model not found at {self.model_path or 'default locations'}. Downloading yolov8n.pt from Ultralytics.")
                print(f"[YOLOV8] ⚠️ Model not found locally, attempting to download from Ultralytics...", flush=True)
                try:
                    self.model = YOLO('yolov8n.pt')  # This will download if not found
                    model_loaded = True
                    print(f"[YOLOV8] ✅ Successfully downloaded and loaded model from Ultralytics!", flush=True)
                except Exception as download_error:
                    logger.error(f"Failed to download model: {download_error}")
                    print(f"[YOLOV8] ❌ CRITICAL: Failed to download model: {download_error}", flush=True)
                    import traceback
                    print(f"[YOLOV8] Traceback:\n{traceback.format_exc()}", flush=True)
                    # Don't raise - let it be None so we can see the error
                    self.model = None
            
            # Move model to specified device (only if model was loaded)
            if self.model is not None:
                self.model.to(self.device)
                logger.info(f"✅ YOLOV8 model loaded successfully on {self.device}")
                print(f"[YOLOV8] ✅ Model loaded successfully on {self.device}", flush=True)
            else:
                logger.error("❌ YOLOV8 model is None after all loading attempts!")
                print(f"[YOLOV8] ❌ Model is None after all loading attempts!", flush=True)
            
        except Exception as e:
            logger.error(f"Failed to load YOLOV8 model: {e}")
            print(f"[YOLOV8 ERROR] Failed to load model: {e}", flush=True)
            import traceback
            logger.error(traceback.format_exc())
            print(f"[YOLOV8 ERROR] Traceback:\n{traceback.format_exc()}", flush=True)
            
            logger.info("Falling back to default YOLOV8 model")
            try:
                self.model = YOLO('yolov8n.pt')
                self.model.to(self.device)
                logger.info("Default YOLOV8 model loaded successfully")
                print(f"[YOLOV8] Default model loaded successfully", flush=True)
            except Exception as fallback_error:
                logger.error(f"Failed to load default YOLOV8 model: {fallback_error}")
                print(f"[YOLOV8 ERROR] Failed to load default model: {fallback_error}", flush=True)
                import traceback
                logger.error(traceback.format_exc())
                self.model = None
    
    async def preprocess_image(self, image_bytes: bytes) -> bytes:
        """
        Preprocess image for YOLOV8 analysis
        """
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_bytes))
            
            # Resize if needed (YOLOV8 typically expects specific input sizes)
            # Example: image = image.resize((640, 640))
            
            # Convert back to bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            return img_byte_arr.getvalue()
            
        except Exception as e:
            logger.error(f"Image preprocessing error: {e}")
            return image_bytes  # Return original if preprocessing fails
    
    async def detect_objects(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Detect objects in image using YOLOV8
        """
        try:
            if not self.model:
                logger.warning("YOLOV8 model not loaded, returning empty detections")
                print(f"[YOLOV8] ERROR: Model is None when detect_objects called!", flush=True)
                print(f"[YOLOV8] Project root: {self.project_root}", flush=True)
                print(f"[YOLOV8] Model path: {self.model_path}", flush=True)
                print(f"[YOLOV8] Device: {self.device}", flush=True)
                return []
            
            # Save image bytes to temporary file for YOLOV8 processing
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_file.write(image_bytes)
                temp_path = temp_file.name
            
            try:
                # Run YOLOV8 inference
                results = self.model(temp_path, conf=self.confidence_threshold)
                
                detections = []
                for result in results:
                    if result.boxes is not None:
                        for box in result.boxes:
                            # Get class name from model
                            class_id = int(box.cls.item())
                            class_name = self.model.names[class_id]
                            confidence = float(box.conf.item())
                            
                            # Get bounding box coordinates
                            bbox = box.xyxy.tolist()[0]  # [x1, y1, x2, y2]
                            
                            detections.append({
                                "class_id": class_id,
                                "class": class_name,
                                "confidence": confidence,
                                "bbox": bbox,
                                "description": f"{class_name} detected with {confidence:.2f} confidence"
                            })
                
                return detections
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"YOLOV8 detection error: {e}")
            return []
    
    async def extract_entrance_region(self, image_bytes: bytes, detections: List[Dict[str, Any]]) -> Optional[bytes]:
        """
        Extract entrance region from image based on YOLOV8 detections
        """
        try:
            if not detections:
                return None
            
            # Find the most confident entrance detection
            entrance_detection = max(detections, key=lambda x: x.get("confidence", 0))
            
            # Load image
            image = Image.open(io.BytesIO(image_bytes))
            
            # Extract bounding box coordinates
            bbox = entrance_detection["bbox"]
            x1, y1, x2, y2 = map(int, bbox)
            
            # Crop image to entrance region
            cropped_image = image.crop((x1, y1, x2, y2))
            
            # Convert back to bytes
            img_byte_arr = io.BytesIO()
            cropped_image.save(img_byte_arr, format='JPEG')
            return img_byte_arr.getvalue()
            
        except Exception as e:
            logger.error(f"Entrance region extraction error: {e}")
            return None
    
    async def analyze_accessibility_features(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Analyze image for accessibility features using YOLOV8
        This method should detect ramps, stairs, doors, etc.
        """
        try:
            # Preprocess image
            processed_image = await self.preprocess_image(image_bytes)
            
            # Detect objects
            detections = await self.detect_objects(processed_image)
            
            # Analyze accessibility features
            accessibility_features = {
                "ramp_detected": False,
                "stairs_detected": False,
                "door_detected": False,
                "entrance_detected": False,
                "confidence_scores": {},
                "detections": detections
            }
            
            # Process detections to identify accessibility features
            for detection in detections:
                class_name = detection.get("class", "").lower()
                confidence = detection.get("confidence", 0)
                
                # Check for accessibility-related objects
                if any(keyword in class_name for keyword in ["ramp", "slope", "incline"]):
                    accessibility_features["ramp_detected"] = True
                    accessibility_features["confidence_scores"]["ramp"] = confidence
                elif any(keyword in class_name for keyword in ["stair", "step", "stairs", "steps"]):
                    accessibility_features["stairs_detected"] = True
                    accessibility_features["confidence_scores"]["stairs"] = confidence
                elif any(keyword in class_name for keyword in ["door", "entrance", "entry"]):
                    accessibility_features["door_detected"] = True
                    accessibility_features["confidence_scores"]["door"] = confidence
                    if "entrance" in class_name or "entry" in class_name:
                        accessibility_features["entrance_detected"] = True
                        accessibility_features["confidence_scores"]["entrance"] = confidence
                
                # Also check for general building/entrance objects
                if any(keyword in class_name for keyword in ["building", "house", "entrance", "door"]):
                    if not accessibility_features["entrance_detected"]:
                        accessibility_features["entrance_detected"] = True
                        accessibility_features["confidence_scores"]["entrance"] = confidence
            
            return accessibility_features
            
        except Exception as e:
            logger.error(f"Accessibility feature analysis error: {e}")
            return {
                "ramp_detected": False,
                "stairs_detected": False,
                "door_detected": False,
                "entrance_detected": False,
                "confidence_scores": {},
                "detections": [],
                "error": str(e)
            }

# Global instance
yolov8_service = YOLOV8Service()

