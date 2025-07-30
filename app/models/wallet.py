"""
Wallet-related data models for Google Wallet integration.
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
import uuid


class WalletEligibleItem(BaseModel):
    """Model for items eligible to be added to Google Wallet."""
    id: str = Field(..., description="Unique identifier for the item")
    title: str = Field(..., description="Display title for the item")
    subtitle: str = Field(..., description="Display subtitle for the item")
    item_type: Literal["receipt", "warranty"] = Field(..., description="Type of wallet item")
    
    # Receipt-specific fields
    receipt_id: Optional[str] = Field(None, description="Receipt ID if this is a receipt item")
    merchant_name: Optional[str] = Field(None, description="Merchant name")
    total_amount: Optional[float] = Field(None, description="Total amount")
    currency: Optional[str] = Field(None, description="Currency code")
    transaction_date: Optional[date] = Field(None, description="Transaction date")
    item_count: Optional[int] = Field(None, description="Number of items in receipt")
    
    # Warranty-specific fields  
    product_name: Optional[str] = Field(None, description="Product name")
    brand: Optional[str] = Field(None, description="Product brand")
    warranty_period: Optional[str] = Field(None, description="Warranty period")
    expiry_date: Optional[date] = Field(None, description="Warranty expiry date")
    purchase_date: Optional[date] = Field(None, description="Purchase date")
    
    # Status tracking
    added_to_wallet: bool = Field(default=False, description="Whether item is already in wallet")
    wallet_pass_id: Optional[str] = Field(None, description="Google Wallet pass ID")
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class PassGenerationRequest(BaseModel):
    """Request model for generating wallet passes."""
    item_id: str = Field(..., description="ID of the item to generate pass for")
    pass_type: Literal["receipt", "warranty"] = Field(..., description="Type of pass to generate")
    user_id: str = Field(..., description="User ID requesting the pass")


class PassGenerationResponse(BaseModel):
    """Response model for pass generation."""
    success: bool = Field(..., description="Whether pass generation was successful")
    jwt: Optional[str] = Field(None, description="Signed JWT for Google Wallet")
    pass_id: Optional[str] = Field(None, description="Generated pass ID")
    wallet_url: Optional[str] = Field(None, description="Google Wallet save URL")
    error: Optional[str] = Field(None, description="Error message if generation failed")


class WalletItemsResponse(BaseModel):
    """Response model for eligible wallet items."""
    success: bool = Field(..., description="Whether request was successful")
    items: List[WalletEligibleItem] = Field(default_factory=list, description="List of eligible items")
    total_receipts: int = Field(default=0, description="Total number of eligible receipts")
    total_warranties: int = Field(default=0, description="Total number of eligible warranties")
    error: Optional[str] = Field(None, description="Error message if request failed")


class GoogleWalletPassObject(BaseModel):
    """Model for Google Wallet pass object structure."""
    id: str = Field(..., description="Unique pass ID")
    classId: str = Field(..., description="Pass class ID")
    genericType: str = Field(default="GENERIC_TYPE_UNSPECIFIED")
    hexBackgroundColor: str = Field(..., description="Background color in hex")
    
    # Logo and branding
    logo: Optional[Dict[str, Any]] = Field(None, description="Logo configuration")
    
    # Text content
    cardTitle: Dict[str, Dict[str, str]] = Field(..., description="Card title")
    header: Dict[str, Dict[str, str]] = Field(..., description="Header text")
    subheader: Dict[str, Dict[str, str]] = Field(..., description="Subheader text")
    
    # Additional information
    textModulesData: List[Dict[str, Any]] = Field(default_factory=list, description="Additional text modules")
    
    # Barcode/QR code
    barcode: Optional[Dict[str, str]] = Field(None, description="Barcode configuration")
    
    # Links and actions
    linksModuleData: Optional[Dict[str, Any]] = Field(None, description="Links module")


class WalletJWTPayload(BaseModel):
    """Model for Google Wallet JWT payload."""
    iss: str = Field(..., description="Issuer email")
    aud: str = Field(default="google", description="Audience")
    typ: str = Field(default="savetowallet", description="Token type")
    iat: int = Field(..., description="Issued at timestamp")
    payload: Dict[str, Any] = Field(..., description="Pass payload")
