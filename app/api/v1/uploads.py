from fastapi import APIRouter, UploadFile, File, Query
from app.core.dependencies import CurrentUser
from app.utils.file_upload import upload_file
from app.utils.response import success_response

router = APIRouter(prefix="/uploads", tags=["File Uploads"])

ALLOWED_FOLDERS = {"gym-logos", "gym-photos", "member-photos", "trainer-photos", "documents"}


@router.post("/")
async def upload(
    current_user: CurrentUser,
    file: UploadFile = File(...),
    folder: str = Query("general", description="Cloudinary folder"),
):
    if folder not in ALLOWED_FOLDERS:
        folder = "general"
    content = await file.read()
    url = await upload_file(content, file.content_type, folder=folder)
    return success_response({"url": url, "folder": folder, "filename": file.filename})
