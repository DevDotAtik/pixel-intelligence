"""Django detector app — thin proxy to the FastAPI detection service.

Kept for API compatibility (``POST /api/detect/``). All YOLO work lives in the
FastAPI service (``app/`` package); this view just forwards the image + chosen
model and returns the backend's response so the two servers never disagree.
"""
import os

import requests
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


class FaceDetectionView(APIView):
    """Proxy ``POST /api/detect/`` to FastAPI ``/api/detect``."""

    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get("image")
        if not file_obj:
            return Response({"error": "No image provided"}, status=400)

        model = (request.POST.get("model") or request.GET.get("model") or "face").lower()
        camera_code = request.POST.get("camera_code") or "CAM-01"

        try:
            resp = requests.post(
                f"{FASTAPI_BASE_URL}/api/detect",
                files={"image_data": (file_obj.name, file_obj.read(), file_obj.content_type or "image/jpeg")},
                data={"model": model, "camera_code": camera_code},
                timeout=20,
            )
            if resp.status_code != 200:
                return Response({"error": f"Backend error: {resp.text[:300]}"}, status=resp.status_code)
            payload = resp.json()
            return Response(
                {
                    "face_count": len(payload.get("detections", [])),
                    "model": model,
                    "detections": payload.get("detections", []),
                    "analytics": payload.get("analytics", {}),
                }
            )
        except requests.RequestException as error:
            return Response({"error": f"Backend unavailable: {error}"}, status=503)