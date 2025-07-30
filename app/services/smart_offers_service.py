"""
Smart Offers Service - AI-powered offer detection and automatic pass generation.

This service analyzes user spending patterns and automatically creates Google Wallet passes
for better deals and offers from nearby shops when unnecessary spending is detected.
"""

import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import math

from .wallet import GoogleWalletService
from .firestore_service import FirestoreService
from .gemini_service import GeminiService
from ..utils.logging import LoggerMixin


class SmartOffersService(LoggerMixin):
    """Service for intelligent offer detection and automatic pass generation."""
    
    def __init__(self):
        self.wallet_service = GoogleWalletService()
        self.firestore = FirestoreService()
        self.gemini = GeminiService()
        
        # Sample nearby shops data (in real implementation, this would come from Maps API)
        self.nearby_shops = {
            "groceries": [
                {"name": "BigBasket", "discount": "20% off on groceries", "location": "0.5km away"},
                {"name": "Reliance Fresh", "discount": "15% off + free delivery", "location": "0.8km away"},
                {"name": "Spencer's", "discount": "Buy 2 Get 1 Free on essentials", "location": "1.2km away"}
            ],
            "food": [
                {"name": "Domino's", "discount": "40% off on orders above ₹500", "location": "0.3km away"},
                {"name": "McDonald's", "discount": "Buy 1 Get 1 Free burgers", "location": "0.7km away"},
                {"name": "KFC", "discount": "₹100 off on family meals", "location": "1.0km away"}
            ],
            "electronics": [
                {"name": "Croma", "discount": "₹2000 cashback on mobiles", "location": "2.0km away"},
                {"name": "Vijay Sales", "discount": "No cost EMI + exchange bonus", "location": "1.5km away"}
            ],
            "fashion": [
                {"name": "Pantaloons", "discount": "Flat 50% off on winter wear", "location": "1.8km away"},
                {"name": "Lifestyle", "discount": "Buy 3 Get 2 Free", "location": "2.2km away"}
            ]
        }
        
        self.logger.info("Smart Offers Service initialized")
    
    async def analyze_spending_and_create_offers(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Analyze user spending patterns and automatically create offer passes.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of created offer passes
        """
        try:
            self.logger.info(f"Analyzing spending patterns for user {user_id}")
            
            # Get user's financial data
            user_data = await self._get_user_spending_data(user_id)
            
            if not user_data or not user_data.get('transactions'):
                self.logger.info(f"No spending data found for user {user_id}")
                return []
            
            # Analyze spending with AI
            spending_analysis = await self._analyze_spending_patterns(user_data)
            
            # Detect unnecessary spending and potential savings
            offer_opportunities = await self._detect_offer_opportunities(spending_analysis)
            
            # Create offer passes automatically
            created_passes = []
            for opportunity in offer_opportunities:
                offer_pass = await self._create_offer_pass(user_id, opportunity)
                if offer_pass:
                    created_passes.append(offer_pass)
            
            self.logger.info(f"Created {len(created_passes)} smart offer passes for user {user_id}")
            return created_passes
            
        except Exception as e:
            self.logger.error(f"Error analyzing spending and creating offers: {e}")
            return []
    
    async def _get_user_spending_data(self, user_id: str) -> Dict[str, Any]:
        """Get user's spending data from Firestore."""
        try:
            # Get knowledge graphs from subcollection
            kg_collection_ref = self.firestore.db.collection('users').document(user_id).collection('knowledge_graphs')
            docs = kg_collection_ref.stream()
            
            transactions = []
            total_spent = 0
            categories = {}
            
            for doc in docs:
                if doc.exists:
                    doc_data = doc.to_dict()
                    if doc_data and doc_data.get('data'):
                        data = doc_data.get('data', {})
                        amount = data.get('total_amount', 0)
                        merchant = data.get('receipt_name', 'Unknown')
                        
                        # Categorize the transaction
                        category = self._categorize_merchant(merchant)
                        
                        transactions.append({
                            'amount': amount,
                            'merchant': merchant,
                            'category': category,
                            'date': data.get('created_at', ''),
                            'items': data.get('item_count', 0)
                        })
                        
                        total_spent += amount
                        categories[category] = categories.get(category, 0) + amount
            
            return {
                'user_id': user_id,
                'total_spent': total_spent,
                'transactions': transactions,
                'categories': categories,
                'transaction_count': len(transactions)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting user spending data: {e}")
            return {}
    
    def _categorize_merchant(self, merchant_name: str) -> str:
        """Categorize merchant based on name."""
        merchant_lower = merchant_name.lower()
        
        if any(word in merchant_lower for word in ['starbucks', 'coffee', 'cafe', 'domino', 'mcdonald', 'kfc', 'pizza']):
            return 'food'
        elif any(word in merchant_lower for word in ['grocery', 'supermarket', 'market', 'bigbasket', 'reliance']):
            return 'groceries'
        elif any(word in merchant_lower for word in ['electronics', 'mobile', 'laptop', 'croma', 'vijay']):
            return 'electronics'
        elif any(word in merchant_lower for word in ['fashion', 'clothes', 'pantaloons', 'lifestyle']):
            return 'fashion'
        else:
            return 'other'
    
    async def _analyze_spending_patterns(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to analyze spending patterns for unnecessary spending."""
        try:
            analysis_prompt = f"""
            Analyze this user's spending data and identify unnecessary or excessive spending patterns:
            
            Total spent: ₹{user_data.get('total_spent', 0)}
            Transactions: {user_data.get('transaction_count', 0)}
            
            Categories:
            {json.dumps(user_data.get('categories', {}), indent=2)}
            
            Recent transactions:
            {json.dumps(user_data.get('transactions', [])[:5], indent=2)}
            
            Identify:
            1. Categories with potentially excessive spending
            2. Merchants where user could get better deals
            3. Spending frequency that suggests habit formation
            4. Opportunities for savings with alternative options
            
            Respond in JSON format with analysis and recommendations.
            """
            
            # Use Gemini for analysis
            analysis_response = await self.gemini.generate_text_response(analysis_prompt)
            
            # Parse the response (for mock, return structured analysis)
            return {
                'excessive_categories': ['food'],  # Categories with high spending
                'frequent_merchants': ['Starbucks', 'McDonald\'s'],  # Often used merchants
                'potential_savings': 200,  # Estimated savings possible
                'recommendations': [
                    'Consider alternatives for frequent food purchases',
                    'Look for discount offers at nearby restaurants',
                    'Use grocery alternatives for better prices'
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing spending patterns: {e}")
            return {}
    
    async def _detect_offer_opportunities(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect specific offer opportunities based on analysis."""
        try:
            opportunities = []
            
            excessive_categories = analysis.get('excessive_categories', [])
            frequent_merchants = analysis.get('frequent_merchants', [])
            
            # Create opportunities for excessive spending categories
            for category in excessive_categories:
                if category in self.nearby_shops:
                    for shop in self.nearby_shops[category]:
                        opportunities.append({
                            'type': 'savings_opportunity',
                            'category': category,
                            'reason': f'High spending detected in {category}',
                            'shop': shop,
                            'priority': 'high',
                            'estimated_savings': '15-25%'
                        })
            
            # Create opportunities for frequent merchants
            for merchant in frequent_merchants:
                category = self._categorize_merchant(merchant)
                if category in self.nearby_shops:
                    for shop in self.nearby_shops[category]:
                        if shop['name'].lower() not in merchant.lower():
                            opportunities.append({
                                'type': 'alternative_option',
                                'category': category,
                                'reason': f'Frequent spending at {merchant}',
                                'shop': shop,
                                'priority': 'medium',
                                'estimated_savings': '10-20%'
                            })
            
            return opportunities[:3]  # Limit to top 3 opportunities
            
        except Exception as e:
            self.logger.error(f"Error detecting offer opportunities: {e}")
            return []
    
    async def _create_offer_pass(self, user_id: str, opportunity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a Google Wallet pass for an offer opportunity."""
        try:
            shop = opportunity['shop']
            category = opportunity['category']
            
            # Generate unique offer ID
            offer_id = f"offer_{user_id}_{shop['name'].lower().replace(' ', '_')}_{int(datetime.now().timestamp())}"
            
            # Create offer pass data
            offer_data = {
                'offer_id': offer_id,
                'shop_name': shop['name'],
                'discount': shop['discount'],
                'location': shop['location'],
                'category': category.title(),
                'reason': opportunity['reason'],
                'estimated_savings': opportunity['estimated_savings'],
                'valid_until': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
                'created_at': datetime.now().isoformat()
            }
            
            # Create Google Wallet pass object
            offer_pass_object = self._create_offer_pass_object(offer_data)
            
            # Insert into Google Wallet
            success = self.wallet_service.insert_object_to_google_wallet(offer_pass_object)
            
            if success:
                # Generate JWT for the pass
                jwt_token = self.wallet_service.sign_jwt(offer_pass_object)
                save_url = self.wallet_service.create_wallet_save_url(jwt_token)
                
                # Save offer to Firestore for tracking
                await self._save_offer_to_firestore(user_id, offer_data, save_url)
                
                self.logger.info(f"Created offer pass for {shop['name']} for user {user_id}")
                
                return {
                    'offer_id': offer_id,
                    'shop_name': shop['name'],
                    'discount': shop['discount'],
                    'save_url': save_url,
                    'estimated_savings': opportunity['estimated_savings'],
                    'reason': opportunity['reason']
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error creating offer pass: {e}")
            return None
    
    def _create_offer_pass_object(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Google Wallet generic object for an offer."""
        try:
            object_id = f"{self.wallet_service.issuer_id}.{offer_data['offer_id']}"
            
            generic_object = {
                "id": object_id,
                "classId": f"{self.wallet_service.issuer_id}.smart_offer_pass",
                "genericType": "GENERIC_TYPE_UNSPECIFIED",
                "hexBackgroundColor": "#4CAF50",  # Green for savings
                
                "cardTitle": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": "💰 Smart Savings Offer"
                    }
                },
                
                "header": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": offer_data['shop_name']
                    }
                },
                
                "subheader": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": offer_data['discount']
                    }
                },
                
                "textModulesData": [
                    {
                        "id": "text_module_1",
                        "header": "Why This Offer?",
                        "body": f"{offer_data['reason']} • Save {offer_data['estimated_savings']}"
                    },
                    {
                        "id": "text_module_2",
                        "header": "Location & Validity",
                        "body": f"{offer_data['location']} • Valid until {offer_data['valid_until']}"
                    },
                    {
                        "id": "text_module_3",
                        "header": "AI Recommendation",
                        "body": f"Raseed AI detected spending patterns in {offer_data['category']} and found this better deal for you!"
                    }
                ],
                
                "barcode": {
                    "type": "QR_CODE",
                    "value": f"raseed://offer/{offer_data['offer_id']}"
                },
                
                "linksModuleData": {
                    "uris": [{
                        "uri": f"https://raseed-app.com/offer/{offer_data['offer_id']}",
                        "description": "View Offer Details"
                    }]
                }
            }
            
            return generic_object
            
        except Exception as e:
            self.logger.error(f"Error creating offer pass object: {e}")
            raise
    
    async def _save_offer_to_firestore(self, user_id: str, offer_data: Dict[str, Any], save_url: str):
        """Save offer details to Firestore for tracking."""
        try:
            offer_doc = {
                **offer_data,
                'user_id': user_id,
                'save_url': save_url,
                'status': 'active',
                'created_at': datetime.now()
            }
            
            # Save to smart_offers collection
            self.firestore.db.collection('smart_offers').document(offer_data['offer_id']).set(offer_doc)
            
        except Exception as e:
            self.logger.error(f"Error saving offer to Firestore: {e}")
