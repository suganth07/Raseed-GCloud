from typing import Optional
import base64
import json
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Base64 Encoded Credentials (Primary source)
    raseed_document_ai_key: Optional[str] = Field(None, env="RASEED_DOCUMENT_AI_KEY")
    credentials_json: Optional[str] = Field(None, env="CREDENTIALS_JSON") 
    raseed_firebase_key: Optional[str] = Field(None, env="RASEED_FIREBASE_KEY")
    raseed_wallet_service_account: Optional[str] = Field(None, env="RASEED_WALLET_SERVICE_ACCOUNT")
    
    # Google Cloud Configuration
    google_cloud_project_id: str = Field(..., env="GOOGLE_CLOUD_PROJECT_ID")
    google_cloud_location: str = Field(default="us", env="GOOGLE_CLOUD_LOCATION")
    document_ai_processor_id: str = Field(..., env="DOCUMENT_AI_PROCESSOR_ID")
    google_application_credentials: Optional[str] = Field(None, env="GOOGLE_APPLICATION_CREDENTIALS")
    
    # Gemini API Configuration
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    
    # Firestore Configuration
    firestore_database_id: str = Field(default="(default)", env="FIRESTORE_DATABASE_ID")
    
    # Firebase Configuration (for graph storage)
    firebase_project_id: Optional[str] = Field(None, env="FIREBASE_PROJECT_ID")
    firebase_database_url: Optional[str] = Field(None, env="FIREBASE_DATABASE_URL")
    firebase_credentials_path: Optional[str] = Field(None, env="FIREBASE_CREDENTIALS_PATH")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    debug: bool = Field(default=False, env="DEBUG")
    
    @property
    def api_port(self) -> int:
        """Get the API port from environment variable (Cloud Run sets PORT=8080)."""
        import os
        return int(os.environ.get("PORT", 8080))
    
    # CORS Configuration
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"], 
        env="ALLOWED_ORIGINS"
    )
    
    # Receipt Processing Configuration
    max_file_size: int = Field(default=10 * 1024 * 1024, env="MAX_FILE_SIZE")  # 10MB
    supported_file_types: list[str] = Field(
        default=["image/jpeg", "image/png", "image/webp", "application/pdf"],
        env="SUPPORTED_FILE_TYPES"
    )
    
    # Google Wallet Configuration
    google_wallet_issuer_id: str = Field(..., env="GOOGLE_WALLET_ISSUER_ID")
    google_wallet_service_account_file: str = Field(
        default="raseed-wallet-service-account.json", 
        env="GOOGLE_WALLET_SERVICE_ACCOUNT_FILE"
    )
    
    def decode_base64_to_dict(self, base64_content: str) -> dict:
        """
        Decode base64 content directly to a dictionary.
        """
        try:
            decoded_content = base64.b64decode(base64_content).decode('utf-8')
            return json.loads(decoded_content)
        except Exception as e:
            raise ValueError(f"Failed to decode base64 content to dict: {str(e)}")
    
    def get_document_ai_credentials_dict(self) -> Optional[dict]:
        """
        Get Document AI credentials as dictionary from base64.
        """
        if self.raseed_document_ai_key:
            return self.decode_base64_to_dict(self.raseed_document_ai_key)
        return None
    
    def get_firebase_credentials_dict(self) -> Optional[dict]:
        """
        Get Firebase credentials as dictionary from base64.
        """
        if self.raseed_firebase_key:
            return self.decode_base64_to_dict(self.raseed_firebase_key)
        return None
    
    def get_wallet_credentials_dict(self) -> Optional[dict]:
        """
        Get Wallet credentials as dictionary from base64.
        """
        if self.raseed_wallet_service_account:
            return self.decode_base64_to_dict(self.raseed_wallet_service_account)
        return None
    
    def get_calendar_credentials_dict(self) -> Optional[dict]:
        """
        Get Calendar credentials as dictionary from base64.
        """
        if self.credentials_json:
            return self.decode_base64_to_dict(self.credentials_json)
        return None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra environment variables


# Global settings instance
settings = Settings()