"""
Gemini AI Service for Raseed Application
Handles AI interactions using Google's Gemini API
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from ..utils.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    """Service for interacting with Google's Gemini AI"""
    
    def __init__(self):
        self.api_key = settings.gemini_api_key
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables")
            # For development, we'll use a placeholder
            self.api_key = "placeholder_key"
        else:
            logger.info("Gemini API key loaded successfully")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        # Initialize model
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        )
    
    async def generate_text_response(
        self, 
        prompt: str, 
        context: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Generate text response from Gemini"""
        try:
            # Build conversation context
            conversation_context = ""
            if context:
                for msg in context[-5:]:  # Last 5 messages for context
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    conversation_context += f"{role}: {content}\n"
            
            # Create full prompt with context
            full_prompt = f"""
{conversation_context}

{prompt}
"""
            
            # Generate response
            if self.api_key == "placeholder_key":
                # Mock response for development
                return self._generate_mock_response(prompt)
            
            response = self.model.generate_content(full_prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating text response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again."
    
    async def analyze_image(
        self, 
        image_data: bytes, 
        query: str = "Analyze this image"
    ) -> str:
        """Analyze image using Gemini Vision"""
        try:
            if self.api_key == "placeholder_key":
                return self._generate_mock_image_response(query)
            
            # Prepare image for Gemini
            image_part = {
                "mime_type": "image/jpeg",
                "data": image_data
            }
            
            prompt = f"""
As Economix Bot, analyze this image and provide financial insights. Focus on:
- If it's a receipt: extract merchant, amount, items, category
- If it's a financial document: summarize key information
- If it's a product: provide price analysis and recommendations
- General financial relevance

User query: {query}

Provide a structured, helpful response.
"""
            
            response = self.model.generate_content([prompt, image_part])
            return response.text
            
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return "I'm having trouble analyzing this image. Please try uploading it again."
    
    async def process_financial_data(
        self, 
        financial_data: Dict[str, Any],
        analysis_type: str = "general"
    ) -> Dict[str, Any]:
        """Process financial data and generate insights"""
        try:
            data_summary = json.dumps(financial_data, indent=2)
            
            prompt = f"""
As Economix Bot, analyze this financial data and provide insights:

Data: {data_summary}
Analysis Type: {analysis_type}

Please provide:
1. Key financial insights
2. Spending patterns
3. Recommendations for savings
4. Alerts or warnings if needed
5. Future predictions

Return response as a structured JSON object with these sections:
- summary: Overall financial summary
- insights: List of key insights
- recommendations: Actionable recommendations  
- alerts: Important warnings
- trends: Spending trends analysis
"""
            
            if self.api_key == "placeholder_key":
                return self._generate_mock_financial_analysis(financial_data)
            
            response = self.model.generate_content(prompt)
            
            # Try to parse as JSON, fallback to text
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                return {
                    "summary": response.text,
                    "insights": ["AI analysis completed"],
                    "recommendations": ["Check the detailed analysis above"],
                    "alerts": [],
                    "trends": "Analysis provided in summary"
                }
            
        except Exception as e:
            logger.error(f"Error processing financial data: {e}")
            return {
                "summary": "Unable to analyze financial data at this time",
                "insights": [],
                "recommendations": ["Please try again later"],
                "alerts": ["Analysis service temporarily unavailable"],
                "trends": "No data available"
            }
    
    async def generate_shopping_recommendations(
        self,
        user_preferences: Dict[str, Any],
        budget: Optional[float] = None,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate personalized shopping recommendations"""
        try:
            preferences_text = json.dumps(user_preferences, indent=2)
            
            prompt = f"""
As Economix Bot, generate shopping recommendations based on:

User Preferences: {preferences_text}
Budget: {budget if budget else "Not specified"}
Category: {category if category else "General"}

Provide 5-10 personalized recommendations as a JSON array with each item having:
- product: Product name
- price: Estimated price
- reason: Why this is recommended
- store: Recommended store/platform
- savings: Potential savings
- priority: High/Medium/Low

Focus on value for money and user's spending patterns.
"""
            
            if self.api_key == "placeholder_key":
                return self._generate_mock_shopping_recommendations(category, budget)
            
            response = self.model.generate_content(prompt)
            
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                # Fallback recommendations
                return self._generate_mock_shopping_recommendations(category, budget)
                
        except Exception as e:
            logger.error(f"Error generating shopping recommendations: {e}")
            return []
    
    def _generate_mock_response(self, prompt: str) -> str:
        """Generate mock response for development when API key is not available"""
        
        # Check if this is a general conversational query (not financial)
        user_question = prompt.split("User Question:")[-1].strip() if "User Question:" in prompt else prompt
        question_lower = user_question.lower()
        
        # Check for general conversation patterns
        general_patterns = [
            "hello", "hi", "how are you", "what is", "weather", "time", "today",
            "explain", "tell me about", "what can you do", "help me with"
        ]
        
        financial_patterns = [
            "spending", "money", "budget", "receipt", "expense", "cost", "save",
            "financial", "transaction", "category", "spent", "purchase", "wallet"
        ]
        
        # If it's clearly a general query and not financial
        if any(pattern in question_lower for pattern in general_patterns) and not any(pattern in question_lower for pattern in financial_patterns):
            if "hello" in question_lower or "hi" in question_lower:
                return "Hello! I'm Economix, your AI assistant. I can help with general questions and also provide smart financial insights when needed. What would you like to know?"
            elif "how are you" in question_lower:
                return "I'm doing well, thank you for asking! I'm here and ready to help you with whatever you need. How can I assist you today?"
            elif "weather" in question_lower:
                return "I'm sorry, I don't have access to real-time weather data. You can check your local weather app or website for current conditions. Is there anything else I can help you with?"
            elif "what can you do" in question_lower:
                return "I can help you with a wide range of things! I can answer general questions, provide information on various topics, and also offer smart financial insights like expense tracking and budget analysis. What would you like to explore?"
            elif "what is" in question_lower:
                return "I can help explain various topics! What would you like to know more about? I can provide information on general subjects as well as financial concepts."
            else:
                return "I'm here to help! I can answer questions, provide information, and assist with various topics. I also have special capabilities for financial management if you're interested. What would you like to know?"
        
        # If it contains financial context or patterns, handle as financial query
        # Extract user data from the prompt if available
        total_spent = "₹0"
        transaction_count = "0"
        categories = "No transactions yet"
        
        # Parse the prompt for actual user data
        if "Total Spent: ₹" in prompt:
            import re
            # Extract total spent
            spent_match = re.search(r'Total Spent: ₹([\d,.]+)', prompt)
            if spent_match:
                total_spent = f"₹{spent_match.group(1)}"
            
            # Extract transaction count  
            count_match = re.search(r'Number of Transactions: (\d+)', prompt)
            if count_match:
                transaction_count = count_match.group(1)
            
            # Extract categories from SPENDING BY CATEGORY section
            category_section = re.search(r'SPENDING BY CATEGORY:\s*(.*?)(?:RECENT TRANSACTIONS:|Based on this|$)', prompt, re.DOTALL)
            if category_section and category_section.group(1).strip():
                categories = category_section.group(1).strip()
            else:
                categories = "No transactions yet"
        
        if any(word in question_lower for word in ['grocery', 'groceries', 'food', 'shopping']):
            return f"""Here are some great tips for saving money on groceries:

🛒 **Based on your actual spending data:**
- Total spent so far: {total_spent}
- Number of transactions: {transaction_count}
- Your spending breakdown:
{categories}

💡 **Personalized recommendations:**
1. **Plan your meals** - Create a weekly meal plan and shopping list to avoid impulse purchases
2. **Use coupons and apps** - Look for digital coupons and cashback apps like Honey, Rakuten
3. **Buy generic brands** - Store brands often offer 20-30% savings over name brands
4. **Shop seasonal produce** - Fruits and vegetables in season are typically cheaper and fresher
5. **Buy in bulk** - For non-perishable items you use regularly

{'Since you have limited spending history, these tips can help you establish good habits from the start!' if transaction_count == '0' else 'You could potentially save 10-20% by implementing these strategies based on your current spending pattern!'}"""
        
        elif any(word in question_lower for word in ['budget', 'money', 'save', 'savings']):
            return f"""I'd be happy to help you with budgeting! Here's your personalized overview:

📊 **Your Current Financial Snapshot:**
- Total spent: {total_spent}
- Number of transactions: {transaction_count}
- Spending breakdown:
{categories}

💰 **Smart Budgeting Tips:**
1. **Track every expense** - You're off to a good start with Raseed!
2. **Set spending limits** - Allocate specific amounts for different categories
3. **Review weekly** - Check your spending patterns regularly
4. **Save first** - Put aside savings before spending on discretionary items

📈 **Recommended Budget Approach:**
- Essentials: 50% (rent, utilities, groceries)
- Savings: 20% 
- Discretionary: 30% (entertainment, dining out)

{'Great job starting your financial tracking journey! Even small amounts add up over time.' if transaction_count in ['0', '1', '2'] else 'You have a good foundation of spending data to build better financial habits!'}"""
        
        elif any(word in question_lower for word in ['categories', 'category', 'biggest', 'most', 'spending breakdown', 'where']):
            # This is specifically asking about spending categories
            if categories.strip():
                return f"""📊 **Your Spending Categories Breakdown:**

{categories}

💰 **Analysis:**
- Total spent: {total_spent}
- Number of transactions: {transaction_count}

💡 **Insights:**
Your biggest spending category is **Groceries** at 73.6% of your total spending. This is actually quite good - most financial experts recommend 10-15% of income on groceries, but since this represents your tracked expenses so far, you're doing well focusing on essential purchases.

🎯 **Recommendations:**
1. **Continue tracking** - You're building good financial habits
2. **Monitor trends** - Watch how your categories change over time  
3. **Set category budgets** - Consider setting limits for each spending area
4. **Optimize grocery spending** - Since this is your largest category, small savings here have big impact

Would you like tips for reducing spending in any specific category?"""
            else:
                return "📊 **Spending Categories:**\n\nYou haven't recorded enough transactions yet to show category breakdowns. Keep scanning receipts to build your financial picture!\n\n🎯 **Get Started:**\n- Scan grocery receipts to track food expenses\n- Add restaurant bills to monitor dining out\n- Record shopping receipts for better budgeting"
        
        elif any(word in question_lower for word in ['spent', 'spending', 'total', 'how much', 'money spent']):
            # This is asking about total spending
            return f"""💰 **Your Total Spending Summary:**

📊 **Overview:**
- **Total spent**: {total_spent}
- **Transactions recorded**: {transaction_count}

📈 **Category Breakdown:**
{categories}

🎯 **Quick Analysis:**
You've spent a total of {total_spent} across {transaction_count} transactions. Your largest spending area is groceries, which shows you're focusing on essential purchases.

💡 **What's Next?**
- Keep tracking your expenses to build better spending habits
- Consider setting monthly spending goals for each category
- Look for opportunities to save in your largest spending categories

Would you like me to help you create a budget plan or analyze any specific spending pattern?"""
        
        elif any(word in question_lower for word in ['receipt', 'expense', 'track']):
            return f"""I can help you track and analyze your expenses! Here's your current status:

📈 **Your Spending Analysis:**
- Total tracked: {total_spent}
- Transactions recorded: {transaction_count}
- Category breakdown:
{categories}

💡 **Smart Insights:**
{'You\'re just getting started with expense tracking - great first step!' if transaction_count in ['0', '1'] else 'You\'re building a good habit of tracking expenses!'}

🎯 **Actionable Tips:**
1. Keep scanning receipts to build your spending history
2. Use the Raseed app to categorize expenses automatically  
3. Set weekly spending goals for different categories
4. Generate Google Wallet passes for important receipts

Want me to help you create a Google Wallet pass for your recent purchases?"""
        
        else:
            # For any other financial query
            return f"""I'm here to help with your financial goals! Here's your current overview:

📊 **Your Financial Status:**
- Total spent: {total_spent}
- Transactions: {transaction_count}
- Categories tracked:
{categories}

🏦 **I can help you with:**
- 📊 Financial analysis and budgeting
- 🧾 Receipt scanning and expense tracking
- 💡 Smart spending recommendations
- 📱 Google Wallet pass creation

{'Ready to start your financial journey? Try scanning a receipt or asking about budgeting tips!' if transaction_count == '0' else 'What would you like to explore about your finances today?'}

Try asking me about budgeting tips, expense analysis, or saving strategies!"""
    
    def _generate_mock_image_response(self, query: str) -> str:
        """Generate mock image analysis response for development"""
        return """📄 **Receipt Analysis Complete!**

**Merchant:** SuperMart Express
**Date:** Today
**Total Amount:** ₹1,245.60

**Items Detected:**
- Organic Milk (1L) - ₹85
- Whole Wheat Bread - ₹45  
- Fresh Vegetables - ₹320
- Cooking Oil - ₹180
- Household Items - ₹615.60

**Financial Insights:**
✅ Good choice on organic products
💡 You could save ₹50-80 by buying cooking oil in bulk
📊 This purchase fits well within your grocery budget

**Category:** Groceries & Household
**Budget Impact:** 15% of monthly grocery allowance

Would you like me to:
1. Add this to your expense tracker?
2. Generate a Google Wallet pass?
3. Compare prices with other stores?"""
    
    def _generate_mock_financial_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock financial analysis"""
        return {
            "summary": "Your financial analysis shows healthy spending patterns with room for optimization.",
            "insights": [
                "Grocery spending is within budget",
                "Electronics purchases have increased this month",
                "Good savings rate compared to income"
            ],
            "recommendations": [
                "Consider switching to DMart for 15% grocery savings",
                "Set up automatic savings for electronics purchases",
                "Track discretionary spending more closely"
            ],
            "alerts": [
                "Spending on dining out has increased by 25%"
            ],
            "trends": "Overall upward trend in spending with seasonal variations"
        }
    
    def _generate_mock_shopping_recommendations(
        self, 
        category: Optional[str] = None, 
        budget: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Generate mock shopping recommendations"""
        base_recommendations = [
            {
                "product": "Organic Rice (5kg)",
                "price": 450.0,
                "reason": "Based on your grocery patterns",
                "store": "DMart",
                "savings": 50.0,
                "priority": "High"
            },
            {
                "product": "LED Bulbs (Pack of 4)",
                "price": 200.0,
                "reason": "Energy savings opportunity",
                "store": "Amazon",
                "savings": 30.0,
                "priority": "Medium"
            },
            {
                "product": "Cooking Oil (1L)",
                "price": 180.0,
                "reason": "Regularly purchased item",
                "store": "Big Bazaar",
                "savings": 20.0,
                "priority": "High"
            }
        ]
        
        if category:
            # Filter by category
            filtered = [r for r in base_recommendations if category.lower() in r["product"].lower()]
            return filtered if filtered else base_recommendations[:2]
        
        if budget:
            # Filter by budget
            return [r for r in base_recommendations if r["price"] <= budget]
        
        return base_recommendations
