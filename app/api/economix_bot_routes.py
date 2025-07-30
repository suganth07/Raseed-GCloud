"""
Economix Bot API Routes - Direct Backend Implementation

Clean implementation with direct Firestore integration.
"""

from fastapi import APIRouter, Form, HTTPException, status, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
from datetime import datetime

from ..services.firestore_service import FirestoreService
from ..services.gemini_service import GeminiService
from ..utils.logging import get_logger

# Initialize services and logger
router = APIRouter(prefix="/economix", tags=["economix"])
firestore_service = FirestoreService()
gemini_service = GeminiService()
logger = get_logger(__name__)

async def get_user_email_from_uid(uid: str) -> str:
    """Get the actual logged-in user's email from Firebase Auth UID."""
    try:
        logger.info(f"🔍 Getting email for authenticated user UID: {uid}")
        
        # If the UID itself looks like an email, use it directly
        if '@' in uid and '.' in uid:
            logger.info(f"✅ UID is already an email: {uid}")
            return uid
        
        # Method 1: Check if Firebase Auth stores email in user document
        try:
            user_doc = firestore_service.db.collection('users').document(uid).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                stored_email = user_data.get('email')
                if stored_email:
                    logger.info(f"✅ Found email in user document: {stored_email}")
                    return stored_email
        except Exception as e:
            logger.debug(f"Could not find email in user document: {e}")
        
        # Method 2: Use Firebase Admin SDK to get user email from UID
        try:
            from firebase_admin import auth
            user_record = auth.get_user(uid)
            if user_record.email:
                logger.info(f"✅ Found email via Firebase Auth: {user_record.email}")
                return user_record.email
        except Exception as e:
            logger.debug(f"Firebase Auth lookup failed: {e}")
        
        # Method 3: Check authentication collection if it exists
        try:
            auth_doc = firestore_service.db.collection('auth_users').document(uid).get()
            if auth_doc.exists:
                auth_data = auth_doc.to_dict()
                email = auth_data.get('email')
                if email:
                    logger.info(f"✅ Found email in auth collection: {email}")
                    return email
        except Exception as e:
            logger.debug(f"Auth collection lookup failed: {e}")
        
        # Method 4: Search through user sessions or login records
        try:
            sessions_collection = firestore_service.db.collection('user_sessions')
            sessions = sessions_collection.where('uid', '==', uid).limit(1).stream()
            
            for session in sessions:
                if session.exists:
                    session_data = session.to_dict()
                    email = session_data.get('email')
                    if email:
                        logger.info(f"✅ Found email in session data: {email}")
                        return email
        except Exception as e:
            logger.debug(f"Session lookup failed: {e}")
        
        # If no email found, this means the user is not properly authenticated
        logger.error(f"❌ Could not find email for authenticated UID: {uid}")
        logger.error("🚨 User must be logged in with valid email to access financial data")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error getting user email: {e}")
        return None


