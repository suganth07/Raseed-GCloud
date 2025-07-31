"""
Gemini AI Service for Raseed Application
Handles AI interactions using Google's Gemini API - REAL DATA ONLY
"""
import json
import logging
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from ..utils.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    """Service for interacting with Google's Gemini AI - REAL CREDENTIALS ONLY"""
    
    def __init__(self):
        self.api_key = settings.gemini_api_key
        
        # STRICT VALIDATION: Never allow placeholder or missing API keys
        if not self.api_key or self.api_key in ["placeholder_key", "your_api_key_here", ""]:
            error_msg = "❌ CRITICAL: Real Gemini API key is required. Mock data is not allowed in production."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validate API key format (basic check)
        if len(self.api_key) < 20:  # Real Gemini API keys are much longer
            error_msg = f"❌ CRITICAL: Gemini API key appears invalid (length: {len(self.api_key)}). Real API key required."
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        logger.info("✅ Real Gemini API key validated and loaded successfully")
        
        # Configure Gemini with real credentials
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
        
        logger.info("Gemini AI Service initialized successfully")
    
    async def generate_text_response(
        self, 
        prompt: str, 
        context: List[Dict[str, str]] = None
    ) -> str:
        """Generate text response using real Gemini API only"""
        try:
            # Build conversation context
            conversation_context = ""
            if context:
                for message in context:
                    role = message.get("role", "user")
                    content = message.get("content", "")
                    conversation_context += f"{role}: {content}\n"
            
            # Create full prompt with context
            full_prompt = f"""
{conversation_context}

{prompt}
"""
            
            # Generate response using real Gemini API only
            response = self.model.generate_content(full_prompt)
            
            if not response or not response.text:
                raise Exception("Empty response from Gemini API")
                
            logger.info("✅ Real Gemini API response generated successfully")
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating text response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again."
    
    async def analyze_image(
        self, 
        image_data: bytes, 
        query: str = "Analyze this image"
    ) -> str:
        """Analyze image using Gemini Vision - REAL API ONLY"""
        try:
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
            
            # Generate real AI response for image analysis - NEVER use mock data
            response = self.model.generate_content([prompt, image_part])
            
            if not response or not response.text:
                raise Exception("Empty response from Gemini API for image analysis")
                
            logger.info("✅ Real Gemini API image analysis completed")
            return response.text
            
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return "I'm having trouble analyzing this image. Please try uploading it again."
    
    async def generate_financial_analysis(
        self, 
        financial_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate financial analysis using real Gemini API only"""
        try:
            prompt = f"""
As Economix Bot, analyze this user's financial data and provide insights:

Financial Data:
{json.dumps(financial_data, indent=2)}

Provide analysis as JSON with these sections:
- summary: Overall financial summary
- insights: List of key insights
- recommendations: Actionable recommendations  
- alerts: Important warnings
- trends: Spending trends analysis
"""
            
            # Generate real financial analysis using Gemini API - NEVER use mock data
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                raise Exception("Empty response from Gemini API for financial analysis")
            
            logger.info("✅ Real Gemini API financial analysis completed")
            
            # Try to parse as JSON, fallback to text
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                return {
                    "summary": response.text,
                    "insights": ["AI analysis completed"],
                    "recommendations": ["Check the detailed analysis above"],
                    "alerts": [],
                    "trends": {"analysis": "See summary for details"}
                }
                
        except Exception as e:
            logger.error(f"Error generating financial analysis: {e}")
            return {
                "error": "Unable to generate financial analysis at this time",
                "summary": "Please try again later",
                "insights": [],
                "recommendations": [],
                "alerts": [],
                "trends": {}
            }
    
    async def generate_shopping_recommendations(
        self, 
        user_data: Dict[str, Any], 
        category: Optional[str] = None, 
        budget: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Generate shopping recommendations using real Gemini API only"""
        try:
            prompt = f"""
Based on this user's spending data, generate personalized shopping recommendations:

User Data: {json.dumps(user_data, indent=2)}
Budget: {budget if budget else "No specific budget"}
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
            
            # Generate real shopping recommendations using Gemini API - NEVER use mock data
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                raise Exception("Empty response from Gemini API for shopping recommendations")
            
            logger.info("✅ Real Gemini API shopping recommendations generated")
            
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                # If JSON parsing fails, return empty list rather than mock data
                logger.warning("Failed to parse shopping recommendations as JSON")
                return []
                
        except Exception as e:
            logger.error(f"Error generating shopping recommendations: {e}")
            return []


# Create global instance - will fail fast if credentials are invalid
try:
    gemini_service = GeminiService()
    logger.info("✅ Gemini service initialized successfully with real credentials")
except Exception as e:
    logger.error(f"❌ CRITICAL: Failed to initialize Gemini service with real credentials: {e}")
    # Re-raise to prevent application startup with invalid credentials
    raise
