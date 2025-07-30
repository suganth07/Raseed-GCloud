"""
Simple Document AI service for text extraction and structured receipt parsing using Google ADK.
Extracts text and converts it to structured receipt JSON format.
"""

import os
import re
from datetime import datetime
from typing import Dict, Any
from google.cloud import documentai
from ..utils.config import settings
from ..utils.logging import get_logger


class SimpleDocumentAI:
    """Simple Document AI service for text extraction only."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.project_id = settings.google_cloud_project_id
        self.location = settings.google_cloud_location
        self.processor_id = settings.document_ai_processor_id
        
        # Set up authentication using base64 credentials
        self.credentials_dict = settings.get_document_ai_credentials_dict()
        if self.credentials_dict:
            self.logger.info("Using Document AI credentials from environment (base64)")
        else:
            self.logger.error("No Document AI credentials found")
        
        # Initialize client only when needed
        self._client = None
        self._processor_name = None
    
    def _get_client(self):
        """Get Document AI client (lazy initialization)."""
        if self._client is None:
            from google.oauth2 import service_account
            
            # Create credentials from the dictionary
            credentials = service_account.Credentials.from_service_account_info(self.credentials_dict)
            
            # Initialize client with credentials
            self._client = documentai.DocumentProcessorServiceClient(credentials=credentials)
            self._processor_name = self._client.processor_path(
                self.project_id, self.location, self.processor_id
            )
            self.logger.info(f"Initialized Document AI client for processor: {self.processor_id}")
        return self._client
    
    async def extract_text_from_image(self, image_data: bytes, mime_type: str = "image/jpeg") -> Dict[str, Any]:
        """
        Extract text from image using Document AI.
        Simplified to just extract text without complex parsing.
        
        Args:
            image_data: Raw image bytes
            mime_type: MIME type of the image
            
        Returns:
            Dictionary with extracted text and basic metadata
        """
        try:
            self.logger.info(f"Processing image with Document AI, mime_type: {mime_type}")
            
            # Validate inputs
            if not image_data:
                raise ValueError("No image data provided")
            
            if len(image_data) == 0:
                raise ValueError("Empty image data")
            
            # Get client
            client = self._get_client()
            
            # The full resource name of the processor
            name = client.processor_path(self.project_id, self.location, self.processor_id)
            
            # Create raw document with validated inputs
            raw_document = documentai.RawDocument(
                content=image_data,
                mime_type=mime_type
            )
            
            # Configure the process request
            request = documentai.ProcessRequest(
                name=name,
                raw_document=raw_document
            )
            
            # Use the Document AI client to process the document
            result = client.process_document(request=request)
            document = result.document
            
            # Extract text
            extracted_text = document.text or ""
            
            # Simple response with basic parsing
            response = {
                "success": True,
                "extracted_text": extracted_text,
                "text_length": len(extracted_text),
                "confidence": self._calculate_confidence(document),
                "mime_type": mime_type,
                "processor_id": self.processor_id,
                "receipt_data": self._parse_basic_receipt_data(extracted_text)
            }
            
            self.logger.info(f"Successfully extracted {len(extracted_text)} characters")
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing document: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "extracted_text": "",
                "text_length": 0,
                "confidence": 0.0,
                "mime_type": mime_type,
                "receipt_data": {}
            }

    def _parse_basic_receipt_data(self, text: str) -> Dict[str, Any]:
        """
        Parse basic receipt data from extracted text.
        
        Args:
            text: Raw extracted text from receipt
            
        Returns:
            Basic receipt data including merchant name and total
        """
        import re
        
        receipt_data = {
            "merchant_name": "Unknown Merchant",
            "total_amount": 0.0,
            "currency": "USD",
            "business_category": "Retail",
            "location": {"city": "Unknown", "state": "Unknown", "country": "USA", "formatted_address": "Unknown Location"}
        }
        
        try:
            lines = text.split('\n')
            
            # Extract merchant name - usually one of the first few lines with all caps
            for i, line in enumerate(lines[:8]):  # Check first 8 lines
                line = line.strip()
                if len(line) > 3 and line.isupper() and not any(skip in line.lower() for skip in ['receipt', 'bill', 'invoice', '***', '---', '===', 'address', 'phone']):
                    # Found potential merchant name
                    if 'SUPER' in line or 'MARKET' in line or 'STORE' in line or len(line) > 8:
                        receipt_data["merchant_name"] = line.title()
                        receipt_data["business_category"] = "Grocery" if any(word in line.lower() for word in ['super', 'market', 'grocery']) else "Retail"
                        break
            
            # Extract total amount - look for patterns like "Total: 780.00", "Amount: 780", etc.
            total_patterns = [
                r'total[:\s]+([0-9,]+\.?[0-9]*)',
                r'amount[:\s]+([0-9,]+\.?[0-9]*)',
                r'received\s+amt[:\s]+([0-9,]+\.?[0-9]*)',
                r'grand\s+total[:\s]+([0-9,]+\.?[0-9]*)',
                r'net\s+amount[:\s]+([0-9,]+\.?[0-9]*)',
                r'final\s+amount[:\s]+([0-9,]+\.?[0-9]*)',
                # Look for dollar amounts
                r'\$([0-9,]+\.?[0-9]*)',
                # Look for rupee amounts
                r'₹([0-9,]+\.?[0-9]*)',
                r'rs[.\s]*([0-9,]+\.?[0-9]*)',
                # Look for standalone amounts that appear multiple times (likely total)
                r'^([0-9]{3,5}\.00)$'  # Matches lines like "780.00"
            ]
            
            # Store all potential totals with their frequency
            potential_totals = {}
            
            for line in lines:
                line_lower = line.lower().strip()
                for pattern in total_patterns:
                    matches = re.findall(pattern, line_lower)
                    for match in matches:
                        try:
                            total = float(match.replace(',', ''))
                            if 10 <= total <= 50000:  # Reasonable range for receipts
                                if total in potential_totals:
                                    potential_totals[total] += 1
                                else:
                                    potential_totals[total] = 1
                        except (ValueError, AttributeError):
                            continue
            
            # Use the highest amount that appears most frequently
            if potential_totals:
                # If a total appears multiple times, prefer it
                max_frequency = max(potential_totals.values())
                high_frequency_totals = [total for total, freq in potential_totals.items() if freq == max_frequency]
                receipt_data["total_amount"] = max(high_frequency_totals)
                # Determine currency based on region or text
                if any(char in text for char in ['₹', 'inr', 'rupee']):
                    receipt_data["currency"] = "INR"
                elif any(char in text for char in ['$', 'usd', 'dollar']):
                    receipt_data["currency"] = "USD"
            
            # Extract location information
            for line in lines:
                line_lower = line.lower()
                # Look for Indian locations
                if 'pallipalayam' in line_lower:
                    receipt_data["location"] = {
                        "city": "Pallipalayam",
                        "state": "Tamil Nadu", 
                        "country": "India",
                        "formatted_address": line.strip()
                    }
                    receipt_data["currency"] = "INR"
                    break
                # Look for other location indicators
                elif any(indicator in line_lower for indicator in ['road', 'street', 'avenue', 'city', 'state']):
                    receipt_data["location"]["formatted_address"] = line.strip()
            
        except Exception as e:
            self.logger.warning(f"Error parsing basic receipt data: {e}")
        
        return receipt_data

    def _parse_receipt_text(self, text: str) -> Dict[str, Any]:
        """
        Parse extracted text into structured receipt JSON format.
        
        Args:
            text: Raw extracted text from receipt
            
        Returns:
            Structured receipt data in the specified format
        """
        
        # Generate receipt ID
        receipt_id = f"RCP-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"
        
        # Initialize receipt structure
        receipt_json = {
            "receipt_id": receipt_id,
            "receipt_json": {
                "date": datetime.now().isoformat(),
                "store": {
                    "name": "Unknown Store",
                    "location": "",
                    "contact": "",
                    "gst_number": ""
                },
                "customer": {
                    "name": "",
                    "email": "",
                    "phone": ""
                },
                "items": [],
                "subtotal": 0.0,
                "taxes": [],
                "total_amount": 0.0,
                "payment": {
                    "method": "Unknown",
                    "status": "Unknown",
                    "transaction_id": ""
                }
            }
        }
        
        lines = text.split('\n')
        
        # Extract store name (usually at the top)
        for i, line in enumerate(lines[:5]):
            line = line.strip()
            if line and not line.lower().startswith(('receipt', '*', '=')):
                if len(line) > 3 and not re.match(r'^\d+', line):
                    receipt_json["receipt_json"]["store"]["name"] = line
                    break
        
        # Extract total amount
        total_patterns = [
            r'total[:\s]*[\$₹]?(\d+\.?\d*)',
            r'amount[:\s]*[\$₹]?(\d+\.?\d*)',
            r'[\$₹](\d+\.?\d*)\s*total'
        ]
        
        for line in lines:
            line_lower = line.lower().strip()
            for pattern in total_patterns:
                match = re.search(pattern, line_lower)
                if match:
                    try:
                        total = float(match.group(1))
                        receipt_json["receipt_json"]["total_amount"] = total
                        receipt_json["receipt_json"]["subtotal"] = total * 0.85  # Approximate subtotal
                        break
                    except ValueError:
                        continue
        
        # Extract items (basic parsing)
        item_counter = 1
        for line in lines:
            line = line.strip()
            # Look for lines with prices
            price_match = re.search(r'[\$₹]?(\d+\.?\d*)', line)
            if price_match and len(line) > 5:
                # Skip total lines
                if any(word in line.lower() for word in ['total', 'tax', 'subtotal', 'amount']):
                    continue
                
                try:
                    price = float(price_match.group(1))
                    if price > 0:
                        # Extract item name (text before price)
                        item_name = re.sub(r'[\$₹]?\d+\.?\d*', '', line).strip()
                        if item_name:
                            item = {
                                "item_id": f"PROD-{item_counter:03d}",
                                "name": item_name,
                                "quantity": 1,
                                "unit_price": price,
                                "total_price": price,
                                "tax_percent": 18
                            }
                            receipt_json["receipt_json"]["items"].append(item)
                            item_counter += 1
                except ValueError:
                    continue
        
        # Calculate tax if total amount is available
        if receipt_json["receipt_json"]["total_amount"] > 0:
            subtotal = receipt_json["receipt_json"]["subtotal"]
            tax_amount = receipt_json["receipt_json"]["total_amount"] - subtotal
            if tax_amount > 0:
                receipt_json["receipt_json"]["taxes"] = [{
                    "type": "GST",
                    "percent": 18,
                    "amount": round(tax_amount, 2)
                }]
        
        # Extract payment method (basic detection)
        text_lower = text.lower()
        if 'upi' in text_lower:
            receipt_json["receipt_json"]["payment"]["method"] = "UPI"
        elif 'card' in text_lower or 'visa' in text_lower or 'mastercard' in text_lower:
            receipt_json["receipt_json"]["payment"]["method"] = "Card"
        elif 'cash' in text_lower:
            receipt_json["receipt_json"]["payment"]["method"] = "Cash"
        
        return receipt_json
    
    def _calculate_confidence(self, document) -> float:
        """Calculate average confidence from document."""
        try:
            if hasattr(document, 'pages') and document.pages:
                total_confidence = 0
                count = 0
                for page in document.pages:
                    if hasattr(page, 'tokens'):
                        for token in page.tokens:
                            if hasattr(token, 'text_anchor') and hasattr(token.text_anchor, 'confidence'):
                                total_confidence += token.text_anchor.confidence
                                count += 1
                
                if count > 0:
                    return total_confidence / count
                    
            return 0.85  # Default confidence
        except Exception:
            return 0.85


# Create a global instance for use in routes
simple_document_ai = SimpleDocumentAI()
