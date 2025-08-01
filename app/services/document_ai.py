import asyncio
import io
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, date
import base64

from google.cloud import documentai
from google.cloud.documentai_v1 import Document
from PIL import Image
import google.generativeai as genai

from ..utils.config import settings
from ..utils.logging import get_logger, LoggerMixin
from ..models.receipt import Receipt, ReceiptItem


class DocumentAIService(LoggerMixin):
    """Service for processing documents using Google Cloud Document AI and Gemini."""
    
    def __init__(self):
        self.project_id = settings.google_cloud_project_id
        self.location = settings.google_cloud_location
        self.processor_id = settings.document_ai_processor_id
        
        # Initialize Document AI client
        self.client = documentai.DocumentProcessorServiceClient()
        self.processor_name = self.client.processor_path(
            self.project_id, self.location, self.processor_id
        )
        
        # Initialize Gemini
        genai.configure(api_key=settings.gemini_api_key)
        self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        
        self.logger.info("Document AI Service initialized")
    
    async def process_receipt_image(
        self, 
        image_data: bytes, 
        mime_type: str = "image/jpeg"
    ) -> Receipt:
        """
        Process a receipt image and extract structured data.
        
        Args:
            image_data: Raw image bytes
            mime_type: MIME type of the image
            
        Returns:
            Receipt object with extracted data
        """
        try:
            self.log_operation("process_receipt_image", mime_type=mime_type)
            
            # Process with Document AI
            document = await self._process_with_document_ai(image_data, mime_type)
            
            # Extract basic text
            extracted_text = self._extract_text(document)
            
            # Enhance with Gemini AI
            receipt_data = await self._enhance_with_gemini(image_data, extracted_text)
            
            # Create Receipt object
            receipt = self._create_receipt_object(receipt_data, extracted_text)
            
            self.log_operation("process_receipt_image_completed", receipt_id=receipt.id)
            return receipt
            
        except Exception as e:
            self.log_error("process_receipt_image", e)
            raise
    
    async def _process_with_document_ai(
        self, 
        image_data: bytes, 
        mime_type: str
    ) -> Document:
        """Process document with Google Cloud Document AI."""
        try:
            # Prepare the document
            raw_document = documentai.RawDocument(
                content=image_data,
                mime_type=mime_type
            )
            
            # Configure the process request
            request = documentai.ProcessRequest(
                name=self.processor_name,
                raw_document=raw_document
            )
            
            # Process the document
            result = self.client.process_document(request=request)
            return result.document
            
        except Exception as e:
            self.log_error("document_ai_processing", e)
            raise
    
    def _extract_text(self, document: Document) -> str:
        """Extract text from Document AI response."""
        try:
            text = document.text
            self.log_operation("text_extracted", text_length=len(text))
            return text
        except Exception as e:
            self.log_error("text_extraction", e)
            return ""
    
    async def _enhance_with_gemini(
        self, 
        image_data: bytes, 
        extracted_text: str
    ) -> Dict[str, Any]:
        """Use Gemini to enhance and structure the extracted data."""
        try:
            # Convert image to PIL Image for Gemini
            image = Image.open(io.BytesIO(image_data))
            
            # Create enhanced prompt
            prompt = self._create_gemini_prompt(extracted_text)
            
            # Generate response with Gemini
            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                [prompt, image]
            )
            
            # Parse the response
            receipt_data = self._parse_gemini_response(response.text)
            
            self.log_operation("gemini_enhancement_completed")
            return receipt_data
            
        except Exception as e:
            self.log_error("gemini_enhancement", e)
            # Return basic structure if Gemini fails
            return self._create_fallback_receipt_data(extracted_text)
    
    def _create_gemini_prompt(self, extracted_text: str) -> str:
        """Create a structured prompt for Gemini to analyze the receipt with enhanced merchant and price extraction."""
        return f"""
        You are an expert receipt analyzer. Analyze this receipt image and extracted text to create a structured JSON response.
        
        Extracted Text:
        {extracted_text}
        
        CRITICAL INSTRUCTIONS FOR INDIAN RECEIPTS:
        1. MERCHANT NAME: Look for the ENGLISH business name at the very top - IGNORE Tamil/Hindi text, bill numbers, dates
        2. PRICE EXTRACTION: Look for tabular format with columns like "Product MRP Rate Qty Amt" - extract the "Rate" or "Amt" column
        3. QUANTITIES: Extract from "Qty" column in tabular format
        4. CURRENCY: Detect ₹, Rs., INR for Indian receipts
        
        Please provide a JSON response with the following structure:
        {{
            "merchant_name": "ENGLISH store name from top of receipt (e.g., 'Nellai department stores', 'Big Bazaar', 'Reliance Fresh') - NEVER bill numbers or Tamil text",
            "merchant_address": "full address if available",
            "date": "YYYY-MM-DD format",
            "time": "HH:MM format if available", 
            "total_amount": "total amount as float",
            "tax_amount": "tax amount as float if available",
            "currency": "INR for Indian receipts with ₹ or Rs.",
            "receipt_number": "receipt/transaction number if available",
            "payment_method": "cash/card/mobile etc if available",
            "items": [
                {{
                    "name": "exact item name from receipt",
                    "quantity": "quantity from Qty column as integer",
                    "unit_price": "price from Rate column as float - NEVER 0 unless actually free",
                    "total_price": "amount from Amt column as float",
                    "category": "product category based on item name"
                }}
            ],
            "category": "overall receipt category (grocery, restaurant, fuel, pharmacy, etc.)",
            "confidence_score": "confidence in extraction (0.0 to 1.0)"
        }}
        
        ENHANCED EXTRACTION RULES FOR INDIAN RETAIL RECEIPTS:
        
        MERCHANT NAME IDENTIFICATION:
        - Find the ENGLISH store name at the very top of the receipt
        - IGNORE these patterns: "பில் நம்பர்", "Bill No:", "Date:", reference numbers, Tamil/Hindi text
        - Examples for this receipt:
          ✅ CORRECT: "Nellai department stores", "Big Bazaar", "Reliance Fresh"
          ❌ WRONG: "பில் நம்பர் :Ssds/23-24/32860 தேடிव : 23-06-2025", "SSDS/23-24/32860"
        
        TABULAR PRICE EXTRACTION:
        - Look for table format: "Product    MRP  Rate  Qty  Amt"
        - Extract item name from first column
        - Extract Rate (unit price) from "Rate" column
        - Extract quantity from "Qty" column  
        - Extract total amount from "Amt" column
        - Example parsing:
          "MPK ARUL DEEPAM OIL-1L    200.00 140.00 1.00 140.00"
          → name: "MPK ARUL DEEPAM OIL-1L", rate: 140.00, qty: 1, amount: 140.00
        
        INDIAN CURRENCY HANDLING:
        - Detect ₹, Rs., INR patterns
        - Convert "Rs: 2243.00" to currency: "INR", amount: 2243.00
        
        CATEGORY CLASSIFICATION RULES:
        - OIL/COOKING: "food" category
        - SOAP/SHAMPOO: "personal_care" category  
        - DETERGENT/CLEANER: "household" category
        - INSECTICIDE/CHALK: "household" category (NOT food)
        - SPICES/MASALA: "food" category
        - SALT: "food" category
        
        Important:
        - Extract ALL items from the receipt with their REAL prices from Rate/Amt columns
        - Use null for missing information, not placeholder values
        - Ensure amounts are numeric and accurate
        - Prioritize ENGLISH text for merchant names over any other language
        - For Indian receipts, use INR currency and extract prices carefully from tabular format
        - Never return 0 for prices unless the item is genuinely free
        """
    
    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Gemini's JSON response."""
        try:
            import json
            
            # Clean the response text
            clean_text = response_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            
            # Parse JSON
            data = json.loads(clean_text.strip())
            
            self.log_operation("gemini_response_parsed", items_count=len(data.get('items', [])))
            return data
            
        except json.JSONDecodeError as e:
            self.log_error("json_parsing", e, response_text=response_text[:200])
            # Return fallback structure
            return {
                "merchant_name": "Unknown",
                "total_amount": 0.0,
                "currency": "INR",
                "items": [],
                "category": "other",
                "confidence_score": 0.0
            }
    
    def _create_fallback_receipt_data(self, extracted_text: str) -> Dict[str, Any]:
        """Create fallback receipt data when Gemini processing fails."""
        return {
            "merchant_name": "Unknown",
            "extracted_text": extracted_text,
            "total_amount": 0.0,
            "currency": "INR",
            "items": [],
            "category": "other",
            "confidence_score": 0.0,
            "processing_status": "fallback"
        }
    
    def _create_receipt_object(
        self, 
        receipt_data: Dict[str, Any], 
        extracted_text: str
    ) -> Receipt:
        """Create a Receipt object from extracted data."""
        try:
            # Parse items
            items = []
            for item_data in receipt_data.get('items', []):
                item = ReceiptItem(
                    name=item_data.get('name', 'Unknown Item'),
                    quantity=item_data.get('quantity', 1),
                    unit_price=float(item_data.get('unit_price', 0.0)),
                    total_price=float(item_data.get('total_price', 0.0)),
                    category=item_data.get('category', 'other')
                )
                items.append(item)
            
            # Parse date
            receipt_date = None
            if receipt_data.get('date'):
                try:
                    receipt_date = datetime.strptime(receipt_data['date'], '%Y-%m-%d').date()
                except ValueError:
                    receipt_date = datetime.now().date()
            else:
                receipt_date = datetime.now().date()
            
            # Create receipt
            receipt = Receipt(
                merchant_name=receipt_data.get('merchant_name', 'Unknown'),
                merchant_address=receipt_data.get('merchant_address'),
                date=receipt_date,
                time=receipt_data.get('time'),
                total_amount=float(receipt_data.get('total_amount', 0.0)),
                tax_amount=float(receipt_data.get('tax_amount', 0.0)) if receipt_data.get('tax_amount') else None,
                currency=receipt_data.get('currency', 'INR'),
                receipt_number=receipt_data.get('receipt_number'),
                payment_method=receipt_data.get('payment_method'),
                items=items,
                category=receipt_data.get('category', 'other'),
                confidence_score=float(receipt_data.get('confidence_score', 0.0)),
                raw_text=extracted_text
            )
            
            self.log_operation("receipt_object_created", receipt_id=receipt.id)
            return receipt
            
        except Exception as e:
            self.log_error("receipt_object_creation", e)
            raise
    
    async def process_multiple_receipts(
        self, 
        images_data: List[tuple[bytes, str]]
    ) -> List[Receipt]:
        """Process multiple receipt images concurrently."""
        try:
            self.log_operation("process_multiple_receipts", count=len(images_data))
            
            # Process all receipts concurrently
            tasks = [
                self.process_receipt_image(image_data, mime_type)
                for image_data, mime_type in images_data
            ]
            
            receipts = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter successful results
            successful_receipts = [
                receipt for receipt in receipts 
                if isinstance(receipt, Receipt)
            ]
            
            # Log any failures
            failed_count = len(receipts) - len(successful_receipts)
            if failed_count > 0:
                self.logger.warning(f"Failed to process {failed_count} receipts")
            
            self.log_operation(
                "process_multiple_receipts_completed",
                successful=len(successful_receipts),
                failed=failed_count
            )
            
            return successful_receipts
            
        except Exception as e:
            self.log_error("process_multiple_receipts", e)
            raise