async def get_user_financial_data(user_email: str) -> Dict[str, Any]:
    """Fetch user's financial data from Firestore using the user's email address."""
    try:
        logger.info(f"🔍 Fetching financial data for user email: {user_email}")
        
        # Validate email format
        if not user_email or '@' not in user_email:
            logger.error(f"❌ Invalid email format: {user_email}")
            return {
                'user_id': user_email,
                'total_spent': 0.0,
                'transaction_count': 0,
                'transactions': [],
                'categories': {},
                'error': f'Invalid email format: {user_email}'
            }
        
        logger.info(f"🔄 Using email directly as document path: {user_email}")
        
        # Access user's knowledge graphs collection using email as document path
        kg_collection_ref = firestore_service.db.collection('users').document(user_email).collection('knowledge_graphs')
        
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
                        category = categorize_transaction(merchant)
                        categories[category] = categories.get(category, 0) + amount
                        
                        transactions.append({
                            'id': doc.id,
                            'amount': amount,
                            'merchant': merchant,
                            'date': date,
                            'category': category
                        })
                        
                        logger.info(f"📄 Found transaction: {merchant} - ₹{amount}")
        
        # Log summary
        logger.info(f"📊 Summary for {user_email}: ₹{total_spent} total, {len(transactions)} transactions")
        
        return {
            'user_id': user_email,  # Return the email
            'total_spent': total_spent,
            'transaction_count': len(transactions),
            'transactions': transactions,
            'categories': categories
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching financial data for {user_email}: {e}")
        return {
            'user_id': user_email,
            'total_spent': 0.0,
            'transaction_count': 0,
            'transactions': [],
            'categories': {}
        }


def categorize_transaction(merchant_name: str) -> str:
    """Categorize transaction based on merchant name."""
    merchant_lower = merchant_name.lower()
    
    # Food & Dining
    food_keywords = ['restaurant', 'cafe', 'coffee', 'pizza', 'burger', 'food', 'dining', 'starbucks', 'mcdonald', 'kfc', 'domino', 'subway']
    if any(keyword in merchant_lower for keyword in food_keywords):
        return 'Food & Dining'
    
    # Groceries & Supermarkets
    grocery_keywords = ['supermarket', 'grocery', 'market', 'mart', 'store', 'bigbasket', 'grofers', 'amazon fresh', 'walmart']
    if any(keyword in merchant_lower for keyword in grocery_keywords):
        return 'Groceries'
    
    # Transportation
    transport_keywords = ['uber', 'lyft', 'taxi', 'bus', 'metro', 'train', 'fuel', 'gas', 'petrol', 'transport']
    if any(keyword in merchant_lower for keyword in transport_keywords):
        return 'Transportation'
    
    # Shopping & Retail
    shopping_keywords = ['mall', 'shopping', 'retail', 'amazon', 'flipkart', 'myntra', 'ajio', 'fashion']
    if any(keyword in merchant_lower for keyword in shopping_keywords):
        return 'Shopping'
    
    # Entertainment
    entertainment_keywords = ['movie', 'cinema', 'theater', 'netflix', 'spotify', 'entertainment', 'game']
    if any(keyword in merchant_lower for keyword in entertainment_keywords):
        return 'Entertainment'
    
    # Default category
    return 'Other'


def create_financial_prompt(financial_data: Dict[str, Any], user_message: str) -> str:
    """Create a comprehensive prompt for Gemini AI with user's financial data."""
    user_id = financial_data.get('user_id', 'Unknown')
    total_spent = financial_data.get('total_spent', 0)
    transaction_count = financial_data.get('transaction_count', 0)
    transactions = financial_data.get('transactions', [])
    categories = financial_data.get('categories', {})
    
    # Build transaction details
    transaction_details = ""
    for i, transaction in enumerate(transactions[:10], 1):  # Show up to 10 recent transactions
        transaction_details += f"{i}. {transaction['merchant']} - ₹{transaction['amount']} ({transaction['category']}) on {transaction['date'][:10]}\n"
    
    # Build category breakdown
    category_breakdown = ""
    for category, amount in categories.items():
        percentage = (amount / total_spent * 100) if total_spent > 0 else 0
        category_breakdown += f"- {category}: ₹{amount:.2f} ({percentage:.1f}%)\n"
    
    prompt = f"""You are Economix, an AI financial assistant. The user has asked: "{user_message}"

USER FINANCIAL DATA FOR {user_id}:
- Total Spent: ₹{total_spent:.2f}
- Number of Transactions: {transaction_count}

SPENDING BY CATEGORY:
{category_breakdown}

RECENT TRANSACTIONS:
{transaction_details}

Based on this financial data, please:
1. Answer the user's specific question accurately
2. Provide relevant financial insights or recommendations  
3. Provide helpful insights based on their real spending
4. Be conversational and helpful
5. If they have no data, encourage them to start tracking expenses

Please provide a helpful response using their actual financial information."""
    
    return prompt


@router.post("/chat")
async def chat_with_economix(
    request: Request,
    user_email: str = Form(None),
    message: str = Form(None),
    message_type: str = Form(default="text")
):
    """
    Chat with Economix Bot using user's email address.
    Expects user_email (logged-in user's email) instead of Firebase UID.
    """
    try:
        # Handle both JSON and form data
        if user_email is None or message is None:
            try:
                body = await request.json()
                user_email = body.get("user_email") or body.get("user_id")  # Support both for transition
                message = body.get("message")
                message_type = body.get("message_type", "text")
            except Exception:
                pass
        
        logger.info(f"🔍 ECONOMIX CHAT: user_email='{user_email}', message='{message}', type={message_type}")
        
        if not message or not user_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_email and message are required"
            )
        
        # Get user's actual financial data using their logged-in email
        logger.info(f"📧 Fetching data for user email: {user_email}")
        user_financial_data = await get_user_financial_data(user_email)
        
        # Check if user authentication was successful
        if user_financial_data.get('error'):
            logger.error(f"🚨 Authentication failed for user: {user_email}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "success": False,
                    "error": "User authentication failed",
                    "message": "Please ensure you are logged in with a valid email address",
                    "details": user_financial_data.get('error')
                }
            )
        
        # Log what we found
        total_spent = user_financial_data.get('total_spent', 0)
        transaction_count = user_financial_data.get('transaction_count', 0)
        user_email_from_data = user_financial_data.get('user_id', 'Unknown')  # This is actually the email
        logger.info(f"💰 User {user_email_from_data} data: ₹{total_spent} across {transaction_count} transactions")
        
        # Create AI prompt with actual user data
        ai_prompt = create_financial_prompt(user_financial_data, message)
        
        # Get AI response
        response = await gemini_service.generate_text_response(
            prompt=ai_prompt,
            context=[]
        )
        
        return JSONResponse(
            content={
                "success": True,
                "response": response,
                "message_type": message_type,
                "timestamp": datetime.now().isoformat(),
                "user_id": user_email,
                "financial_summary": {
                    "total_spent": total_spent,
                    "transaction_count": transaction_count
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in chat endpoint: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Failed to process message",
                "details": str(e)
            }
        )


# Debug endpoints for testing
@router.get("/debug/user-data/{user_email}")
async def debug_user_data(user_email: str):
    """Debug endpoint to check user's financial data by email"""
    try:
        logger.info(f"🔍 DEBUG: Fetching data for user: {user_email}")
        data = await get_user_financial_data(user_email)
        return JSONResponse(content={
            "success": True,
            "user_email": user_email,
            "data": data
        })
    except Exception as e:
        logger.error(f"❌ DEBUG ERROR: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.post("/debug/test-auth")
async def debug_test_auth(user_id: str = Form(...)):
    """Debug endpoint to test authentication flow."""
    try:
        logger.info(f"🔍 DEBUG: Testing auth for user_id: {user_id}")
        
        # Step 1: Convert UID to email
        email = await get_user_email_from_uid(user_id)
        
        if email is None:
            return JSONResponse(content={
                "success": False,
                "step": "UID to email conversion",
                "error": f"Could not find email for UID: {user_id}",
                "suggestion": "User must be logged in with valid credentials"
            })
        
        # Step 2: Check if user has knowledge graphs
        kg_collection = firestore_service.db.collection('users').document(email).collection('knowledge_graphs')
        kg_docs = list(kg_collection.limit(5).stream())
        
        return JSONResponse(content={
            "success": True,
            "original_uid": user_id,
            "converted_email": email,
            "knowledge_graphs_found": len(kg_docs),
            "sample_kg_ids": [doc.id for doc in kg_docs[:3]]
        })
        
    except Exception as e:
        logger.error(f"❌ DEBUG AUTH ERROR: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.get("/debug/list-users")
async def debug_list_users():
    """Debug endpoint to list all users in Firestore"""
    try:
        users_collection = firestore_service.db.collection('users')
        users = users_collection.limit(20).stream()
        
        user_list = []
        for user in users:
            user_data = user.to_dict()
            
            # Count knowledge graphs for each user
            kg_collection = firestore_service.db.collection('users').document(user.id).collection('knowledge_graphs')
            kg_count = len(list(kg_collection.limit(100).stream()))
            
            user_list.append({
                "user_id": user.id,
                "user_data": user_data,
                "knowledge_graphs_count": kg_count
            })
        
        return JSONResponse(content={
            "success": True,
            "total_users": len(user_list),
            "users": user_list
        })
        
    except Exception as e:
        logger.error(f"❌ DEBUG LIST USERS ERROR: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )
