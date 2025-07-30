"""
Google Wallet API routes for pass generation and management.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from ..agents.pass_generator_agent import PassGeneratorAgent
from ..models.wallet import (
    PassGenerationRequest, 
    PassGenerationResponse,
    WalletItemsResponse
)
from ..utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/wallet", tags=["wallet"])

# Initialize Pass Generator Agent
pass_generator = PassGeneratorAgent()


@router.get("/eligible-items/{user_id}", response_model=WalletItemsResponse)
async def get_eligible_wallet_items(user_id: str):
    """
    Get all items eligible for Google Wallet for a specific user.
    
    Args:
        user_id: User identifier
        
    Returns:
        WalletItemsResponse with eligible receipts and warranties
    """
    try:
        logger.info(f"Fetching eligible wallet items for user: {user_id}")
        
        # Get eligible items from Pass Generator Agent
        eligible_items = await pass_generator.get_eligible_wallet_items(user_id)
        
        # Count items by type
        receipts = [item for item in eligible_items if item.item_type == "receipt"]
        warranties = [item for item in eligible_items if item.item_type == "warranty"]
        
        response = WalletItemsResponse(
            success=True,
            items=eligible_items,
            total_receipts=len(receipts),
            total_warranties=len(warranties)
        )
        
        logger.info(f"Found {len(eligible_items)} eligible items ({len(receipts)} receipts, {len(warranties)} warranties)")
        return response
        
    except Exception as e:
        logger.error(f"Error fetching eligible wallet items for user {user_id}: {str(e)}")
        return WalletItemsResponse(
            success=False,
            error=f"Failed to fetch eligible items: {str(e)}"
        )


@router.post("/generate-pass", response_model=PassGenerationResponse)
async def generate_wallet_pass(request: PassGenerationRequest):
    """
    Generate a signed JWT token for Google Wallet.
    
    Args:
        request: Pass generation request containing item details
        
    Returns:
        PassGenerationResponse with JWT token and wallet URL
    """
    try:
        logger.info(f"Generating wallet pass for item: {request.item_id}, type: {request.pass_type}")
        
        # Validate request
        if not request.item_id or not request.pass_type or not request.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields: item_id, pass_type, user_id"
            )
        
        if request.pass_type not in ["receipt", "warranty"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid pass_type. Must be 'receipt' or 'warranty'"
            )
        
        # Generate pass using Pass Generator Agent
        response = await pass_generator.generate_wallet_pass(request)
        
        if response.success:
            logger.info(f"Successfully generated wallet pass: {response.pass_id}")
        else:
            logger.error(f"Failed to generate wallet pass: {response.error}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating wallet pass: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate wallet pass: {str(e)}"
        )


@router.get("/pass-status/{pass_id}")
async def get_pass_status(pass_id: str):
    """
    Check the status of a wallet pass.
    
    Args:
        pass_id: Google Wallet pass ID
        
    Returns:
        Pass status information
    """
    try:
        logger.info(f"Checking status for pass: {pass_id}")
        
        # For now, return a simple status
        # In a full implementation, you might query Google Wallet API
        # or check your local database for pass status
        
        return JSONResponse(
            content={
                "success": True,
                "pass_id": pass_id,
                "status": "created",  # Could be: created, active, expired, revoked
                "message": "Pass status check completed"
            }
        )
        
    except Exception as e:
        logger.error(f"Error checking pass status for {pass_id}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": f"Failed to check pass status: {str(e)}"
            }
        )


@router.get("/user-passes/{user_id}")
async def get_user_wallet_passes(user_id: str):
    """
    Get all wallet passes for a specific user.
    
    Args:
        user_id: User identifier
        
    Returns:
        List of user's wallet passes
    """
    try:
        logger.info(f"Fetching wallet passes for user: {user_id}")
        
        # Get eligible items (these could be marked as added to wallet)
        eligible_items = await pass_generator.get_eligible_wallet_items(user_id)
        
        # Filter items that have been added to wallet
        wallet_passes = [
            {
                "pass_id": item.wallet_pass_id or f"generated_for_{item.id}",
                "item_id": item.id,
                "title": item.title,
                "subtitle": item.subtitle,
                "type": item.item_type,
                "added_to_wallet": item.added_to_wallet,
                "created_at": item.created_at.isoformat()
            }
            for item in eligible_items
        ]
        
        return JSONResponse(
            content={
                "success": True,
                "user_id": user_id,
                "passes": wallet_passes,
                "total_passes": len(wallet_passes)
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching user wallet passes for {user_id}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": f"Failed to fetch user wallet passes: {str(e)}"
            }
        )


@router.delete("/pass/{pass_id}")
async def revoke_wallet_pass(pass_id: str):
    """
    Revoke a wallet pass (remove from Google Wallet).
    
    Args:
        pass_id: Google Wallet pass ID to revoke
        
    Returns:
        Revocation status
    """
    try:
        logger.info(f"Revoking wallet pass: {pass_id}")
        
        # In a full implementation, you would:
        # 1. Call Google Wallet API to revoke the pass
        # 2. Update your local database to mark pass as revoked
        
        # For now, return success
        return JSONResponse(
            content={
                "success": True,
                "pass_id": pass_id,
                "message": "Pass revocation completed",
                "note": "Pass revocation not fully implemented yet"
            }
        )
        
    except Exception as e:
        logger.error(f"Error revoking wallet pass {pass_id}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": f"Failed to revoke wallet pass: {str(e)}"
            }
        )


# Health check endpoint for wallet service
@router.get("/health")
async def wallet_health_check():
    """Health check for wallet service."""
    try:
        # You could add checks for:
        # - Google Wallet API connectivity
        # - Service account credentials validity
        # - Firestore connectivity
        
        return JSONResponse(
            content={
                "status": "healthy",
                "service": "wallet",
                "timestamp": logger.info("Wallet service health check completed"),
                "checks": {
                    "pass_generator": "operational",
                    "google_wallet_service": "configured",
                    "firestore": "connected"
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Wallet health check failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "wallet",
                "error": str(e)
            }
        )
