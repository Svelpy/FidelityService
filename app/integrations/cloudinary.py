import logging

import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.core.config import Settings, get_settings
from app.shared.errors.exceptions import AppException


logger = logging.getLogger(__name__)


def configure_cloudinary(settings: Settings) -> None:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )

class CloudinaryService:
    @staticmethod
    def _extract_public_id(url: str) -> str:
        """
        Extrae el public_id de una URL de Cloudinary.
        """
        try:
            # Dividir por '/upload/' para obtener la parte derecha de la URL
            parts = url.split("/upload/")
            if len(parts) < 2:
                raise ValueError("URL de Cloudinary inválida")
            
            # Quitar la versión (ej: 'v123456789/') si existe
            right_part = parts[1]
            if right_part.startswith("v"):
                right_part = "/".join(right_part.split("/")[1:])
            
            # Quitar la extensión del archivo (ej: '.jpg')
            public_id = right_part.rsplit(".", 1)[0]
            return public_id

        except Exception:
            raise AppException("No se pudo extraer el identificador de la imagen", 400)
    
    
    @staticmethod
    async def upload_image(
        file: UploadFile,
        folder: str,
    ) -> str:
        """
        Sube una imagen a Cloudinary y retorna la URL segura.
        """
        # 1. Validar Content-Type
        if not file.content_type.startswith("image/"):
            raise AppException("El archivo debe ser una imagen", 400)
        
        # Bloquear SVG explícitamente (riesgo de XSS)
        if file.content_type == "image/svg+xml" or file.filename.lower().endswith('.svg'):
            raise AppException("Los archivos SVG no están permitidos ", 400)
            
        # 2. Leer archivo
        content = await file.read()
        
        # 3. Validar tamaño (Max 5MB)
        if len(content) > 5 * 1024 * 1024:
             raise AppException("La imagen no puede pesar más de 5MB", 400)
        # 4. Subir a Cloudinary    
        try:
            
            response = cloudinary.uploader.upload(
                content, 
                folder=f"{get_settings().CLOUDINARY_FOLDER_NAME}/{folder}",
                resource_type="image"
            )
            return response.get("secure_url")

        finally:
            await file.seek(0)

    @staticmethod
    async def delete_image(image_url: str) -> bool:
        """
        Elimina una imagen de Cloudinary a partir de su URL.
        """
        if not image_url:
            return False
            
        public_id = CloudinaryService._extract_public_id(image_url)
        response = cloudinary.uploader.destroy(public_id)
        return response.get("result") == "ok"

    @staticmethod
    async def safe_delete_image(image_url: str) -> bool:
        """Intenta eliminar una imagen sin interrumpir la operación principal."""
        try:
            return await CloudinaryService.delete_image(image_url)
        except Exception:
            logger.exception(
                "No se pudo eliminar una imagen residual de Cloudinary: %s",
                image_url,
            )
            return False

