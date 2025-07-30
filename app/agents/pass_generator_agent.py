"""
Pass Generator Agent for creating Google Wallet passes from Knowledge Graph data.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from ..services.firestore_service import FirestoreService
from ..services.wallet import GoogleWalletService
from ..models.wallet import WalletEligibleItem, PassGenerationRequest, PassGenerationResponse
from ..utils.logging import LoggerMixin


class PassGeneratorAgent(LoggerMixin):
    """
    Agent responsible for:
    1. Fetching receipt and warranty data from Knowledge Graph
    2. Transforming KG data into wallet-compatible format
    3. Generating signed JWT tokens for Google Wallet
    4. Managing pass creation and status tracking
    """
    
    def __init__(self):
        self.firestore = FirestoreService()
        self.wallet_service = GoogleWalletService()
        self.logger.info("Pass Generator Agent initialized")
    
    async def get_eligible_wallet_items(self, user_id: str) -> List[WalletEligibleItem]:
        """
        Get all items eligible for Google Wallet from user's Knowledge Graph data.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of WalletEligibleItem objects
        """
        try:
            eligible_items = []
            
            # Get user's knowledge graph data from Firestore
            kg_data = await self._fetch_user_kg_data(user_id)
            
            if not kg_data:
                self.logger.warning(f"No knowledge graph data found for user {user_id}")
                return eligible_items
            
            # Process each knowledge graph entry
            for kg_id, kg_entry in kg_data.items():
                if not kg_entry.get('data', {}).get('graph_built', False):
                    continue  # Skip incomplete knowledge graphs
                
                # Add receipt as eligible item
                receipt_item = self._transform_receipt_to_wallet_item(kg_id, kg_entry)
                if receipt_item:
                    eligible_items.append(receipt_item)
                
                # Add warranty items
                warranty_items = self._transform_warranties_to_wallet_items(kg_id, kg_entry)
                eligible_items.extend(warranty_items)
            
            self.logger.info(f"Found {len(eligible_items)} eligible wallet items for user {user_id}")
            return eligible_items
            
        except Exception as e:
            self.log_error("get_eligible_wallet_items", e)
            return []
    
    async def generate_wallet_pass(self, request: PassGenerationRequest) -> PassGenerationResponse:
        """
        Generate a signed JWT token for Google Wallet.
        
        Args:
            request: Pass generation request
            
        Returns:
            PassGenerationResponse with JWT token or error
        """
        try:
            # Get the specific item data
            item_data = await self._get_item_data(request.item_id, request.user_id)
            
            if not item_data:
                return PassGenerationResponse(
                    success=False,
                    error=f"Item {request.item_id} not found or not eligible"
                )
            
            # Generate pass object based on type
            if request.pass_type == "receipt":
                pass_object = self.wallet_service.create_receipt_pass_object(item_data)
            elif request.pass_type == "warranty":
                pass_object = self.wallet_service.create_warranty_pass_object(item_data)
            else:
                return PassGenerationResponse(
                    success=False,
                    error=f"Unsupported pass type: {request.pass_type}"
                )
            
            # Insert object to Google Wallet first
            insert_success = self.wallet_service.insert_object_to_google_wallet(pass_object)
            
            if not insert_success:
                self.logger.warning("Failed to insert object to Google Wallet, but continuing with JWT generation")
            
            # Sign JWT token
            jwt_token = self.wallet_service.sign_jwt(pass_object)
            
            # Create wallet save URL
            wallet_url = self.wallet_service.create_wallet_save_url(jwt_token)
            
            # Update item status in Firestore (mark as added to wallet)
            await self._update_wallet_status(request.item_id, request.user_id, pass_object["id"])
            
            return PassGenerationResponse(
                success=True,
                jwt=jwt_token,
                pass_id=pass_object["id"],
                wallet_url=wallet_url
            )
            
        except Exception as e:
            self.log_error("generate_wallet_pass", e)
            return PassGenerationResponse(
                success=False,
                error=str(e)
            )
    
    async def _fetch_user_kg_data(self, user_id: str) -> Dict[str, Any]:
        """Fetch user's knowledge graph data from Firestore."""
        try:
            self.logger.info(f"Fetching KG data for user_id: {user_id}")
            
            # Query Firestore for user's knowledge graphs subcollection
            kg_collection_ref = self.firestore.db.collection('users').document(user_id).collection('knowledge_graphs')
            docs = kg_collection_ref.stream()
            
            kg_data = {}
            for doc in docs:
                if doc.exists:
                    doc_data = doc.to_dict()
                    # Only include documents that have complete graph data
                    if doc_data and doc_data.get('data', {}).get('graph_built', False):
                        kg_data[doc.id] = doc_data
                        self.logger.info(f"Found valid KG document: {doc.id} for user {user_id}")
            
            self.logger.info(f"Fetched {len(kg_data)} knowledge graph documents for user {user_id}")
            
            # If no data found for this user, check if there are similar users (for debugging)
            if not kg_data:
                self.logger.warning(f"No KG data found for user {user_id}")
                # Check for potential alternative user IDs (for debugging only)
                alt_users = []
                if user_id == "sample":
                    alt_users = ["sam", "flutter_user_1753337340086"]
                elif user_id == "sam":
                    alt_users = ["sample", "flutter_user_1753337340086"]
                
                for alt_user in alt_users:
                    try:
                        alt_kg_ref = self.firestore.db.collection('users').document(alt_user).collection('knowledge_graphs')
                        alt_docs = list(alt_kg_ref.stream())
                        if alt_docs:
                            self.logger.info(f"Found {len(alt_docs)} documents under alternative user: {alt_user}")
                    except:
                        pass
            
            return kg_data
            
        except Exception as e:
            self.log_error("_fetch_user_kg_data", e)
            return {}
    
    def _transform_receipt_to_wallet_item(self, kg_id: str, kg_entry: Dict[str, Any]) -> Optional[WalletEligibleItem]:
        """Transform knowledge graph receipt data to wallet item."""
        try:
            data = kg_entry.get('data', {})
            merchant_details = kg_entry.get('merchant_details', {})
            merchant = merchant_details.get('merchant', {})
            
            # Check wallet status from receipts array in KG data
            added_to_wallet = False
            wallet_pass_id = None
            receipts = kg_entry.get('receipts', [])
            for receipt in receipts:
                if receipt.get('receipt_id') == kg_id:
                    added_to_wallet = receipt.get('addedToWallet', False)
                    wallet_pass_id = receipt.get('walletPassId')
                    break
            
            # Parse transaction date
            created_at_str = data.get('created_at', '')
            transaction_date = None
            if created_at_str:
                try:
                    transaction_date = datetime.fromisoformat(created_at_str.replace('+05:30', '+05:30')).date()
                except:
                    transaction_date = datetime.now().date()
            
            return WalletEligibleItem(
                id=f"receipt_{kg_id}",
                title=data.get('receipt_name', 'Unknown Receipt'),
                subtitle=f"{data.get('receipt_summary', 'Receipt')} • {data.get('currency', 'USD')} {data.get('total_amount', 0.00):.2f}",
                item_type="receipt",
                
                # Receipt-specific fields
                receipt_id=kg_id,
                merchant_name=merchant.get('name', 'Unknown Merchant'),
                total_amount=data.get('total_amount', 0.00),
                currency=data.get('currency', 'USD'),
                transaction_date=transaction_date,
                item_count=kg_entry.get('analytics', {}).get('item_count', 0),
                
                # Wallet status from Firestore
                added_to_wallet=added_to_wallet,
                wallet_pass_id=wallet_pass_id
            )
            
        except Exception as e:
            self.log_error("_transform_receipt_to_wallet_item", e)
            return None
    
    def _transform_warranties_to_wallet_items(self, kg_id: str, kg_entry: Dict[str, Any]) -> List[WalletEligibleItem]:
        """Transform warranty products to wallet items."""
        warranty_items = []
        
        try:
            products = kg_entry.get('products', [])
            data = kg_entry.get('data', {})
            
            # Parse purchase date
            created_at_str = data.get('created_at', '')
            purchase_date = None
            if created_at_str:
                try:
                    purchase_date = datetime.fromisoformat(created_at_str.replace('+05:30', '+05:30')).date()
                except:
                    purchase_date = datetime.now().date()
            
            for product in products:
                if product.get('warranty', False) and product.get('expiry_date'):
                    # Generate warranty ID for comparison
                    warranty_id = f"warranty_{kg_id}_{product['name'].replace(' ', '_').lower()}"
                    
                    # Check wallet status from warranties array in KG data
                    added_to_wallet = False
                    wallet_pass_id = None
                    warranties = kg_entry.get('warranties', [])
                    for warranty in warranties:
                        if warranty.get('warranty_id') == warranty_id:
                            added_to_wallet = warranty.get('addedToWallet', False)
                            wallet_pass_id = warranty.get('walletPassId')
                            break
                    
                    # Parse expiry date
                    expiry_date = None
                    if product.get('expiry_date'):
                        try:
                            expiry_date = datetime.fromisoformat(product['expiry_date']).date()
                        except:
                            try:
                                expiry_date = datetime.strptime(product['expiry_date'], '%Y-%m-%d').date()
                            except:
                                expiry_date = None
                    
                    warranty_item = WalletEligibleItem(
                        id=warranty_id,
                        title=f"{product['name']} Warranty",
                        subtitle=f"Brand: {product.get('brand', 'Unknown')} • Expires: {product.get('expiry_date', 'Unknown')}",
                        item_type="warranty",
                        
                        # Warranty-specific fields
                        receipt_id=kg_id,
                        product_name=product['name'],
                        brand=product.get('brand', 'Unknown'),
                        warranty_period=product.get('warranty_period', 'Unknown'),
                        expiry_date=expiry_date,
                        purchase_date=purchase_date,
                        
                        # Wallet status from Firestore
                        added_to_wallet=added_to_wallet,
                        wallet_pass_id=wallet_pass_id
                    )
                    
                    warranty_items.append(warranty_item)
            
        except Exception as e:
            self.log_error("_transform_warranties_to_wallet_items", e)
        
        return warranty_items
    
    async def _get_item_data(self, item_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get specific item data for pass generation."""
        try:
            # Parse item ID to determine type and get data
            if item_id.startswith("receipt_"):
                receipt_id = item_id.replace("receipt_", "")
                return await self._get_receipt_data(receipt_id, user_id)
            elif item_id.startswith("warranty_"):
                return await self._get_warranty_data(item_id, user_id)
            
            return None
            
        except Exception as e:
            self.log_error("_get_item_data", e)
            return None
    
    async def _get_receipt_data(self, receipt_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get receipt data for pass generation."""
        try:
            kg_data = await self._fetch_user_kg_data(user_id)
            kg_entry = kg_data.get(receipt_id)
            
            if not kg_entry:
                return None
            
            data = kg_entry.get('data', {})
            merchant_details = kg_entry.get('merchant_details', {})
            merchant = merchant_details.get('merchant', {})
            
            # Parse transaction date
            created_at_str = data.get('created_at', '')
            transaction_date = 'Unknown date'
            if created_at_str:
                try:
                    dt = datetime.fromisoformat(created_at_str.replace('+05:30', '+05:30'))
                    transaction_date = dt.strftime('%B %d, %Y')
                except:
                    transaction_date = 'Unknown date'
            
            return {
                'receipt_id': receipt_id,
                'merchant_name': merchant.get('name', 'Unknown Merchant'),
                'total_amount': data.get('total_amount', 0.00),
                'currency': data.get('currency', 'USD'),
                'transaction_date': transaction_date,
                'item_count': kg_entry.get('analytics', {}).get('item_count', 0)
            }
            
        except Exception as e:
            self.log_error("_get_receipt_data", e)
            return None
    
    async def _get_warranty_data(self, item_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get warranty data for pass generation."""
        try:
            # Parse warranty item ID: warranty_{receipt_id}_{product_name}
            parts = item_id.split('_', 2)
            if len(parts) < 3:
                return None
            
            receipt_id = parts[1]
            product_name_key = parts[2]
            
            kg_data = await self._fetch_user_kg_data(user_id)
            kg_entry = kg_data.get(receipt_id)
            
            if not kg_entry:
                return None
            
            # Find the specific product
            products = kg_entry.get('products', [])
            target_product = None
            
            for product in products:
                if product['name'].replace(' ', '_').lower() == product_name_key:
                    target_product = product
                    break
            
            if not target_product or not target_product.get('warranty', False):
                return None
            
            # Parse dates
            data = kg_entry.get('data', {})
            created_at_str = data.get('created_at', '')
            purchase_date = 'Unknown'
            if created_at_str:
                try:
                    dt = datetime.fromisoformat(created_at_str.replace('+05:30', '+05:30'))
                    purchase_date = dt.strftime('%B %d, %Y')
                except:
                    purchase_date = 'Unknown'
            
            expiry_date = 'Unknown'
            if target_product.get('expiry_date'):
                try:
                    dt = datetime.fromisoformat(target_product['expiry_date'])
                    expiry_date = dt.strftime('%B %d, %Y')
                except:
                    try:
                        dt = datetime.strptime(target_product['expiry_date'], '%Y-%m-%d')
                        expiry_date = dt.strftime('%B %d, %Y')
                    except:
                        expiry_date = target_product['expiry_date']
            
            return {
                'receipt_id': receipt_id,
                'product_name': target_product['name'],
                'brand': target_product.get('brand', 'Unknown'),
                'warranty_period': target_product.get('warranty_period', 'Unknown'),
                'purchase_date': purchase_date,
                'expiry_date': expiry_date
            }
            
        except Exception as e:
            self.log_error("_get_warranty_data", e)
            return None
    
    async def _update_wallet_status(self, item_id: str, user_id: str, pass_id: str):
        """Update item status to indicate it's been added to wallet."""
        try:
            # Extract the actual ID based on item type
            if item_id.startswith("receipt_"):
                actual_id = item_id.replace("receipt_", "")
                item_type = "receipt"
            elif item_id.startswith("warranty_"):
                actual_id = item_id
                item_type = "warranty"
            else:
                self.logger.error(f"Unknown item type for ID: {item_id}")
                return
            
            # Update the wallet status in Firestore
            kg_collection = self.firestore.db.collection('users').document(user_id).collection('knowledge_graphs')
            
            # Find the document containing this item
            docs = kg_collection.stream()
            for doc in docs:
                doc_data = doc.to_dict()
                self.logger.info(f"Processing document {doc.id} for item {actual_id}")
                self.logger.info(f"Document keys: {list(doc_data.keys()) if doc_data else 'None'}")
                
                if item_type == "receipt":
                    # Check if this document IS the receipt we're looking for
                    if doc.id == actual_id:
                        # Initialize receipts array if it doesn't exist
                        if 'receipts' not in doc_data:
                            doc_data['receipts'] = []
                        
                        # Check if receipt already exists in array
                        receipt_found = False
                        for receipt in doc_data['receipts']:
                            if receipt.get('receipt_id') == actual_id:
                                # Update existing receipt
                                receipt['addedToWallet'] = True
                                receipt['walletPassId'] = pass_id
                                receipt['walletAddedAt'] = datetime.now().isoformat()
                                receipt_found = True
                                break
                        
                        # If receipt not found in array, add it
                        if not receipt_found:
                            doc_data['receipts'].append({
                                'receipt_id': actual_id,
                                'addedToWallet': True,
                                'walletPassId': pass_id,
                                'walletAddedAt': datetime.now().isoformat()
                            })
                        
                        # Update the document
                        doc.reference.update({'receipts': doc_data['receipts']})
                        self.logger.info(f"Updated wallet status for receipt {actual_id} with pass ID {pass_id}")
                        return
                            
                elif item_type == "warranty" and doc_data and 'warranties' in doc_data:
                    warranties = doc_data['warranties']
                    for warranty in warranties:
                        if warranty.get('warranty_id') == actual_id:
                            # Update the warranty with wallet status
                            warranty['addedToWallet'] = True
                            warranty['walletPassId'] = pass_id
                            warranty['walletAddedAt'] = datetime.now().isoformat()
                            
                            # Update the document
                            doc.reference.update({'warranties': warranties})
                            self.logger.info(f"Updated wallet status for warranty {actual_id} with pass ID {pass_id}")
                            return
            
            self.logger.warning(f"Could not find item {item_id} (actual_id: {actual_id}) to update wallet status")
            
        except Exception as e:
            self.log_error("_update_wallet_status", e)
