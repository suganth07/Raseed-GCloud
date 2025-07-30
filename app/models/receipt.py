from datetime import datetime, date as date_type
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class ReceiptItem(BaseModel):
    """Model for individual items in a receipt."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Name of the item")
    quantity: int = Field(default=1, description="Quantity of the item")
    unit_price: float = Field(..., description="Price per unit")
    total_price: float = Field(..., description="Total price for this item")
    category: str = Field(default="other", description="Category of the item")
    description: Optional[str] = Field(None, description="Additional item description")
    sku: Optional[str] = Field(None, description="Stock keeping unit")
    discount: Optional[float] = Field(None, description="Discount applied to this item")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date_type: lambda v: v.isoformat()
        }


class Receipt(BaseModel):
    """Model for a complete receipt."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Merchant Information
    merchant_name: str = Field(..., description="Name of the merchant/store")
    merchant_address: Optional[str] = Field(None, description="Address of the merchant")
    merchant_phone: Optional[str] = Field(None, description="Phone number of the merchant")
    merchant_tax_id: Optional[str] = Field(None, description="Tax ID of the merchant")
    
    # Transaction Information
    date: date_type = Field(..., description="Date of the transaction")
    time: Optional[str] = Field(None, description="Time of the transaction")
    receipt_number: Optional[str] = Field(None, description="Receipt/transaction number")
    
    # Financial Information
    total_amount: float = Field(..., description="Total amount of the receipt")
    subtotal: Optional[float] = Field(None, description="Subtotal before tax")
    tax_amount: Optional[float] = Field(None, description="Tax amount")
    tip_amount: Optional[float] = Field(None, description="Tip amount")
    discount_amount: Optional[float] = Field(None, description="Total discount amount")
    currency: str = Field(default="USD", description="Currency code")
    
    # Payment Information
    payment_method: Optional[str] = Field(None, description="Payment method used")
    card_last_four: Optional[str] = Field(None, description="Last four digits of card")
    
    # Items
    items: List[ReceiptItem] = Field(default_factory=list, description="List of items")
    
    # Categorization
    category: str = Field(default="other", description="Overall category of the receipt")
    
    # Processing Information
    confidence_score: float = Field(default=0.0, description="Confidence in extraction")
    raw_text: Optional[str] = Field(None, description="Raw extracted text")
    processing_status: str = Field(default="completed", description="Processing status")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[str] = Field(None, description="ID of the user who uploaded")
    
    # Image Information
    image_url: Optional[str] = Field(None, description="URL of the original image")
    image_hash: Optional[str] = Field(None, description="Hash of the image for deduplication")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date_type: lambda v: v.isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert receipt to dictionary for Firestore storage."""
        data = self.dict()
        
        # Convert datetime objects to ISO strings
        if isinstance(data.get('date'), date_type):
            data['date'] = data['date'].isoformat()
        if isinstance(data.get('created_at'), datetime):
            data['created_at'] = data['created_at'].isoformat()
        if isinstance(data.get('updated_at'), datetime):
            data['updated_at'] = data['updated_at'].isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Receipt':
        """Create receipt from dictionary (e.g., from Firestore)."""
        # Convert ISO strings back to datetime objects
        if isinstance(data.get('date'), str):
            data['date'] = datetime.fromisoformat(data['date']).date()
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        return cls(**data)
    
    def calculate_totals(self) -> None:
        """Recalculate totals based on items."""
        self.subtotal = sum(item.total_price for item in self.items)
        
        if self.tax_amount is None and self.subtotal and self.total_amount:
            self.tax_amount = self.total_amount - self.subtotal
    
    def add_item(self, item: ReceiptItem) -> None:
        """Add an item to the receipt."""
        self.items.append(item)
        self.calculate_totals()
        self.updated_at = datetime.utcnow()
    
    def remove_item(self, item_id: str) -> bool:
        """Remove an item from the receipt."""
        original_count = len(self.items)
        self.items = [item for item in self.items if item.id != item_id]
        
        if len(self.items) < original_count:
            self.calculate_totals()
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def get_items_by_category(self, category: str) -> List[ReceiptItem]:
        """Get all items in a specific category."""
        return [item for item in self.items if item.category == category]
    
    def get_total_by_category(self, category: str) -> float:
        """Get total amount for a specific category."""
        return sum(item.total_price for item in self.get_items_by_category(category))


class ReceiptSearchQuery(BaseModel):
    """Model for receipt search queries."""
    merchant_name: Optional[str] = None
    category: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    start_date: Optional[date_type] = None
    end_date: Optional[date_type] = None
    payment_method: Optional[str] = None
    user_id: Optional[str] = None
    
    class Config:
        json_encoders = {
            date_type: lambda v: v.isoformat()
        }


class ReceiptSummary(BaseModel):
    """Model for receipt summaries and analytics."""
    total_receipts: int
    total_amount: float
    average_amount: float
    currency: str
    date_range: Dict[str, date_type]
    top_merchants: List[Dict[str, Any]]
    category_breakdown: Dict[str, float]
    monthly_spending: Dict[str, float]
    
    class Config:
        json_encoders = {
            date_type: lambda v: v.isoformat()
        }