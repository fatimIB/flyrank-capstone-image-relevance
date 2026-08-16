from groq import BaseModel


class ImageMetadata(BaseModel):
    subject: str          
    category: str         
    attributes: list[str] 
    caption: str          
    confidence: float     