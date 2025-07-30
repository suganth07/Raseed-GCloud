"""
Warranty Reminder Service

This service integrates the Google Calendar Agent with the warranty data from Firestore
to create automated reminders for warranty expiration dates.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from .calendar import GoogleCalendarAgent
from .firestore_service import FirestoreService
from ..utils.logging import LoggerMixin


class WarrantyReminderService(LoggerMixin):
    """Service to manage warranty expiration reminders through Google Calendar."""
    
    def __init__(self):
        """Initialize the warranty reminder service."""
        super().__init__()
        self.calendar_agent = GoogleCalendarAgent()
        self.firestore_service = FirestoreService()
        
    async def check_and_create_warranty_reminders(self, user_id: str) -> Dict[str, Any]:
        """
        Check all warranties for a user and create calendar reminders 2 days before expiry.
        
        Args:
            user_id: The user ID to check warranties for
            
        Returns:
            Dict containing the result of the operation
        """
        try:
            self.logger.info(f"Checking warranty reminders for user: {user_id}")
            
            # Get all warranty data from knowledge graphs
            warranty_items = await self._get_user_warranties(user_id)
            
            if not warranty_items:
                return {
                    "status": "success",
                    "message": "No warranties found for the user",
                    "reminders_created": 0
                }
            
            # Process each warranty and create reminders
            reminders_created = 0
            failed_reminders = []
            
            for warranty in warranty_items:
                try:
                    result = await self._create_warranty_reminder(warranty)
                    if result["status"] == "success":
                        reminders_created += 1
                        self.logger.info(f"Created reminder for {warranty['product_name']}")
                    else:
                        failed_reminders.append({
                            "product": warranty["product_name"],
                            "error": result.get("error_message", "Unknown error")
                        })
                except Exception as e:
                    self.log_error("_create_warranty_reminder", e)
                    failed_reminders.append({
                        "product": warranty.get("product_name", "Unknown"),
                        "error": str(e)
                    })
            
            return {
                "status": "success",
                "message": f"Created {reminders_created} warranty reminders",
                "reminders_created": reminders_created,
                "failed_reminders": failed_reminders,
                "total_warranties": len(warranty_items)
            }
            
        except Exception as e:
            self.log_error("check_and_create_warranty_reminders", e)
            return {
                "status": "error",
                "error_message": f"Failed to check warranty reminders: {str(e)}"
            }
    
    async def _get_user_warranties(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all warranty items from user's knowledge graphs.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of warranty dictionaries
        """
        try:
            warranty_items = []
            
            # Get all knowledge graphs for the user from nested collection
            # Path: /users/{user_id}/knowledge_graphs/{kg_id}
            user_doc_ref = self.firestore_service.db.collection('users').document(user_id)
            graphs_collection = user_doc_ref.collection('knowledge_graphs')
            docs = graphs_collection.stream()
            
            for doc in docs:
                graph_data = doc.to_dict()
                
                # Products are stored directly in 'products' array, not in 'entities'
                products = graph_data.get('products', [])
                
                # Find products with warranties or expiry dates
                for product in products:
                    # Check for warranty or expiry information
                    has_warranty = product.get('warranty', False) or product.get('warranty_period') is not None
                    has_expiry = product.get('has_expiry', False) or product.get('expiry_date') is not None
                    
                    if has_warranty or has_expiry:
                        warranty_item = await self._extract_warranty_info_from_product(product, graph_data)
                        if warranty_item:
                            warranty_items.append(warranty_item)
            
            self.logger.info(f"Found {len(warranty_items)} warranty items for user {user_id}")
            return warranty_items
            
        except Exception as e:
            self.log_error("_get_user_warranties", e)
            return []
    
    async def _extract_warranty_info(self, entity: Dict[str, Any], graph_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract warranty information from a product entity.
        
        Args:
            entity: Product entity data
            graph_data: Full knowledge graph data
            
        Returns:
            Warranty information dictionary or None
        """
        try:
            properties = entity.get('properties', {})
            
            # Get expiry date
            expiry_date_str = properties.get('expiry_date')
            if not expiry_date_str:
                return None
            
            # Parse expiry date
            expiry_date = self._parse_date(expiry_date_str)
            if not expiry_date:
                return None
            
            # Check if expiry is in the future
            if expiry_date <= datetime.now().date():
                return None
            
            # Calculate reminder date (2 days before expiry)
            reminder_date = expiry_date - timedelta(days=2)
            
            # Only create reminders for future dates
            if reminder_date <= datetime.now().date():
                return None
            
            return {
                "product_name": properties.get('name', 'Unknown Product'),
                "brand": properties.get('brand', 'Unknown Brand'),
                "warranty_period": properties.get('warranty_period', 'Unknown'),
                "expiry_date": expiry_date,
                "reminder_date": reminder_date,
                "receipt_id": graph_data.get('receipt_ids', ['unknown'])[0],
                "purchase_date": graph_data.get('created_at')
            }
            
        except Exception as e:
            self.log_error("_extract_warranty_info", e)
            return None
    
    async def _extract_warranty_info_from_product(self, product: Dict[str, Any], graph_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract warranty information from a product dictionary.
        
        Args:
            product: Product data dictionary
            graph_data: Full knowledge graph data
            
        Returns:
            Warranty information dictionary or None
        """
        try:
            # Get expiry date (prioritize expiry_date field, then warranty_end_date)
            expiry_date_str = product.get('expiry_date') or product.get('warranty_end_date')
            if not expiry_date_str:
                return None
            
            # Parse expiry date
            expiry_date = self._parse_date(expiry_date_str)
            if not expiry_date:
                return None
            
            # Check if expiry is in the future
            if expiry_date <= datetime.now().date():
                return None
            
            # Calculate reminder date (2 days before expiry)
            reminder_date = expiry_date - timedelta(days=2)
            
            # Only create reminders for future dates
            if reminder_date <= datetime.now().date():
                return None
            
            return {
                "product_name": product.get('name', 'Unknown Product'),
                "brand": product.get('brand', 'Unknown Brand'),
                "warranty_period": product.get('warranty_period', 'Unknown'),
                "expiry_date": expiry_date,
                "reminder_date": reminder_date,
                "receipt_id": graph_data.get('receipt_id', 'unknown'),
                "purchase_date": graph_data.get('created_at'),
                "has_warranty": product.get('warranty', False),
                "has_expiry": product.get('has_expiry', False),
                "category": product.get('category', 'Unknown'),
                "price": product.get('price', 0)
            }
            
        except Exception as e:
            self.log_error("_extract_warranty_info_from_product", e)
            return None
    
    async def _create_warranty_reminder(self, warranty: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a calendar reminder for a warranty expiration.
        
        Args:
            warranty: Warranty information dictionary
            
        Returns:
            Result of the calendar event creation
        """
        try:
            # Format the reminder details
            product_name = warranty["product_name"]
            brand = warranty["brand"]
            expiry_date = warranty["expiry_date"]
            reminder_date = warranty["reminder_date"]
            
            # Create event title
            title = f"Warranty Expiring Soon: {product_name}"
            
            # Create event description
            description = f"""
🛡️ WARRANTY EXPIRATION REMINDER

Product: {product_name}
Brand: {brand}
Warranty Period: {warranty.get('warranty_period', 'Unknown')}
Expiry Date: {expiry_date.strftime('%B %d, %Y')}

⚠️ Your warranty expires in 2 days!

Receipt ID: {warranty.get('receipt_id', 'Unknown')}
Purchase Date: {self._format_purchase_date(warranty.get('purchase_date'))}

📱 View in Raseed App for more details.
            """.strip()
            
            # Set reminder time (9:00 AM on the reminder date)
            start_datetime = f"{reminder_date.isoformat()}T09:00:00"
            end_datetime = f"{reminder_date.isoformat()}T09:30:00"
            
            # Create the calendar event using the GoogleCalendarAgent
            result = self.calendar_agent.create_calendar_event(
                title=title,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                description=description,
                location=""
            )
            
            return result
            
        except Exception as e:
            self.log_error("_create_warranty_reminder", e)
            return {
                "status": "error",
                "error_message": f"Failed to create warranty reminder: {str(e)}"
            }
    
    def _parse_date(self, date_str: str) -> Optional[datetime.date]:
        """
        Parse date string in various formats.
        
        Args:
            date_str: Date string to parse
            
        Returns:
            Parsed date or None
        """
        try:
            # Try ISO format first
            if 'T' in date_str:
                return datetime.fromisoformat(date_str.split('T')[0]).date()
            
            # Try standard date format
            return datetime.fromisoformat(date_str).date()
            
        except ValueError:
            try:
                # Try other common formats
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
                    try:
                        return datetime.strptime(date_str, fmt).date()
                    except ValueError:
                        continue
            except Exception:
                pass
            
        return None
    
    def _format_purchase_date(self, purchase_date_str: Optional[str]) -> str:
        """
        Format purchase date for display.
        
        Args:
            purchase_date_str: Purchase date string
            
        Returns:
            Formatted date string
        """
        if not purchase_date_str:
            return "Unknown"
        
        try:
            if 'T' in purchase_date_str:
                dt = datetime.fromisoformat(purchase_date_str.replace('+05:30', '+05:30'))
                return dt.strftime('%B %d, %Y')
            else:
                dt = datetime.fromisoformat(purchase_date_str)
                return dt.strftime('%B %d, %Y')
        except Exception:
            return purchase_date_str
    
    async def create_single_warranty_reminder(self, user_id: str, product_name: str) -> Dict[str, Any]:
        """
        Create a reminder for a specific warranty product.
        
        Args:
            user_id: The user ID
            product_name: Name of the product
            
        Returns:
            Result of the operation
        """
        try:
            warranty_items = await self._get_user_warranties(user_id)
            
            # Find the specific warranty
            target_warranty = None
            for warranty in warranty_items:
                if warranty["product_name"].lower() == product_name.lower():
                    target_warranty = warranty
                    break
            
            if not target_warranty:
                return {
                    "status": "error",
                    "error_message": f"Warranty for '{product_name}' not found"
                }
            
            result = await self._create_warranty_reminder(target_warranty)
            return result
            
        except Exception as e:
            self.log_error("create_single_warranty_reminder", e)
            return {
                "status": "error",
                "error_message": f"Failed to create warranty reminder: {str(e)}"
            }
    
    async def get_upcoming_warranty_expirations(self, user_id: str, days_ahead: int = 30) -> Dict[str, Any]:
        """
        Get warranties expiring within the specified number of days.
        
        Args:
            user_id: The user ID
            days_ahead: Number of days to look ahead (default 30)
            
        Returns:
            Dictionary with upcoming expirations
        """
        try:
            warranty_items = await self._get_user_warranties(user_id)
            
            # Filter warranties expiring within the specified timeframe
            cutoff_date = datetime.now().date() + timedelta(days=days_ahead)
            upcoming_expirations = []
            
            for warranty in warranty_items:
                if warranty["expiry_date"] <= cutoff_date:
                    days_until_expiry = (warranty["expiry_date"] - datetime.now().date()).days
                    warranty["days_until_expiry"] = days_until_expiry
                    upcoming_expirations.append(warranty)
            
            # Sort by expiry date
            upcoming_expirations.sort(key=lambda x: x["expiry_date"])
            
            return {
                "status": "success",
                "upcoming_expirations": upcoming_expirations,
                "count": len(upcoming_expirations)
            }
            
        except Exception as e:
            self.log_error("get_upcoming_warranty_expirations", e)
            return {
                "status": "error",
                "error_message": f"Failed to get upcoming expirations: {str(e)}"
            }
    
    async def get_warranty_products(self, user_id: str) -> Dict[str, Any]:
        """
        Get all products with warranty or expiry information for display in UI.
        
        Args:
            user_id: The user ID
            
        Returns:
            Dict containing warranty products information
        """
        try:
            self.logger.info(f"Getting warranty products for user: {user_id}")
            
            warranty_products = []
            
            # Get all knowledge graphs for the user from nested collection
            # Path: /users/{user_id}/knowledge_graphs/{kg_id}
            user_doc_ref = self.firestore_service.db.collection('users').document(user_id)
            graphs_collection = user_doc_ref.collection('knowledge_graphs')
            docs = graphs_collection.stream()
            
            for doc in docs:
                graph_data = doc.to_dict()
                
                # Products are stored directly in 'products' array, not in 'entities'
                products = graph_data.get('products', [])
                
                # Find products with warranties or expiry dates
                for product in products:
                    # Check if product has warranty or expiry information
                    has_warranty = product.get('warranty', False) or product.get('warranty_period') is not None
                    has_expiry = product.get('has_expiry', False) or product.get('expiry_date') is not None
                    
                    if has_warranty or has_expiry:
                        # Parse expiry date if available
                        expiry_date = None
                        days_until_expiry = None
                        
                        expiry_date_str = product.get('expiry_date') or product.get('warranty_end_date')
                        if expiry_date_str:
                            expiry_date = self._parse_date(expiry_date_str)
                            if expiry_date:
                                days_until_expiry = (expiry_date - datetime.now().date()).days
                        
                        product_info = {
                            "product_name": product.get('name', 'Unknown Product'),
                            "product_id": f"{doc.id}_{product.get('name', 'unknown')}",
                            "has_warranty": has_warranty,
                            "has_expiry": has_expiry,
                            "warranty_info": product.get('warranty_period'),
                            "expiry_date": expiry_date.isoformat() if expiry_date else None,
                            "days_until_expiry": days_until_expiry,
                            "is_expiring_soon": days_until_expiry is not None and days_until_expiry <= 30,
                            "purchase_date": graph_data.get('created_at'),
                            "brand": product.get('brand', 'Unknown'),
                            "category": product.get('category', 'Unknown'),
                            "price": product.get('price', 0),
                            "receipt_id": graph_data.get('receipt_id', doc.id),
                            "created_at": graph_data.get('created_at')
                        }
                        
                        warranty_products.append(product_info)
            
            # Sort by expiry date (closest first, then by product name)
            warranty_products.sort(key=lambda x: (
                x['days_until_expiry'] if x['days_until_expiry'] is not None else 9999,
                x['product_name']
            ))
            
            self.logger.info(f"Found {len(warranty_products)} warranty products for user {user_id}")
            
            return {
                "status": "success",
                "warranty_products": warranty_products,
                "count": len(warranty_products)
            }
            
        except Exception as e:
            self.log_error("get_warranty_products", e)
            return {
                "status": "error",
                "error_message": f"Failed to get warranty products: {str(e)}"
            }
