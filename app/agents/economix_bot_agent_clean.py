"""
Economix Bot Agent - Clean implementation for user-specific financial data retrieval.

This agent fetches actual user financial data from Firestore:
- Retrieves data from /users/{user_id}/knowledge_graphs/
- Provides user-specific financial analysis  
- Returns actual transaction amounts and counts
"""

from typing import Dict, Any
from datetime import datetime

from ..services.firestore_service import FirestoreService
from ..services.gemini_service import GeminiService
from ..utils.logging import LoggerMixin


class EconomixBotAgent(LoggerMixin):
    """
    Clean Economix Bot Agent focused on user-specific data retrieval.
    """
    
    def __init__(self):
        self.firestore = FirestoreService()
        self.gemini = GeminiService()
        self.logger.info("🤖 Clean Economix Bot Agent initialized")
    
    async def process_text_message(self, user_id: str, message: str) -> str:
        """Process text message with user's actual financial data."""
        try:
            self.logger.info(f"🔍 Processing message for user: {user_id}")
            
            # Get user's actual financial data
            user_financial_data = await self._get_user_financial_data(user_id)
            
            # Log what we found
            total_spent = user_financial_data.get('total_spent', 0)
            transaction_count = user_financial_data.get('transaction_count', 0)
            self.logger.info(f"💰 User {user_id} data: ₹{total_spent} across {transaction_count} transactions")
            
            # Create AI prompt with actual user data
            ai_prompt = self._create_financial_prompt(user_financial_data, message)
            
            # Get AI response
            response = await self.gemini.generate_text_response(
                prompt=ai_prompt,
                context=[]
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"❌ Error processing message for user {user_id}: {e}")
            return "I apologize, but I'm having trouble accessing your financial data right now. Please try again."
    
    async def _get_user_financial_data(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch user's financial data from Firestore.
        Path: /users/{user_id}/knowledge_graphs/
        """
        try:
            self.logger.info(f"🔍 Fetching financial data for user: {user_id}")
            
            # Access user's knowledge graphs collection
            kg_collection_ref = self.firestore.db.collection('users').document(user_id).collection('knowledge_graphs')
            
            # Get all documents
            docs = kg_collection_ref.stream()
            
            # Process financial data
            total_spent = 0.0
            transactions = []
            categories = {}
            
            for doc in docs:
                if doc.exists:
                    doc_data = doc.to_dict()
                    
                    # Extract financial information from document
                    if doc_data and 'data' in doc_data:
                        data = doc_data['data']
                        
                        # Get transaction amount
                        amount = float(data.get('total_amount', 0))
                        merchant = data.get('receipt_name', 'Unknown Merchant')
                        date = data.get('created_at', datetime.now().isoformat())
                        
                        if amount > 0:  # Only include valid transactions
                            total_spent += amount
                            
                            # Categorize transaction
                            category = self._categorize_transaction(merchant)
                            categories[category] = categories.get(category, 0) + amount
                            
                            transactions.append({
                                'id': doc.id,
                                'amount': amount,
                                'merchant': merchant,
                                'date': date,
                                'category': category
                            })
                            
                            self.logger.info(f"📄 Found transaction: {merchant} - ₹{amount}")
            
            # Log summary
            self.logger.info(f"📊 Summary for {user_id}: ₹{total_spent} total, {len(transactions)} transactions")
            
            return {
                'user_id': user_id,
                'total_spent': total_spent,
                'transaction_count': len(transactions),
                'transactions': transactions,
                'categories': categories
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error fetching financial data for {user_id}: {e}")
            return {
                'user_id': user_id,
                'total_spent': 0.0,
                'transaction_count': 0,
                'transactions': [],
                'categories': {}
            }
    
    def _categorize_transaction(self, merchant_name: str) -> str:
        """Categorize transaction based on merchant name."""
        merchant_lower = merchant_name.lower()
        
        if any(word in merchant_lower for word in ['grocery', 'supermarket', 'market', 'mart']):
            return 'Groceries'
        elif any(word in merchant_lower for word in ['restaurant', 'cafe', 'coffee', 'food', 'dining']):
            return 'Food & Dining'
        elif any(word in merchant_lower for word in ['gas', 'fuel', 'petrol', 'transport']):
            return 'Transportation'
        elif any(word in merchant_lower for word in ['shopping', 'store', 'mall']):
            return 'Shopping'
        else:
            return 'Other'
    
    def _create_financial_prompt(self, financial_data: Dict[str, Any], user_message: str) -> str:
        """Create AI prompt with user's actual financial data."""
        
        user_id = financial_data.get('user_id', 'Unknown')
        total_spent = financial_data.get('total_spent', 0)
        transaction_count = financial_data.get('transaction_count', 0)
        categories = financial_data.get('categories', {})
        transactions = financial_data.get('transactions', [])
        
        # Build category breakdown
        category_breakdown = ""
        if categories:
            for category, amount in categories.items():
                percentage = (amount / total_spent * 100) if total_spent > 0 else 0
                category_breakdown += f"- {category}: ₹{amount:.2f} ({percentage:.1f}%)\n"
        else:
            category_breakdown = "No spending categories available yet."
        
        # Build recent transactions
        recent_transactions = ""
        if transactions:
            for tx in transactions[-5:]:  # Last 5 transactions
                recent_transactions += f"- {tx['merchant']}: ₹{tx['amount']:.2f}\n"
        else:
            recent_transactions = "No transactions recorded yet."
        
        prompt = f"""
You are Economix, an AI financial assistant for the Raseed app. You help users understand their spending and make smart financial decisions.

USER FINANCIAL DATA FOR {user_id}:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 **Financial Overview:**
- Total spent: ₹{total_spent:.2f}
- Number of transactions: {transaction_count}

📊 **Category Breakdown:**
{category_breakdown}

📋 **Recent Transactions:**
{recent_transactions}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

USER QUESTION: {user_message}

INSTRUCTIONS:
1. Use the ACTUAL financial data provided above
2. Give specific amounts and transaction counts
3. Provide helpful insights based on their real spending
4. Be conversational and helpful
5. If they have no data, encourage them to start tracking expenses

Please provide a helpful response using their actual financial information.
"""
        
        return prompt


# Create global instance
economix_bot_agent = EconomixBotAgent()
