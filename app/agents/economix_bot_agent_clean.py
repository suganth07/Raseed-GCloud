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
from ..services.real_data_validator import RealDataValidator
from ..utils.logging import LoggerMixin
from .question_classifier import EnhancedQuestionClassifier


class EconomixBotAgent(LoggerMixin):
    """
    Clean Economix Bot Agent focused on user-specific data retrieval.
    """
    
    def __init__(self):
        # Validate real credentials before initialization
        validator = RealDataValidator()
        validation_result = validator.validate_all_services()
        
        if not validation_result["all_valid"]:
            error_msg = "❌ CRITICAL: Cannot initialize bot without real credentials. Mock data not allowed."
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.firestore = FirestoreService()
        self.gemini = GeminiService()
        self.question_classifier = EnhancedQuestionClassifier()
        self.validator = validator
        
        self.logger.info("🤖 Clean Economix Bot Agent initialized with question classification and real data validation")
    
    async def process_text_message(self, user_id: str, message: str) -> str:
        """Process text message with user's actual financial data and intelligent classification."""
        try:
            self.logger.info(f"🔍 Processing message for user: {user_id}")
            
            # Validate that we can access real user data
            user_data_validation = await self.validator.validate_user_data_access(user_id)
            if not user_data_validation["validation_passed"]:
                self.logger.warning(f"⚠️ User {user_id} has no real financial data available")
                return (
                    "I notice you don't have any financial data connected yet. "
                    "Please upload some receipts or connect your accounts to get personalized insights!"
                )
            
            # Classify the user's question
            classification_result = await self.question_classifier.classify_question(message)
            intent = classification_result.intent.value if hasattr(classification_result.intent, 'value') else str(classification_result.intent)
            confidence = classification_result.confidence
            
            self.logger.info(f"🎯 Question classified as: {intent} (confidence: {confidence:.2f})")
            
            # Get user's actual financial data - REAL DATA ONLY
            user_financial_data = await self._get_user_financial_data(user_id)
            
            # Validate that the data is real (not empty or mock)
            if user_financial_data["transaction_count"] == 0:
                return (
                    "I see you're getting started with Raseed! Upload some receipts or "
                    "connect your financial accounts to get personalized insights about your spending."
                )
            
            # Log what we found
            total_spent = user_financial_data.get('total_spent', 0)
            transaction_count = user_financial_data.get('transaction_count', 0)
            self.logger.info(f"💰 User {user_id} REAL data: ₹{total_spent} across {transaction_count} transactions")
            
            # Create AI prompt with actual user data and intent context
            ai_prompt = self._create_financial_prompt(user_financial_data, message, classification_result)
            
            # Get AI response using REAL Gemini API
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
    
    def _create_financial_prompt(self, financial_data: Dict[str, Any], user_message: str, classification_result = None) -> str:
        """Create AI prompt with user's actual financial data and intent classification."""
        
        user_id = financial_data.get('user_id', 'Unknown')
        total_spent = financial_data.get('total_spent', 0)
        transaction_count = financial_data.get('transaction_count', 0)
        categories = financial_data.get('categories', {})
        transactions = financial_data.get('transactions', [])
        
        # Extract classification info
        intent = "GENERAL_INQUIRY"
        confidence = 0.0
        
        if classification_result:
            # Handle both dict and object formats
            if hasattr(classification_result, 'intent'):
                intent = classification_result.intent.value if hasattr(classification_result.intent, 'value') else str(classification_result.intent)
                confidence = classification_result.confidence
            else:
                intent = classification_result.get('intent', 'GENERAL_INQUIRY')
                confidence = classification_result.get('confidence', 0.0)
        
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
        
        # Create intent-specific guidance
        intent_guidance = ""
        if intent == "SPENDING_ANALYSIS":
            intent_guidance = "Focus on analyzing spending patterns, categories, and trends."
        elif intent == "BUDGET_MANAGEMENT":
            intent_guidance = "Provide budgeting advice and spending limit recommendations."
        elif intent == "CATEGORY_INQUIRY":
            intent_guidance = "Focus on specific spending categories and their breakdowns."
        elif intent == "TRANSACTION_SEARCH":
            intent_guidance = "Help find specific transactions or merchants."
        elif intent == "SAVINGS_ADVICE":
            intent_guidance = "Provide money-saving tips and recommendations."
        elif intent == "FINANCIAL_GOALS":
            intent_guidance = "Discuss financial planning and goal-setting strategies."
        else:
            intent_guidance = "Provide general financial assistance and guidance."

        prompt = f"""
You are Economix, an AI financial assistant for the Raseed app. You help users understand their spending and make smart financial decisions.

🤖 **QUESTION ANALYSIS:**
- Intent: {intent} (Confidence: {confidence:.1f})
- Guidance: {intent_guidance}

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
1. {intent_guidance}
2. Use the ACTUAL financial data provided above
3. Give specific amounts and transaction counts
4. Provide helpful insights based on their real spending
5. Be conversational and helpful
6. If they have no data, encourage them to start tracking expenses

Please provide a helpful response using their actual financial information and the identified intent.
"""
        
        return prompt


# Create global instance
economix_bot_agent = EconomixBotAgent()
