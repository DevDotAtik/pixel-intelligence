from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .yolo_utils import detect_faces
import os
from django.core.files.storage import default_storage

class FaceDetectionView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get('image')
        if not file_obj:
            return Response({"error": "No image provided"}, status=400)

        # Save the uploaded image temporarily
        file_name = default_storage.save(file_obj.name, file_obj)
        file_path = default_storage.path(file_name)

        try:
            # Run YOLO detection
            detections = detect_faces(file_path)

            # Cleanup: Delete the image after processing to save space
            os.remove(file_path)

            return Response({
                "face_count": len(detections),
                "detections": detections
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)