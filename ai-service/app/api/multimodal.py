
"""
可选多模态入口（占位）：工业界常见为「图片 URL / base64 + 视觉模型」。
未开启 MULTIMODAL_ENABLED 时返回说明，避免误用。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.config import settings

router = APIRouter()


class VisionProbeRequest(BaseModel):
    image_url: str = Field(..., description="可公开访问的图片 URL（演示用）")
    question: str = Field(..., description="关于图片的问题")


@router.post("/chat/vision-probe")
async def vision_probe(_req: VisionProbeRequest):
    """
    多模态能力探测端点：当前默认关闭，避免在无视觉模型配置时产生隐性费用。
    开启方式：配置 MULTIMODAL_ENABLED=true 并接入支持 vision 的 OpenAI 兼容端点。
    """
    if not settings.MULTIMODAL_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="多模态未启用。请设置 MULTIMODAL_ENABLED=true 并配置视觉模型与密钥。",
        )
    raise HTTPException(status_code=501, detail="视觉链路待接入：请绑定 ChatOpenAI vision 模型后在此实现。")
