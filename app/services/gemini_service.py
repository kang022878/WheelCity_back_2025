import os
import json
import re
import time
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import google.generativeai as genai
from fastapi import HTTPException
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.timeout = float(os.getenv("GEMINI_TIMEOUT", "60.0"))
        
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        genai.configure(api_key=self.api_key)
        
        # System prompt for accessibility analysis
        self.system_prompt = (
            "You are an accessibility analysis AI. Analyze the provided image of a building entrance to determine if it is accessible for a lone wheelchair user.\n"
            "Accessibility Rules:\n"
            "1. There must be no steps or curbs between the ground and the entrance.\n"
            "2. If there are steps or curbs, a ramp must connect the ground to the entrance.\n\n"
            "Return ONLY valid JSON. Do not include any explanations, Markdown, or code fences.\n"
            'JSON schema: {"accessible": boolean | null, "reason": string}\n'
        )
        
        # MIME type mapping
        self.mime_by_ext = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg", 
            ".png": "image/png",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        
        # Initialize model
        try:
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.2,
                }
            )
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            raise ValueError(f"Failed to initialize Gemini model: {str(e)}")
    
    def _guess_mime_type(self, filename: str) -> Optional[str]:
        """Guess MIME type from file extension"""
        ext = os.path.splitext(filename)[1].lower()
        return self.mime_by_ext.get(ext)
    
    def _extract_json_from_response(self, text: str) -> Optional[str]:
        """Extract JSON from model response using regex patterns"""
        if not text:
            return None
        
        # Pattern 1: ```json ... ``` blocks
        json_block_pattern = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
        match = json_block_pattern.search(text)
        if match:
            return match.group(1).strip()
        
        # Pattern 2: Find first { and last } 
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace:last_brace+1].strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                return candidate
        
        # Pattern 3: Any {...} block
        brace_pattern = re.compile(r"\{.*\}", re.DOTALL)
        match = brace_pattern.search(text)
        if match:
            return match.group(0).strip()
        
        return None
    
    def _safe_json_parse(self, text: str) -> Dict[str, Any]:
        """Safely parse JSON from model response with fallbacks"""
        # Try direct parsing first
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return self._validate_analysis_result(obj)
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from response
        extracted = self._extract_json_from_response(text)
        if extracted:
            try:
                obj = json.loads(extracted)
                if isinstance(obj, dict):
                    return self._validate_analysis_result(obj)
            except json.JSONDecodeError:
                pass
        
        # Fallback for parse errors
        return {
            "accessible": None,
            "reason": "Parse error: model did not return valid JSON."
        }
    
    def _validate_analysis_result(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean analysis result"""
        accessible = obj.get("accessible")
        if accessible not in (True, False, None):
            accessible = None
        
        reason = obj.get("reason", "No reason provided.")
        if not isinstance(reason, str):
            reason = str(reason)
        
        return {
            "accessible": accessible,
            "reason": reason
        }
    
    async def analyze_accessibility(self, image_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Analyze image for accessibility using Gemini API
        """
        start_time = time.time()
        
        try:
            # Get MIME type
            mime_type = self._guess_mime_type(filename)
            if not mime_type:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported file type: {os.path.splitext(filename)[1]}"
                )
            
            # Generate content with image
            response = self.model.generate_content(
                [{"inline_data": {"mime_type": mime_type, "data": image_bytes}}],
                request_options={"timeout": self.timeout},
            )
            
            # Extract text from response
            text = getattr(response, "text", None)
            if not text:
                try:
                    candidate = response.candidates[0]
                    parts = getattr(candidate.content, "parts", [])
                    text = "".join(getattr(part, "text", "") for part in parts)
                except Exception:
                    text = ""
            
            # Parse JSON response
            result = self._safe_json_parse((text or "").strip())
            
            processing_time = time.time() - start_time
            
            return {
                "accessible": result["accessible"],
                "reason": result["reason"],
                "confidence": None,  # Gemini doesn't provide confidence scores
                "model_version": self.model_name,
                "processing_time": processing_time,
                "analyzed_at": time.time()
            }
            
        except Exception as e:
            logger.error(f"Gemini analysis error: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to analyze image: {str(e)}"
            )

# Provider (singleton) for dependency injection
_gemini_service_instance = None

def get_gemini_service() -> "GeminiService":
    global _gemini_service_instance
    if _gemini_service_instance is None:
        _gemini_service_instance = GeminiService()
    return _gemini_service_instance

