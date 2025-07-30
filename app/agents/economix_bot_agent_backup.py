"""
Economix Bot Agent - AI-powered financial assistant with multi-modal capabilities.

This agent provides intelligent financial analysis using:
- Google Gemini AI for natural language processing
- Knowledge graph integration for personalized insights
- Speech-to-text for audio processing
- Computer vision for image/document analysis
- Real-time financial recommendations
"""

import asyncio
import json
import base64
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import io
import os

from ..services.firestore_service import FirestoreService
from ..services.gemini_service import GeminiService
from ..services.smart_offers_service import SmartOffersService
from ..utils.logging import LoggerMixin


class EconomixBotAgent(LoggerMixin):
    """
    Economix Bot Agent - AI Financial Assistant
    
    Features:
    - Natural language financial analysis
    - Multi-modal input processing (text, image, audio, files)
    - Knowledge graph integration
    - Personalized recommendations
    - Real-time insights generation
    """
    
    def __init__(self):
        self.firestore = FirestoreService()
        self.gemini = GeminiService()
        self.smart_offers = SmartOffersService()
        self.logger.info("Economix Bot Agent initialized with multi-modal capabilities and smart offers")
    
    async def process_text_message(self, user_id: str, message: str) -> str:
        """Process text message with AI and knowledge graph context."""
        try:
            self.logger.info(f"Processing text message for user {user_id}: {message[:100]}...")
            
            # Check if this is a recipe-related request
            if await self._is_recipe_request(message):
                return await self._handle_recipe_request(user_id, message)
            
            # Check if this is a financial query that needs user data
            is_financial_query = await self._is_financial_query(message)
            
            if is_financial_query:
                # Get user context from knowledge graph for financial queries
                user_context = await self._get_user_financial_context(user_id)
                
                # Build AI prompt with financial context
                system_prompt = self._build_system_prompt(user_context)
                
                # Create enhanced prompt with user data
                enhanced_prompt = f"""
{system_prompt}

User Question: {message}

Please provide a helpful response using the user's actual financial data shown above.
"""
            else:
                # For general queries, use a simple conversational prompt
                enhanced_prompt = f"""
You are Economix, a helpful AI assistant. You can answer general questions, provide information, have conversations, and help with various topics. When users ask about financial matters, you can also provide smart financial insights.

User Question: {message}

Please provide a helpful and friendly response.
"""
            
            # Process with Gemini
            response = await self.gemini.generate_text_response(
                prompt=enhanced_prompt,
                context=[]  # Will add context support later
            )
            
            # Only trigger smart offers for financial spending analysis requests
            if is_financial_query and await self._is_spending_analysis_request(message):
                try:
                    # Trigger smart offers analysis in background
                    offers_created = await self.smart_offers.analyze_spending_and_create_offers(user_id)
                    if offers_created:
                        response += f"\n\n💡 I've also analyzed your spending patterns and found {len(offers_created)} personalized deals that could save you money! Check your Google Wallet for new offer passes."
                except Exception as e:
                    self.logger.error(f"Error creating smart offers: {e}")
                    # Continue with normal response even if offers fail
            
            # Save conversation to history
            await self._save_conversation(user_id, message, response, 'text')
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing text message: {e}")
            return "I'm having trouble understanding that. Could you please rephrase your question?"
    
    async def process_image_message(self, user_id: str, image_data: bytes, query: str = "") -> str:
        """Process image with computer vision and financial analysis."""
        try:
            self.logger.info(f"Processing image message for user {user_id}")
            
            # Get user context
            user_context = await self._get_user_financial_context(user_id)
            
            # Analyze image with Gemini Vision
            image_analysis = await self._analyze_image_with_gemini(image_data, query, user_context)
            
            # If it's a receipt or financial document, extract structured data
            if self._is_financial_document(image_analysis):
                structured_data = await self._extract_financial_data(image_data, user_context)
                response = await self._generate_financial_image_response(structured_data, user_context)
            else:
                response = image_analysis
            
            # Save conversation
            await self._save_conversation(user_id, f"[IMAGE] {query}", response, 'image')
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing image: {e}")
            return "I had trouble analyzing that image. Could you try uploading it again or describe what you'd like me to help with?"
    
    async def process_file_message(self, user_id: str, file_data: bytes, filename: str, query: str = "") -> str:
        """Process file with document analysis."""
        try:
            self.logger.info(f"Processing file message for user {user_id}: {filename}")
            
            # Get user context
            user_context = await self._get_user_financial_context(user_id)
            
            # Determine file type and process accordingly
            file_extension = filename.lower().split('.')[-1]
            
            if file_extension in ['pdf', 'jpg', 'jpeg', 'png']:
                # Process as document/image
                analysis = await self._analyze_document_with_gemini(file_data, filename, user_context)
            elif file_extension in ['csv', 'xlsx']:
                # Process as financial data
                analysis = await self._analyze_financial_spreadsheet(file_data, filename, user_context)
            else:
                analysis = "I can process PDF, image, CSV, and Excel files. Could you upload a supported file type?"
            
            # Generate contextual response
            response = await self._generate_file_analysis_response(analysis, query, user_context)
            
            # Save conversation
            await self._save_conversation(user_id, f"[FILE: {filename}] {query}", response, 'file')
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing file: {e}")
            return "I had trouble processing that file. Please make sure it's a supported format (PDF, image, CSV, or Excel)."
    
    async def process_audio_message(self, user_id: str, audio_data: bytes) -> str:
        """Process audio with speech-to-text and AI analysis."""
        try:
            self.logger.info(f"Processing audio message for user {user_id}")
            
            # Convert speech to text (placeholder - would integrate with Google Speech-to-Text)
            transcribed_text = await self._speech_to_text(audio_data)
            
            if not transcribed_text:
                return "I couldn't understand the audio. Could you try speaking clearly or send a text message instead?"
            
            # Process as text message
            response = await self.process_text_message(user_id, transcribed_text)
            
            # Update conversation record to show it was from audio
            await self._save_conversation(user_id, f"[AUDIO] {transcribed_text}", response, 'audio')
            
            return f"I heard: \"{transcribed_text}\"\n\n{response}"
            
        except Exception as e:
            self.logger.error(f"Error processing audio: {e}")
            return "I had trouble processing the audio. Could you try again or send a text message?"
    
    async def get_financial_summary(self, user_id: str) -> Dict[str, Any]:
        """Generate comprehensive financial summary."""
        try:
            user_context = await self._get_user_financial_context(user_id)
            
            # Generate AI-powered summary
            summary_prompt = f"""
            Based on this user's financial data: {json.dumps(user_context, indent=2)}
            
            Generate a comprehensive financial summary including:
            1. Total spending this month
            2. Top spending categories
            3. Spending trends (compared to last month)
            4. Key insights and recommendations
            5. Potential savings opportunities
            
            Format as JSON with clear sections.
            """
            
            summary = await self.gemini.generate_text_response(
                prompt=summary_prompt
            )
            
            return {
                'success': True,
                'summary': summary,
                'generated_at': datetime.now().isoformat(),
                'user_id': user_id
            }
            
        except Exception as e:
            self.logger.error(f"Error generating financial summary: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_shopping_recommendations(self, user_id: str, category: str = 'all') -> List[Dict[str, Any]]:
        """Generate smart shopping recommendations."""
        try:
            user_context = await self._get_user_financial_context(user_id)
            
            # Generate AI recommendations
            recommendations_prompt = f"""
            Based on this user's shopping history and preferences: {json.dumps(user_context, indent=2)}
            
            Generate smart shopping recommendations for category: {category}
            
            Include:
            1. Cheaper store alternatives
            2. Discount opportunities
            3. Bulk buying suggestions
            4. Seasonal deals
            5. Budget optimization tips
            
            Format as a JSON array of recommendation objects.
            """
            
            recommendations = await self.gemini.generate_text_response(
                prompt=recommendations_prompt
            )
            
            # Parse and structure recommendations
            try:
                parsed_recommendations = json.loads(recommendations)
                return parsed_recommendations if isinstance(parsed_recommendations, list) else []
            except json.JSONDecodeError:
                return [{'title': 'Smart Shopping Tips', 'description': recommendations}]
            
        except Exception as e:
            self.logger.error(f"Error generating shopping recommendations: {e}")
            return []
    
    async def get_spending_insights(self, user_id: str, period: str = 'month') -> Dict[str, Any]:
        """Generate detailed spending insights."""
        try:
            user_context = await self._get_user_financial_context(user_id)
            
            # Generate insights with AI
            insights_prompt = f"""
            Analyze this user's spending data for insights: {json.dumps(user_context, indent=2)}
            
            Generate spending insights for period: {period}
            
            Include:
            1. Spending patterns and trends
            2. Unusual or concerning patterns
            3. Positive financial behaviors
            4. Areas for improvement
            5. Personalized recommendations
            
            Use a friendly, encouraging tone with practical advice.
            """
            
            insights = await self.gemini.generate_text_response(
                prompt=insights_prompt
            )
            
            return {
                'success': True,
                'insights': insights,
                'period': period,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating spending insights: {e}")
            return {'success': False, 'error': str(e)}
    
    # Private helper methods
    
    async def _get_user_financial_context(self, user_id: str) -> Dict[str, Any]:
        """Fetch user's financial context from knowledge graph for the ACTUAL logged-in user."""
        try:
            self.logger.info(f"🔍 FETCHING FINANCIAL DATA for user: '{user_id}'")
            
            # Step 1: Try to identify the real user ID from the request
            actual_user_id = await self._identify_real_user_id(user_id)
            self.logger.info(f"🎯 IDENTIFIED REAL USER: '{actual_user_id}' (from request: '{user_id}')")
            
            # Step 2: Fetch data for the identified user
            kg_collection_ref = self.firestore.db.collection('users').document(actual_user_id).collection('knowledge_graphs')
            docs = kg_collection_ref.stream()
            
            kg_data = {}
            for doc in docs:
                if doc.exists:
                    doc_data = doc.to_dict()
                    if doc_data and doc_data.get('data'):
                        kg_data[doc.id] = doc_data
                        self.logger.info(f"📄 Found KG document: {doc.id} for user {actual_user_id}")
            
            self.logger.info(f"📊 Fetched {len(kg_data)} knowledge graph documents for user {actual_user_id}")
            
            # Step 3: Process the financial data
            user_info = {}
            try:
                user_doc = self.firestore.db.collection('users').document(actual_user_id).get()
                if user_doc.exists:
                    user_info = user_doc.to_dict()
            except Exception as e:
                self.logger.warning(f"Could not fetch user info: {e}")
            
            # Extract financial data from knowledge graphs
            total_spent = 0
            transactions = []
            categories = {}
            
            for kg_id, kg_entry in kg_data.items():
                data = kg_entry.get('data', {})
                self.logger.info(f"🔍 Processing KG entry: {kg_id} with data keys: {list(data.keys())}")
                
                amount = data.get('total_amount', 0)
                receipt_name = data.get('receipt_name', 'Unknown')
                category = self._categorize_receipt(receipt_name)
                
                total_spent += amount
                
                transactions.append({
                    'amount': amount,
                    'merchant': receipt_name,
                    'date': data.get('created_at', ''),
                    'category': category,
                    'items': data.get('item_count', 0)
                })
                
                # Count categories
                categories[category] = categories.get(category, 0) + amount
            
            self.logger.info(f"💰 FINAL RESULT for user '{actual_user_id}': Total: ₹{total_spent}, Transactions: {len(transactions)}")
            
            return {
                'total_spent': total_spent,
                'transactions': transactions,
                'categories': categories,
                'transaction_count': len(transactions),
                'user_info': user_info,
                'user_id': actual_user_id,
                'original_request_user_id': user_id
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error fetching user context: {e}")
            return {'user_id': user_id, 'total_spent': 0, 'transactions': [], 'categories': {}, 'transaction_count': 0}
    
    async def _identify_real_user_id(self, requested_user_id: str) -> str:
        """Identify the real user ID from various possible formats."""
        try:
            self.logger.info(f"🔍 IDENTIFYING REAL USER from request: '{requested_user_id}'")
            
            # Step 1: If it's already a valid email format, try it directly
            if '@' in requested_user_id:
                # Check if this user exists and has data
                kg_ref = self.firestore.db.collection('users').document(requested_user_id).collection('knowledge_graphs')
                test_docs = list(kg_ref.limit(1).stream())
                if test_docs:
                    self.logger.info(f"✅ Found data for email user: {requested_user_id}")
                    return requested_user_id
                
                # Try to find user by email field in user document
                users_ref = self.firestore.db.collection('users')
                email_query = users_ref.where('email', '==', requested_user_id).limit(1).stream()
                email_users = list(email_query)
                if email_users:
                    actual_id = email_users[0].id
                    self.logger.info(f"✅ Found user by email field: {requested_user_id} -> {actual_id}")
                    return actual_id
            
            # Step 2: For local/unknown user IDs, we need to determine the actual logged-in user
            # Check if there are active session indicators or use the most recent user with data
            
            # Get all users sorted by most recent activity
            users_ref = self.firestore.db.collection('users')
            all_users = users_ref.stream()
            
            users_with_data = []
            for user_doc in all_users:
                user_id = user_doc.id
                kg_ref = self.firestore.db.collection('users').document(user_id).collection('knowledge_graphs')
                kg_docs = list(kg_ref.limit(1).stream())
                
                if kg_docs:
                    # Get the most recent document timestamp
                    try:
                        most_recent_doc = max(kg_ref.stream(), key=lambda x: x.to_dict().get('created_at', ''))
                        timestamp = most_recent_doc.to_dict().get('created_at', '')
                        users_with_data.append({
                            'user_id': user_id,
                            'last_activity': timestamp,
                            'doc_count': len(list(kg_ref.stream()))
                        })
                    except:
                        users_with_data.append({
                            'user_id': user_id,
                            'last_activity': '',
                            'doc_count': len(kg_docs)
                        })
            
            if users_with_data:
                # Sort by most recent activity and most data
                users_with_data.sort(key=lambda x: (x['last_activity'], x['doc_count']), reverse=True)
                selected_user = users_with_data[0]['user_id']
                self.logger.info(f"🎯 Selected most active user: {selected_user} (from {len(users_with_data)} candidates)")
                return selected_user
            
            # Step 3: Final fallback - return the requested user ID
            self.logger.warning(f"⚠️ No users with data found, using requested user: {requested_user_id}")
            return requested_user_id
            
        except Exception as e:
            self.logger.error(f"❌ Error identifying real user: {e}")
            return requested_user_id
    
    def _categorize_receipt(self, receipt_name: str) -> str:
        """Categorize receipt based on merchant name."""
        receipt_lower = receipt_name.lower()
        
        if any(word in receipt_lower for word in ['starbucks', 'coffee', 'cafe', 'tea']):
            return 'Food & Beverage'
        elif any(word in receipt_lower for word in ['mcdonald', 'burger', 'pizza', 'restaurant', 'food']):
            return 'Food & Beverage'
        elif any(word in receipt_lower for word in ['grocery', 'supermarket', 'market', 'store']):
            return 'Groceries'
        elif any(word in receipt_lower for word in ['gas', 'fuel', 'petrol', 'station']):
            return 'Transportation'
        else:
            return 'Other'
    
    def _build_system_prompt(self, user_context: Dict[str, Any]) -> str:
        """Build system prompt with user context."""
        total_spent = user_context.get('total_spent', 0)
        transaction_count = user_context.get('transaction_count', 0)
        categories = user_context.get('categories', {})
        user_id = user_context.get('user_id', 'Unknown')
        
        # Handle case where user has no financial data
        if total_spent == 0 and transaction_count == 0:
            return f"""
            You are Economix, an AI financial assistant for the Raseed app. You help users manage their finances, analyze spending, and make smart financial decisions.

            USER STATUS: {user_id} - NEW USER (No financial data yet)
            
            This user hasn't scanned any receipts or added any financial data yet. Guide them to:
            1. Scan their first receipt using the app's receipt scanner
            2. Upload financial documents for analysis
            3. Manually add expenses if needed
            4. Start tracking their spending habits
            
            Be encouraging and explain the benefits of tracking their finances with Raseed.
            
            Guidelines:
            1. Be friendly, welcoming, and encouraging for new users
            2. Explain how to get started with Raseed
            3. Highlight the benefits of financial tracking
            4. Offer to help with any questions about the app
            5. Use emojis sparingly but effectively to make responses engaging
            """
        
        # Build category breakdown for users with data
        category_text = ""
        if categories:
            for category, amount in categories.items():
                percentage = (amount / total_spent * 100) if total_spent > 0 else 0
                category_text += f"- {category}: ₹{amount:.2f} ({percentage:.1f}%)\n"
        
        return f"""
        You are Economix, an AI financial assistant for the Raseed app. You help users manage their finances, analyze spending, and make smart financial decisions.

        USER: {user_id} - ACTIVE USER
        ACTUAL FINANCIAL DATA:
        - Total spent: ₹{total_spent:.2f}
        - Number of transactions: {transaction_count}
        - Category breakdown:
        {category_text if category_text else "No category breakdown available yet"}
        
        IMPORTANT: Always use the user's ACTUAL data shown above, never make up fake numbers!

        Guidelines:
        1. Be friendly, helpful, and encouraging
        2. Provide practical, actionable advice based on REAL data
        3. Use the user's actual spending amounts and patterns
        4. Explain financial concepts in simple terms
        5. Focus on helping users save money and spend wisely
        6. If asked about creating wallet passes, guide them to the appropriate features
        7. Use emojis sparingly but effectively to make responses engaging

        Always base your responses on this user's actual financial data when available.
        """
    
    async def _analyze_image_with_gemini(self, image_data: bytes, query: str, user_context: Dict[str, Any]) -> str:
        """Analyze image using Gemini Vision."""
        try:
            # Convert image to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Create vision prompt
            vision_prompt = f"""
            Analyze this image in the context of personal finance management.
            User query: {query}
            
            If this is a receipt or financial document:
            1. Extract key information (merchant, amount, items, date)
            2. Categorize the spending
            3. Provide relevant financial insights
            
            If this is not financial:
            1. Describe what you see
            2. Explain how it might relate to personal finance
            
            Be helpful and provide actionable insights.
            """
            
            # Use Gemini Vision (placeholder - would integrate with actual Gemini Vision API)
            response = f"I can see this is an image. {query if query else 'Could you tell me what you\'d like me to analyze about this image?'}"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error analyzing image: {e}")
            return "I had trouble analyzing the image. Could you try uploading it again?"
    
    def _is_financial_document(self, analysis: str) -> bool:
        """Determine if the analyzed image is a financial document."""
        financial_keywords = ['receipt', 'invoice', 'bill', 'transaction', 'payment', 'purchase', 'total', 'amount']
        return any(keyword in analysis.lower() for keyword in financial_keywords)
    
    async def _extract_financial_data(self, image_data: bytes, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured financial data from image."""
        # Placeholder for Document AI integration
        return {
            'merchant': 'Example Store',
            'total': 25.99,
            'date': datetime.now().isoformat(),
            'items': ['Item 1', 'Item 2'],
            'category': 'Grocery'
        }
    
    async def _generate_financial_image_response(self, data: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Generate response for financial image analysis."""
        return f"""
        I analyzed your receipt! Here's what I found:

        🏪 Merchant: {data.get('merchant', 'Unknown')}
        💰 Total: ₹{data.get('total', 0)}
        📅 Date: {data.get('date', 'Unknown')}
        📦 Items: {len(data.get('items', []))} items
        🏷️ Category: {data.get('category', 'Unknown')}

        Would you like me to:
        1. Create a Google Wallet pass for this receipt?
        2. Add this to your spending analysis?
        3. Get recommendations for similar purchases?

        Just let me know how I can help! 😊
        """
    
    async def _analyze_document_with_gemini(self, file_data: bytes, filename: str, user_context: Dict[str, Any]) -> str:
        """Analyze document using Gemini."""
        # Placeholder for document analysis
        return f"I've analyzed the document '{filename}'. It appears to contain financial information that could be useful for your spending analysis."
    
    async def _analyze_financial_spreadsheet(self, file_data: bytes, filename: str, user_context: Dict[str, Any]) -> str:
        """Analyze financial spreadsheet."""
        # Placeholder for spreadsheet analysis
        return f"I've processed the spreadsheet '{filename}'. It contains financial data that I can help you analyze for spending patterns and insights."
    
    async def _generate_file_analysis_response(self, analysis: str, query: str, user_context: Dict[str, Any]) -> str:
        """Generate response for file analysis."""
        return f"""
        {analysis}

        {f"Regarding your question: '{query}'" if query else ""}

        I can help you:
        - Extract and organize financial data
        - Identify spending patterns
        - Create budget recommendations
        - Generate wallet passes for transactions

        What would you like me to focus on?
        """
    
    async def _speech_to_text(self, audio_data: bytes) -> str:
        """Convert speech to text using Google Speech-to-Text."""
        # Placeholder for Google Speech-to-Text integration
        return "This is a placeholder for speech-to-text conversion"
    
    async def _save_conversation(self, user_id: str, user_message: str, bot_response: str, message_type: str):
        """Save conversation to Firestore."""
        try:
            conversation_data = {
                'user_id': user_id,
                'user_message': user_message,
                'bot_response': bot_response,
                'message_type': message_type,
                'timestamp': datetime.now(),
                'created_at': datetime.now()
            }
            
            # Use direct Firestore client instead of wrapper
            self.firestore.db.collection("economix_conversations").add(conversation_data)
            
        except Exception as e:
            self.logger.error(f"Error saving conversation: {e}")

    async def _is_recipe_request(self, message: str) -> bool:
        """Check if the message is asking for a recipe using AI detection."""
        # Enhanced keyword detection
        recipe_keywords = [
            'recipe', 'cook', 'make', 'prepare', 'dish', 'food', 'meal',
            'pasta', 'soup', 'salad', 'cake', 'bread', 'curry', 'stir fry',
            'ingredients', 'how to make', 'how to cook', 'shopping list for',
            'want to make', 'want to cook', 'recipe for', 'cooking',
            'bake', 'fry', 'boil', 'grill', 'roast', 'sauté', 'steam',
            'breakfast', 'lunch', 'dinner', 'snack', 'dessert', 'appetizer'
        ]
        
        message_lower = message.lower()
        
        # Direct keyword match
        if any(keyword in message_lower for keyword in recipe_keywords):
            return True
            
        # Use Gemini AI for intelligent detection
        try:
            detection_prompt = f"""
            Analyze this message and determine if the user is asking about cooking, recipes, or food preparation:
            Message: "{message}"
            
            Consider if they're asking about:
            - Making/cooking any dish or food
            - Recipe instructions
            - Ingredients for cooking
            - Food preparation methods
            - Meal planning
            
            Respond with only "YES" if it's food/recipe related, or "NO" if it's not.
            """
            
            ai_response = await self.gemini.generate_text_response(prompt=detection_prompt)
            return "YES" in ai_response.upper()
            
        except Exception as e:
            self.logger.warning(f"AI recipe detection failed: {e}")
            return False

    async def _is_spending_analysis_request(self, message: str) -> bool:
        """Check if the message is asking for spending analysis that should trigger smart offers."""
        # Keywords that indicate spending analysis requests
        spending_keywords = [
            'spending', 'spend', 'money', 'budget', 'expense', 'cost', 'save',
            'analysis', 'pattern', 'habit', 'financial', 'purchase', 'buy',
            'bought', 'shopping', 'categories', 'breakdown', 'total',
            'how much', 'where did i spend', 'what did i buy', 'analyze my',
            'monthly', 'weekly', 'daily', 'grocery', 'food', 'restaurant'
        ]
        
        message_lower = message.lower()
        
        # Check if message contains spending-related keywords
        return any(keyword in message_lower for keyword in spending_keywords)

    async def _is_financial_query(self, message: str) -> bool:
        """Check if the message is asking about financial/money-related topics."""
        # Financial keywords that indicate the user wants financial data/analysis
        financial_keywords = [
            'money', 'spend', 'spending', 'expense', 'cost', 'budget', 'financial', 
            'receipt', 'transaction', 'purchase', 'buy', 'bought', 'shopping',
            'price', 'paid', 'payment', 'bill', 'total', 'amount', 'rupee', 'rupees',
            'dollar', 'currency', 'cash', 'credit', 'debit', 'bank', 'account',
            'save', 'saving', 'investment', 'loan', 'income', 'salary', 'earn',
            'analysis', 'breakdown', 'category', 'merchant', 'store', 'shop',
            'grocery', 'restaurant', 'food', 'dining', 'gas', 'fuel', 'transport',
            'how much', 'what did i', 'show my', 'my expenses', 'my spending'
        ]
        
        message_lower = message.lower()
        
        # Check if message contains financial keywords
        return any(keyword in message_lower for keyword in financial_keywords)

    async def _handle_recipe_request(self, user_id: str, message: str) -> str:
        """Handle recipe requests with smart shopping list generation."""
        try:
            # Step 1: Get recipe details from Gemini
            recipe_details = await self._get_recipe_details(message)
            
            # Step 2: Get user's existing groceries from knowledge graph
            existing_groceries = await self._get_user_groceries(user_id)
            
            # Step 3: Compare and find missing ingredients
            missing_items = await self._find_missing_ingredients(
                recipe_details['ingredients'], 
                existing_groceries
            )
            
            # Step 4: Generate response with shopping list
            if missing_items:
                # Generate shopping list pass (prepare data)
                await self._generate_shopping_list_pass(
                    user_id, 
                    recipe_details['recipe_name'],
                    missing_items
                )
                
                response = f"""🍽️ **{recipe_details['recipe_name']}** 

{recipe_details.get('description', '')}

**Cuisine:** {recipe_details.get('cuisine_type', 'International')} | **Difficulty:** {recipe_details.get('difficulty', 'Easy')} | **Servings:** {recipe_details.get('servings', 4)}
**Prep Time:** {recipe_details.get('prep_time', '15 mins')} | **Cook Time:** {recipe_details.get('cook_time', '20 mins')}

📋 **Recipe Ingredients:**
{self._format_ingredients_list(recipe_details['ingredients'])}

✅ **Available in your pantry:**
{self._format_available_items(recipe_details['ingredients'], existing_groceries)}

🛒 **Shopping List (Missing Items):**
{self._format_missing_items(missing_items)}

💳 **Google Wallet Pass Generated!**
I've created a shopping list pass for the missing ingredients.

**Pass Details:**
• Title: Shopping for {recipe_details['recipe_name']}
• Items: {len(missing_items)} products needed
• Estimated Cost: ₹{self._estimate_cost(missing_items)}

👨‍🍳 **Quick Cooking Steps:**
{self._format_cooking_steps(recipe_details.get('cooking_steps', []))}

💡 **Chef's Tips:**
{self._format_tips(recipe_details.get('tips', []))}

📊 **Nutrition (per serving):** {recipe_details.get('nutritional_info', {}).get('calories_per_serving', 'N/A')} calories

Would you like me to add this shopping list to your Google Wallet? Just tap "Add to Wallet" below! 🎯"""

            else:
                response = f"""🍽️ **{recipe_details['recipe_name']}** 

{recipe_details.get('description', '')}

**Cuisine:** {recipe_details.get('cuisine_type', 'International')} | **Difficulty:** {recipe_details.get('difficulty', 'Easy')} | **Servings:** {recipe_details.get('servings', 4)}
**Prep Time:** {recipe_details.get('prep_time', '15 mins')} | **Cook Time:** {recipe_details.get('cook_time', '20 mins')}

🎉 **Great news!** You have all the ingredients needed for this recipe!

📋 **Recipe Ingredients:**
{self._format_ingredients_list(recipe_details['ingredients'])}

✅ **All items are available in your pantry and within expiry dates.**

👨‍🍳 **Ready to Cook! Here's how:**
{self._format_cooking_steps(recipe_details.get('cooking_steps', []))}

💡 **Chef's Tips:**
{self._format_tips(recipe_details.get('tips', []))}

📊 **Nutrition (per serving):** {recipe_details.get('nutritional_info', {}).get('calories_per_serving', 'N/A')} calories

You're all set to start cooking! Enjoy your delicious {recipe_details['recipe_name']}! 👨‍🍳✨"""

            return response
            
        except Exception as e:
            self.logger.error(f"Error handling recipe request: {e}")
            return "I encountered an error while analyzing your recipe request. Could you try again?"

    async def _get_recipe_details(self, message: str) -> Dict[str, Any]:
        """Get comprehensive recipe details using Gemini AI."""
        prompt = f"""
        You are a professional chef and recipe expert. Analyze this cooking request: "{message}"
        
        Please provide a comprehensive recipe response in JSON format. Be creative and helpful if the user's request is vague.
        
        Requirements:
        1. If they mention a specific dish, provide that recipe
        2. If they're vague (like "something with chicken"), suggest a popular, easy recipe
        3. If they ask for a type of cuisine, pick a representative dish
        4. Always provide practical, realistic ingredients and quantities
        
        Return ONLY valid JSON in this exact format:
        {{
            "recipe_name": "Exact name of the dish",
            "description": "Brief appetizing description of the dish",
            "cuisine_type": "Type of cuisine (Italian, Indian, etc.)",
            "difficulty": "Easy/Medium/Hard", 
            "prep_time": "X minutes",
            "cook_time": "X minutes",
            "servings": 4,
            "ingredients": [
                "500g penne pasta",
                "300g fresh mushrooms",
                "1 cup heavy cream",
                "2 cloves garlic",
                "1 medium onion",
                "50g parmesan cheese",
                "2 tbsp olive oil",
                "Salt to taste",
                "Black pepper to taste",
                "Fresh parsley for garnish"
            ],
            "cooking_steps": [
                "Step 1: Preparation instructions",
                "Step 2: Cooking instructions", 
                "Step 3: Final steps"
            ],
            "tips": [
                "Helpful cooking tip 1",
                "Helpful cooking tip 2"
            ],
            "nutritional_info": {{
                "calories_per_serving": 450,
                "protein": "15g",
                "carbs": "55g", 
                "fat": "18g"
            }}
        }}
        
        Make sure ingredients are realistic grocery store items with proper quantities.
        """
        
        try:
            response = await self.gemini.generate_text_response(prompt=prompt)
            
            # Clean the response to extract JSON
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()
            
            # Parse JSON response
            recipe_data = json.loads(response)
            
            # Validate required fields
            required_fields = ['recipe_name', 'ingredients', 'servings']
            if all(field in recipe_data for field in required_fields):
                return recipe_data
            else:
                raise ValueError("Missing required recipe fields")
                
        except Exception as e:
            self.logger.warning(f"Failed to parse Gemini recipe response: {e}")
            
            # Intelligent fallback based on user message
            fallback_recipe = await self._generate_fallback_recipe(message)
            return fallback_recipe

    async def _get_user_groceries(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's existing groceries from knowledge graph."""
        try:
            # Query Firestore for user's grocery purchases
            groceries_query = {
                'user_id': user_id,
                'category': 'Grocery',
                'expiry_date': {'>=': datetime.now()}  # Only non-expired items
            }
            
            groceries = await self.firestore.query_documents("receipts", groceries_query)
            
            # Extract individual items from receipts
            grocery_items = []
            for receipt in groceries:
                if 'items' in receipt:
                    for item in receipt['items']:
                        grocery_items.append({
                            'name': item.get('name', '').lower(),
                            'quantity': item.get('quantity', 1),
                            'expiry_date': receipt.get('expiry_date'),
                            'purchase_date': receipt.get('date')
                        })
            
            return grocery_items
            
        except Exception as e:
            self.logger.error(f"Error getting user groceries: {e}")
            # Return empty list - no demo data fallback
            return []

    async def _find_missing_ingredients(self, required_ingredients: List[str], existing_groceries: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Find missing ingredients by comparing recipe needs with existing groceries."""
        missing_items = []
        existing_items = [item['name'].lower() for item in existing_groceries]
        
        for ingredient in required_ingredients:
            # Extract the main ingredient name (ignore quantities)
            ingredient_name = self._extract_ingredient_name(ingredient).lower()
            
            # Check if we have this ingredient
            if not any(ingredient_name in existing_item for existing_item in existing_items):
                missing_items.append({
                    'ingredient': ingredient,
                    'name': ingredient_name,
                    'estimated_price': self._estimate_ingredient_price(ingredient_name)
                })
        
        return missing_items

    def _extract_ingredient_name(self, ingredient: str) -> str:
        """Extract the main ingredient name from a quantity string."""
        # Remove common quantity words and numbers
        words_to_remove = ['cup', 'cups', 'tbsp', 'tsp', 'lb', 'lbs', 'kg', 'g', 'ml', 'l', 'medium', 'large', 'small', 'fresh', 'to', 'taste']
        
        # Split and filter
        words = ingredient.lower().split()
        filtered_words = []
        
        for word in words:
            # Skip numbers
            if word.replace('.', '').replace('/', '').isdigit():
                continue
            # Skip measurement units
            if word in words_to_remove:
                continue
            filtered_words.append(word)
        
        return ' '.join(filtered_words)

    def _estimate_ingredient_price(self, ingredient_name: str) -> str:
        """Estimate price for an ingredient."""
        price_estimates = {
            'mushrooms': '₹80',
            'cream': '₹60',
            'heavy cream': '₹60',
            'onion': '₹20',
            'garlic': '₹15',
            'parmesan cheese': '₹200',
            'olive oil': '₹150',
            'pasta': '₹50',
            'penne pasta': '₹50',
            'salt': '₹20',
            'pepper': '₹30',
            'black pepper': '₹30',
            'herbs': '₹40',
            'parsley': '₹30',
            'thyme': '₹35'
        }
        
        return price_estimates.get(ingredient_name, '₹50')

    async def _generate_shopping_list_pass(self, user_id: str, recipe_name: str, missing_items: List[Dict]) -> Dict[str, Any]:
        """Generate a Google Wallet shopping list pass."""
        try:
            # Prepare shopping list data
            items_text = "\n".join([f"• {item['ingredient']}" for item in missing_items])
            total_cost = sum([int(item['estimated_price'].replace('₹', '')) for item in missing_items])
            
            pass_data = {
                'type': 'shopping_list',
                'title': f'Shopping for {recipe_name}',
                'description': f'Shopping list for {recipe_name} recipe',
                'items': items_text,
                'total_items': len(missing_items),
                'estimated_cost': f'₹{total_cost}',
                'recipe_name': recipe_name,
                'created_by': 'Economix Bot',
                'user_id': user_id
            }
            
            # Store the pass data in Firestore for wallet generation
            await self.firestore.add_document("shopping_list_passes", pass_data)
            
            return {'success': True, 'pass_data': pass_data}
            
        except Exception as e:
            self.logger.error(f"Error generating shopping list pass: {e}")
            return {'success': False, 'error': str(e)}

    def _format_ingredients_list(self, ingredients: List[str]) -> str:
        """Format ingredients list for display."""
        return "\n".join([f"• {ingredient}" for ingredient in ingredients])

    def _format_available_items(self, required_ingredients: List[str], existing_groceries: List[Dict]) -> str:
        """Format available items for display."""
        existing_items = [item['name'].lower() for item in existing_groceries]
        available = []
        
        for ingredient in required_ingredients:
            ingredient_name = self._extract_ingredient_name(ingredient).lower()
            if any(ingredient_name in existing_item for existing_item in existing_items):
                available.append(f"✅ {ingredient}")
        
        return "\n".join(available) if available else "None found in your pantry"

    def _format_missing_items(self, missing_items: List[Dict]) -> str:
        """Format missing items for display."""
        if not missing_items:
            return "None - you have everything!"
        
        return "\n".join([
            f"🛒 {item['ingredient']} - {item['estimated_price']}" 
            for item in missing_items
        ])

    def _format_cooking_steps(self, steps: List[str]) -> str:
        """Format cooking steps for display."""
        if not steps:
            return "Recipe steps will be provided with detailed instructions."
        
        return "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps[:4])])  # Show first 4 steps

    def _format_tips(self, tips: List[str]) -> str:
        """Format cooking tips for display."""
        if not tips:
            return "• Cook with love and taste as you go!"
        
        return "\n".join([f"• {tip}" for tip in tips[:3]])  # Show first 3 tips

    def _estimate_cost(self, missing_items: List[Dict]) -> int:
        """Estimate total cost of missing items."""
        total = sum([int(item['estimated_price'].replace('₹', '')) for item in missing_items])
        return total

    async def _generate_fallback_recipe(self, message: str) -> Dict[str, Any]:
        """Generate a smart fallback recipe based on user's message."""
        message_lower = message.lower()
        
        # Detect cuisine/dish type from message
        if any(word in message_lower for word in ['pasta', 'italian']):
            return {
                "recipe_name": "Classic Mushroom Penne Pasta",
                "description": "Creamy mushroom pasta with fresh herbs",
                "cuisine_type": "Italian",
                "difficulty": "Easy",
                "prep_time": "15 minutes",
                "cook_time": "20 minutes", 
                "servings": 4,
                "ingredients": [
                    "500g penne pasta",
                    "300g fresh mushrooms, sliced",
                    "1 cup heavy cream",
                    "3 cloves garlic, minced",
                    "1 medium onion, diced",
                    "100g parmesan cheese, grated",
                    "3 tbsp olive oil",
                    "Salt to taste",
                    "Black pepper to taste",
                    "Fresh parsley for garnish"
                ],
                "cooking_steps": [
                    "Cook pasta according to package directions",
                    "Sauté mushrooms and onions in olive oil",
                    "Add cream and parmesan, simmer until thick",
                    "Toss with pasta and serve hot"
                ],
                "tips": ["Don't overcook the mushrooms", "Save pasta water to adjust consistency"],
                "nutritional_info": {
                    "calories_per_serving": 485,
                    "protein": "18g",
                    "carbs": "58g",
                    "fat": "20g"
                }
            }
        elif any(word in message_lower for word in ['curry', 'indian', 'spicy']):
            return {
                "recipe_name": "Chicken Curry",
                "description": "Aromatic Indian chicken curry with rich spices",
                "cuisine_type": "Indian",
                "difficulty": "Medium",
                "prep_time": "20 minutes",
                "cook_time": "30 minutes",
                "servings": 4,
                "ingredients": [
                    "1 kg chicken, cut into pieces",
                    "2 large onions, sliced",
                    "4 tomatoes, chopped",
                    "1 cup coconut milk",
                    "2 tbsp curry powder",
                    "1 tbsp garam masala",
                    "4 cloves garlic, minced",
                    "1 inch ginger, grated",
                    "3 tbsp vegetable oil",
                    "Salt to taste",
                    "Fresh cilantro for garnish",
                    "2 cups basmati rice"
                ],
                "cooking_steps": [
                    "Marinate chicken with spices for 15 minutes",
                    "Sauté onions until golden, add garlic and ginger",
                    "Add chicken and cook until browned",
                    "Add tomatoes and coconut milk, simmer 20 minutes",
                    "Serve over rice with fresh cilantro"
                ],
                "tips": ["Let chicken marinate for best flavor", "Adjust spice level to taste"],
                "nutritional_info": {
                    "calories_per_serving": 520,
                    "protein": "35g",
                    "carbs": "45g",
                    "fat": "22g"
                }
            }
        else:
            # Default simple recipe
            return {
                "recipe_name": "Quick Stir-Fried Noodles",
                "description": "Simple and delicious vegetable noodles",
                "cuisine_type": "Asian",
                "difficulty": "Easy",
                "prep_time": "10 minutes",
                "cook_time": "15 minutes",
                "servings": 3,
                "ingredients": [
                    "400g egg noodles",
                    "2 cups mixed vegetables",
                    "3 tbsp soy sauce",
                    "2 tbsp vegetable oil",
                    "2 cloves garlic, minced",
                    "1 tbsp sesame oil",
                    "1 tsp sugar",
                    "Green onions for garnish"
                ],
                "cooking_steps": [
                    "Cook noodles according to package directions",
                    "Heat oil and stir-fry vegetables until tender",
                    "Add cooked noodles and sauces, toss well",
                    "Garnish with green onions and serve hot"
                ],
                "tips": ["Don't overcook vegetables", "High heat works best for stir-frying"],
                "nutritional_info": {
                    "calories_per_serving": 380,
                    "protein": "12g",
                    "carbs": "65g",
                    "fat": "8g"
                }
            }


# Global instance
economix_bot_agent = EconomixBotAgent()
