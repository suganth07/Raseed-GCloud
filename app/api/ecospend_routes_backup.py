"""
Ecospend API Routes - Spending analysis and eco-friendly recommendations
=====================================================================

Provides REST API endpoints for Ecospend functionality:
- Spending analysis and visualization
- Location-based store recommendations  
- Sustainability tips and recycling centers
- Price comparison opportunities
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import structlog
import os

from ..services.ecospend_service import EcospendService
from ..utils.logging import LoggerMixin

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/ecospend", tags=["ecospend"])

class EcospendRequest(BaseModel):
    """Base request model for Ecospend endpoints."""
    user_email: str

class ChatRequest(BaseModel):
    """Request model for Ecospend chat functionality."""
    user_email: str
    message: str
    context: Optional[Dict[str, Any]] = {}

class EcospendController(LoggerMixin):
    """Controller for Ecospend operations."""
    
    def __init__(self):
        super().__init__()
        self.ecospend_service = EcospendService()

    async def _process_chat_message(self, user_email: str, message: str, context: Dict) -> Dict[str, Any]:
        """
        Process user chat message and return appropriate response.
        
        Args:
            user_email: User's email
            message: User's message
            context: Chat context
            
        Returns:
            Dictionary with response and suggestions
        """
        message_lower = message.lower()
        
        # Check for expiring products
        if any(word in message_lower for word in ['expiring', 'expiry', 'expire', 'expires', 'expiration']):
            try:
                # Get real data from Firestore
                knowledge_graphs = self.ecospend_service.firebase_loader.fetch_user_knowledge_graphs(user_email)
                
                if not knowledge_graphs:
                    return {
                        "message": "❌ No purchase data found. Please scan some receipts first!",
                        "suggestions": [
                            {"action": "scan_receipt", "label": "📷 Scan Receipt"}
                        ]
                    }
                
                # Extract products with expiry dates
                expiring_products = []
                for kg in knowledge_graphs:
                    products = kg.get('products', [])
                    for product in products:
                        expiry_date = product.get('expiry_date', '')
                        if expiry_date and expiry_date != '':
                            expiring_products.append({
                                'name': product.get('name', 'Unknown Product'),
                                'brand': product.get('brand', ''),
                                'expiry_date': expiry_date,
                                'merchant': kg.get('merchant', {}).get('name', 'Unknown Store')
                            })
                
                if not expiring_products:
                    return {
                        "message": "✅ Great news! None of your scanned products have expiry dates recorded, or they may not have expiry information on the receipts.",
                        "suggestions": [
                            {"action": "scan_receipt", "label": "📷 Scan More Receipts"},
                            {"action": "spending_analysis", "label": "📊 View Spending Analysis"}
                        ]
                    }
                
                # Format response with expiring products
                response = "📅 **Your Products with Expiry Information**\n\n"
                response += f"Found {len(expiring_products)} products with expiry dates:\n\n"
                
                for i, product in enumerate(expiring_products[:10], 1):  # Limit to 10 products
                    response += f"{i}. **{product['name']}**\n"
                    if product['brand']:
                        response += f"   Brand: {product['brand']}\n"
                    response += f"   📅 Expires: {product['expiry_date']}\n"
                    response += f"   🏪 From: {product['merchant']}\n\n"
                
                return {
                    "message": response,
                    "suggestions": [
                        {"action": "set_reminder", "label": "⏰ Set Expiry Reminders"},
                        {"action": "spending_analysis", "label": "📊 View Spending Analysis"},
                        {"action": "find_stores", "label": "🏪 Find Replacement Stores"}
                    ],
                    "data": {"expiring_products": expiring_products}
                }
                
            except Exception as e:
                self.log_error("process_expiring_products", e)
                return {
                    "message": "❌ Sorry, I couldn't retrieve your product information right now. Please try again.",
                    "suggestions": [
                        {"action": "scan_receipt", "label": "📷 Scan Receipt"}
                    ]
                }
        
        # Analyze spending patterns - use real data
        elif any(word in message_lower for word in ['spending', 'analysis', 'chart', 'money', 'spent']):
            analysis_result = await self.ecospend_service.get_spending_analysis(user_email)
            
            if analysis_result["status"] == "success":
                data = analysis_result["data"]
                response = "📊 **Your Spending Analysis**\n\n"
                response += f"💰 **Total Spent**: ₹{data['total_spent']:.2f}\n"
                response += f"🛒 **Total Items**: {data['total_items']} items\n\n"
                response += "**📈 Top Categories:**\n"
                
                # Check if category analysis exists and has data
                if 'category_analysis' in data and 'top_categories' in data['category_analysis']:
                    for category, amount in data['category_analysis']['top_categories'][:3]:
                        percentage = (amount / data['total_spent']) * 100
                        response += f"• {category}: ₹{amount:.2f} ({percentage:.1f}%)\n"
                else:
                    response += "• Data being processed...\n"
                
                response += "\n**🏪 Top Stores:**\n"
                if 'store_preferences' in data and 'preferred_stores' in data['store_preferences']:
                    for store, amount in data['store_preferences']['preferred_stores'][:3]:
                        response += f"• {store}: ₹{amount:.2f}\n"
                else:
                    response += "• Data being processed...\n"
                
                return {
                    "message": response,
                    "suggestions": [
                        {"action": "view_chart", "label": "📊 View Spending Chart"},
                        {"action": "find_stores", "label": "🏪 Find Nearby Stores"},
                        {"action": "eco_tips", "label": "♻️ Eco-Friendly Tips"}
                    ],
                    "data": data
                }
            else:
                return {
                    "message": "❌ No spending data found. Please scan some receipts first!",
                    "suggestions": [
                        {"action": "scan_receipt", "label": "📷 Scan Receipt"}
                    ]
                }
        
        # Find nearby stores
        elif any(word in message_lower for word in ['store', 'shop', 'near', 'location', 'buy']):
            return {
                "message": "🏪 **Find Nearby Stores**\n\nI can help you find stores near your location. Please share your location or address.",
                "suggestions": [
                    {"action": "share_location", "label": "📍 Share Location"},
                    {"action": "search_stores", "label": "🔍 Search Stores"},
                    {"action": "spending_analysis", "label": "📊 View Spending"}
                ]
            }
        
        # Eco-friendly tips
        elif any(word in message_lower for word in ['eco', 'environment', 'green', 'sustainable', 'planet']):
            tips = [
                "🌱 Choose products with minimal packaging",
                "♻️ Buy from brands with recycling programs", 
                "🌍 Support local businesses to reduce carbon footprint",
                "💡 Look for energy-efficient products",
                "🥬 Consider organic and natural alternatives"
            ]
            
            response = "♻️ **Eco-Friendly Shopping Tips**\n\n"
            for tip in tips:
                response += f"• {tip}\n"
            
            return {
                "message": response,
                "suggestions": [
                    {"action": "find_stores", "label": "🏪 Find Eco Stores"},
                    {"action": "spending_analysis", "label": "📊 View Spending"},
                    {"action": "scan_receipt", "label": "📷 Scan Receipt"}
                ]
            }
        
        # Warranty information
        elif any(word in message_lower for word in ['warranty', 'guarantee', 'protection', 'coverage']):
            return {
                "message": "🛡️ **Warranty Information**\n\nI can help you track product warranties from your receipts. Scan your receipts to automatically extract warranty information.",
                "suggestions": [
                    {"action": "scan_receipt", "label": "📷 Scan Receipt"},
                    {"action": "warranty_reminder", "label": "⏰ Set Warranty Reminder"},
                    {"action": "spending_analysis", "label": "📊 View Spending"}
                ]
            }
        
        # General greeting or help
        elif any(word in message_lower for word in ['hi', 'hello', 'help', 'what', 'how']):
            return {
                "message": "👋 **Hi! I'm Ecospend**\n\nI'm your AI shopping assistant! I can help you:\n\n• 📊 Analyze your spending patterns\n• 📅 Track product expiry dates\n• 🏪 Find nearby stores\n• ♻️ Get eco-friendly shopping tips\n• 🛡️ Manage product warranties\n\nWhat would you like to know?",
                "suggestions": [
                    {"action": "spending_analysis", "label": "📊 Spending Analysis"},
                    {"action": "expiring_products", "label": "📅 Expiring Products"},
                    {"action": "find_stores", "label": "🏪 Find Stores"},
                    {"action": "eco_tips", "label": "♻️ Eco Tips"}
                ]
            }
        
        # Default response
        else:
            return {
                "message": "🤔 I'm not sure I understand. I can help you with spending analysis, finding stores, tracking expiry dates, and eco-friendly tips.",
                "suggestions": [
                    {"action": "spending_analysis", "label": "📊 Spending Analysis"},
                    {"action": "expiring_products", "label": "📅 Expiring Products"},
                    {"action": "find_stores", "label": "🏪 Find Stores"},
                    {"action": "scan_receipt", "label": "📷 Scan Receipt"}
                ]
            }
        
        # Find nearby stores
        elif any(word in message_lower for word in ['store', 'shop', 'nearby', 'location', 'supermarket']):
            location_result = await self.ecospend_service.get_location_recommendations(user_email)
            
            if location_result["status"] == "success":
                data = location_result["data"]
                location = data['user_location']
                stores = data['nearby_stores']
                
                response = "🏪 **Nearby Stores**\n\n"
                response += f"📍 **Your Location**: {location['city']}, {location['state']}\n\n"
                response += "**🛒 Recommended Supermarkets:**\n"
                
                for store in stores[:5]:
                    response += f"• {store['name']} - ⭐ {store['rating']} ({store['distance']})\n"
                
                return {
                    "message": response,
                    "suggestions": [
                        {"action": "get_directions", "label": "🗺️ Get Directions"},
                        {"action": "price_compare", "label": "💰 Compare Prices"},
                        {"action": "eco_options", "label": "♻️ Eco-Friendly Options"}
                    ],
                    "data": data
                }
            else:
                return {
                    "message": "❌ Could not find your location. Please ensure location access is enabled.",
                    "suggestions": []
                }
        
        # Sustainability tips
        elif any(word in message_lower for word in ['eco', 'green', 'recycle', 'sustainable', 'environment']):
            tips_result = await self.ecospend_service.get_sustainability_tips(user_email)
            
            if tips_result["status"] == "success":
                tips = tips_result["data"]["tips"]
                
                response = "♻️ **Sustainability Tips**\n\n"
                
                for tip in tips[:4]:
                    icon = tip.get('icon', '💡')
                    response += f"{icon} **{tip['category']}**\n"
                    response += f"   {tip['tip']}\n"
                    response += f"   💰 Potential Savings: {tip['savings_potential']}\n\n"
                
                return {
                    "message": response,
                    "suggestions": [
                        {"action": "find_recycling", "label": "♻️ Find Recycling Centers"},
                        {"action": "eco_stores", "label": "🌱 Eco-Friendly Stores"},
                        {"action": "save_money", "label": "💰 Money-Saving Tips"}
                    ],
                    "data": tips_result["data"]
                }
            else:
                return {
                    "message": "💡 Here are some general eco-friendly tips to get you started!",
                    "suggestions": []
                }
        
        # General greeting or help
        else:
            welcome_msg = "👋 **Hi! I'm Ecospend, your AI spending assistant!**\n\n"
            welcome_msg += "I can help you with:\n\n"
            welcome_msg += "📊 **Spending Analysis** - \"Show my spending analysis\"\n"
            welcome_msg += "🏪 **Find Stores** - \"Find nearby supermarkets\"\n"
            welcome_msg += "♻️ **Eco Tips** - \"Give me sustainability tips\"\n"
            welcome_msg += "💰 **Save Money** - \"How can I save money?\"\n\n"
            welcome_msg += "What would you like to explore?"
            
            return {
                "message": welcome_msg,
                "suggestions": [
                    {"action": "spending_analysis", "label": "📊 Analyze Spending"},
                    {"action": "find_stores", "label": "🏪 Find Stores"},
                    {"action": "eco_tips", "label": "♻️ Eco Tips"},
                    {"action": "save_money", "label": "💰 Save Money"}
                ]
            }

def get_ecospend_controller() -> EcospendController:
    """Dependency to get Ecospend controller instance."""
    return EcospendController()

@router.get("/")
async def ecospend_info():
    """Get information about Ecospend capabilities."""
    return {
        "name": "Ecospend AI Assistant",
        "version": "1.0.0",
        "description": "AI-powered spending analysis and eco-friendly recommendations",
        "capabilities": [
            "📊 Spending analysis and visualization",
            "🏪 Location-based store recommendations",
            "♻️ Sustainability tips and recycling centers",
            "💰 Price comparison opportunities",
            "📈 Weekly spending charts",
            "🎯 Personalized money-saving tips"
        ],
        "endpoints": [
            "/spending-analysis/{user_email}",
            "/location-recommendations/{user_email}",
            "/sustainability-tips/{user_email}", 
            "/chat"
        ]
    }

@router.get("/spending-analysis/{user_email}")
async def get_spending_analysis(
    user_email: str,
    controller: EcospendController = Depends(get_ecospend_controller)
) -> Dict[str, Any]:
    """
    Get comprehensive spending analysis for a user.
    
    Args:
        user_email: User's email address
        
    Returns:
        Dictionary with spending analysis results including charts and insights
    """
    try:
        controller.logger.info("Ecospend spending analysis request", user_email=user_email)
        
        result = await controller.ecospend_service.get_spending_analysis(user_email)
        
        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        
        return {
            "status": "success",
            "message": "Spending analysis completed successfully",
            "data": result["data"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        controller.log_error("get_spending_analysis", e)
        raise HTTPException(status_code=500, detail=f"Failed to analyze spending: {str(e)}")

@router.get("/location-recommendations/{user_email}")
async def get_location_recommendations(
    user_email: str,
    controller: EcospendController = Depends(get_ecospend_controller)
) -> Dict[str, Any]:
    """
    Get location-based store and sustainability recommendations.
    
    Args:
        user_email: User's email address
        
    Returns:
        Dictionary with nearby stores and recycling centers
    """
    try:
        controller.logger.info("Ecospend location recommendations request", user_email=user_email)
        
        result = await controller.ecospend_service.get_location_recommendations(user_email)
        
        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        
        return {
            "status": "success",
            "message": "Location recommendations retrieved successfully",
            "data": result["data"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        controller.log_error("get_location_recommendations", e)
        raise HTTPException(status_code=500, detail=f"Failed to get location recommendations: {str(e)}")

@router.get("/sustainability-tips/{user_email}")
async def get_sustainability_tips(
    user_email: str,
    controller: EcospendController = Depends(get_ecospend_controller)
) -> Dict[str, Any]:
    """
    Get personalized sustainability and money-saving tips.
    
    Args:
        user_email: User's email address
        
    Returns:
        Dictionary with personalized sustainability recommendations
    """
    try:
        controller.logger.info("Ecospend sustainability tips request", user_email=user_email)
        
        result = await controller.ecospend_service.get_sustainability_tips(user_email)
        
        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        
        return {
            "status": "success",
            "message": "Sustainability tips retrieved successfully",
            "data": result["data"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        controller.log_error("get_sustainability_tips", e)
        raise HTTPException(status_code=500, detail=f"Failed to get sustainability tips: {str(e)}")

@router.post("/chat")
async def chat_with_ecospend(
    request: ChatRequest,
    controller: EcospendController = Depends(get_ecospend_controller)
) -> Dict[str, Any]:
    """
    Chat with Ecospend AI assistant.
    
    Args:
        request: Chat request with user message and context
        
    Returns:
        Dictionary with AI response and suggested actions
    """
    try:
        controller.logger.info("Ecospend chat request", 
                             user_email=request.user_email, 
                             message=request.message[:100])
        
        # Analyze user message and determine response
        response = await controller._process_chat_message(
            request.user_email,
            request.message,
            request.context
        )
        
        return {
            "status": "success",
            "response": response["message"],
            "suggestions": response.get("suggestions", []),
            "data": response.get("data", {})
        }
        
    except Exception as e:
        controller.log_error("chat_with_ecospend", e)
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

@router.get("/chart/{chart_filename}")
async def get_spending_chart(chart_filename: str):
    """
    Serve spending chart images.
    
    Args:
        chart_filename: Name of the chart file to serve
        
    Returns:
        Chart image file
    """
    try:
        chart_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '..', 
            'static', 'charts', 
            chart_filename
        )
        
        if os.path.exists(chart_path):
            return FileResponse(
                chart_path,
                media_type="image/png",
                filename=chart_filename
            )
        else:
            raise HTTPException(status_code=404, detail="Chart not found")
            
    except Exception as e:
        logger.error("Error serving chart", error=str(e), filename=chart_filename)
        raise HTTPException(status_code=500, detail="Failed to serve chart")
