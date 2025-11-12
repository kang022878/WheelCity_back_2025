import os
import io
import tempfile
from typing import List, Dict, Any, Optional
from PIL import Image
import logging
import numpy as np
from ultralytics import YOLO
from torch.serialization import add_safe_globals
import ultralytics.nn.tasks as ul_tasks

logger = logging.getLogger(__name__)

class YOLOV8Service:
    """
    YOLOV8 service for image preprocessing and object detection
    This is a placeholder implementation - you'll need to integrate your actual YOLOV8 model
    """
    
    def __init__(self):
        self.model_path = os.getenv("YOLOV8_MODEL_PATH", "models/yolov8.pt")
        self.confidence_threshold = float(os.getenv("YOLOV8_CONFIDENCE", "0.5"))
        self.device = os.getenv("YOLOV8_DEVICE", "cpu")  # cpu, cuda, mps
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """
        Load YOLOV8 model
        """
        try:
            # Allowlist Ultralytics DetectionModel for torch.load under PyTorch 2.6+
            try:
                add_safe_globals([ul_tasks.DetectionModel])
                os.environ.setdefault("TORCH_LOAD_WEIGHTS_ONLY", "0")
            except Exception:
                pass
            if not os.path.exists(self.model_path):
                logger.warning(f"YOLOV8 model not found at {self.model_path}. Using default model.")
                # Use a default YOLOV8 model if custom model not found
                self.model = YOLO('yolov8n.pt')  # nano version for faster inference
            else:
                self.model = YOLO(self.model_path)
            
            # Move model to specified device
            self.model.to(self.device)
            logger.info(f"YOLOV8 model loaded successfully on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to load YOLOV8 model: {e}")
            logger.info("Falling back to default YOLOV8 model")
            try:
                self.model = YOLO('yolov8n.pt')
                self.model.to(self.device)
                logger.info("Default YOLOV8 model loaded successfully")
            except Exception as fallback_error:
                logger.error(f"Failed to load default YOLOV8 model: {fallback_error}")
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

