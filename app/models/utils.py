from typing import Any, Dict, List
from bson import ObjectId

def serialize_doc(doc: Any) -> Any:
    """
    MongoDB 문서를 JSON 직렬화 가능하게 변환.
    _id(ObjectId)를 문자열로 바꾸고, 중첩 구조도 처리.
    """
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, list):
        return [serialize_doc(x) for x in doc]
    if isinstance(doc, dict):
        return {k: serialize_doc(v) for k, v in doc.items()}
    return doc
