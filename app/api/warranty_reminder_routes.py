"""
Warranty Reminder API Routes

This module provides API endpoints for warranty reminder functionality.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime
from ..services.warranty_reminder_service import WarrantyReminderService
from ..utils.logging import LoggerMixin

router = APIRouter(prefix="/warranty-reminders", tags=["warranty-reminders"])


class CreateReminderRequest(BaseModel):
    """Request model for creating warranty reminders."""
    user_id: str


class CreateSingleReminderRequest(BaseModel):
    """Request model for creating a single warranty reminder."""
    user_id: str
    product_name: str


class WarrantyReminderController(LoggerMixin):
    """Controller for warranty reminder operations."""
    
    def __init__(self):
        super().__init__()
        self.reminder_service = WarrantyReminderService()


def get_reminder_controller() -> WarrantyReminderController:
    """Dependency to get reminder controller instance."""
    return WarrantyReminderController()


@router.post("/create-all-test/")
async def create_all_warranty_reminders_test(
    request: CreateReminderRequest,
    controller: WarrantyReminderController = Depends(get_reminder_controller)
) -> Dict[str, Any]:
    """
    Test endpoint to create warranty reminders without Google Calendar API.
    
    Args:
        request: Request containing user_id
        
    Returns:
        Dictionary with operation results
    """
    try:
        controller.logger.info(f"Testing warranty reminders for user: {request.user_id}")
        
        # Get warranty products without creating actual calendar events
        warranty_products_result = await controller.reminder_service.get_warranty_products(request.user_id)
        
        if warranty_products_result.get("status") == "error":
            raise HTTPException(status_code=500, detail=warranty_products_result.get("error_message", "Unknown error"))
        
        warranty_products = warranty_products_result.get("warranty_products", [])
        
        # Simulate creating reminders for products with both warranty and expiry
        created_count = 0
        reminders_info = []
        
        for product in warranty_products:
            if product.get('has_warranty') or product.get('has_expiry'):
                created_count += 1
                reminders_info.append({
                    "product_name": product.get('product_name'),
                    "has_warranty": product.get('has_warranty'),
                    "has_expiry": product.get('has_expiry'),
                    "expiry_date": product.get('expiry_date'),
                    "days_until_expiry": product.get('days_until_expiry'),
                    "reminder_status": "would_be_created"
                })
        
        return {
            "success": True,
            "message": f"Found {created_count} products that would have reminders created",
            "created_count": created_count,
            "total_products": len(warranty_products),
            "reminders_info": reminders_info,
            "note": "This is a test endpoint - no actual calendar events were created"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        controller.log_error("create_all_warranty_reminders_test", e)
        raise HTTPException(status_code=500, detail=f"Failed to test warranty reminders: {str(e)}")


@router.post("/create-all/")
async def create_all_warranty_reminders_new(
    request: CreateReminderRequest,
    controller: WarrantyReminderController = Depends(get_reminder_controller)
) -> Dict[str, Any]:
    """
    Create calendar reminders for all warranties expiring soon (new endpoint).
    
    Args:
        request: Request containing user_id
        
    Returns:
        Dictionary with operation results
    """
    try:
        controller.logger.info(f"Creating warranty reminders for user: {request.user_id}")
        
        result = await controller.reminder_service.check_and_create_warranty_reminders(request.user_id)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error_message", "Unknown error"))
        
        return {
            "status": "success",
            "message": result.get("message", "Reminders created"),
            "reminders_created": result.get("reminders_created", 0),
            "total_warranties": result.get("total_warranties", 0),
            "failed_reminders": result.get("failed_reminders", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        controller.log_error("create_all_warranty_reminders_new", e)
        raise HTTPException(status_code=500, detail=f"Failed to create warranty reminders: {str(e)}")


@router.post("/create-all/{user_id}")
async def create_all_warranty_reminders(
    user_id: str,
    controller: WarrantyReminderController = Depends(get_reminder_controller)
) -> Dict[str, Any]:
    """
    Create calendar reminders for all warranties expiring soon.
    
    Args:
        user_id: The user ID to create reminders for
        
    Returns:
        Dictionary with operation results
    """
    try:
        controller.logger.info(f"Creating warranty reminders for user: {user_id}")
        
        result = await controller.reminder_service.check_and_create_warranty_reminders(user_id)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["error_message"])
        
        return {
            "success": True,
            "message": result["message"],
            "reminders_created": result["reminders_created"],
            "total_warranties": result["total_warranties"],
            "failed_reminders": result.get("failed_reminders", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        controller.log_error("create_all_warranty_reminders", e)
        raise HTTPException(status_code=500, detail=f"Failed to create warranty reminders: {str(e)}")


@router.get("/warranty-products/{user_id}")
async def get_warranty_products(
    user_id: str,
    controller: WarrantyReminderController = Depends(get_reminder_controller)
) -> Dict[str, Any]:
    """
    Get all products with warranty or expiry information for a user.
    
    Args:
        user_id: The user ID
        
    Returns:
        Dictionary with warranty products
    """
    try:
        controller.logger.info(f"Getting warranty products for user: {user_id}")
        
        result = await controller.reminder_service.get_warranty_products(user_id)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["error_message"])
        
        return {
            "success": True,
            "warranty_products": result["warranty_products"],
            "count": result["count"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        controller.log_error("get_warranty_products", e)
        raise HTTPException(status_code=500, detail=f"Failed to get warranty products: {str(e)}")


@router.post("/create-single/")
async def create_single_warranty_reminder_new(
    request: CreateSingleReminderRequest,
    controller: WarrantyReminderController = Depends(get_reminder_controller)
) -> Dict[str, Any]:
    """
    Create a calendar reminder for a specific warranty product (new endpoint).
    
    Args:
        request: Request containing user_id and product_name
        
    Returns:
        Dictionary with operation results
    """
    try:
        controller.logger.info(f"Creating warranty reminder for user: {request.user_id}, product: {request.product_name}")
        
        result = await controller.reminder_service.create_single_warranty_reminder(request.user_id, request.product_name)
        
        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["error_message"])
        
        return {
            "status": "success",
            "message": f"Calendar reminder created for {request.product_name}",
            "event_details": result.get("details", {}),
            "event_link": result.get("event_link", "")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        controller.log_error("create_single_warranty_reminder_new", e)
        raise HTTPException(status_code=500, detail=f"Failed to create warranty reminder: {str(e)}")


@router.get("/upcoming/")
async def get_upcoming_warranty_reminders(
    user_id: str,
    days_ahead: int = 30,
    controller: WarrantyReminderController = Depends(get_reminder_controller)
) -> Dict[str, Any]:
    """
    Get upcoming warranty reminders (new endpoint matching frontend).
    
    Args:
        user_id: The user ID (from query parameters)
        days_ahead: Number of days to look ahead (default 30)
        
    Returns:
        Dictionary with upcoming warranty reminders
    """
    try:
        controller.logger.info(f"Getting upcoming reminders for user: {user_id}, days ahead: {days_ahead}")
        
        result = await controller.reminder_service.get_upcoming_warranty_expirations(user_id, days_ahead)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["error_message"])
        
        return {
            "success": True,
            "reminders": result["upcoming_expirations"],
            "count": result["count"],
            "days_ahead": days_ahead
        }
        
    except HTTPException:
        raise
    except Exception as e:
        controller.log_error("get_upcoming_warranty_reminders", e)
        raise HTTPException(status_code=500, detail=f"Failed to get upcoming reminders: {str(e)}")


@router.get("/upcoming/{user_id}")
async def create_single_warranty_reminder(
    user_id: str,
    product_name: str,
    controller: WarrantyReminderController = Depends(get_reminder_controller)
) -> Dict[str, Any]:
    """
    Create a calendar reminder for a specific warranty product.
    
    Args:
        user_id: The user ID
        product_name: Name of the product to create reminder for
        
    Returns:
        Dictionary with operation results
    """
    try:
        controller.logger.info(f"Creating warranty reminder for user: {user_id}, product: {product_name}")
        
        result = await controller.reminder_service.create_single_warranty_reminder(user_id, product_name)
        
        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["error_message"])
        
        return {
            "success": True,
            "message": f"Calendar reminder created for {product_name}",
            "event_details": result.get("details", {}),
            "event_link": result.get("event_link", "")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        controller.log_error("create_single_warranty_reminder", e)
        raise HTTPException(status_code=500, detail=f"Failed to create warranty reminder: {str(e)}")


@router.get("/upcoming/{user_id}")
async def get_upcoming_warranty_expirations(
    user_id: str,
    days_ahead: int = 30,
    controller: WarrantyReminderController = Depends(get_reminder_controller)
) -> Dict[str, Any]:
    """
    Get warranties expiring within the specified number of days.
    
    Args:
        user_id: The user ID
        days_ahead: Number of days to look ahead (default 30)
        
    Returns:
        Dictionary with upcoming warranty expirations
    """
    try:
        controller.logger.info(f"Getting upcoming expirations for user: {user_id}, days ahead: {days_ahead}")
        
        result = await controller.reminder_service.get_upcoming_warranty_expirations(user_id, days_ahead)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["error_message"])
        
        return {
            "success": True,
            "upcoming_expirations": result["upcoming_expirations"],
            "count": result["count"],
            "days_ahead": days_ahead
        }
        
    except HTTPException:
        raise
    except Exception as e:
        controller.log_error("get_upcoming_warranty_expirations", e)
        raise HTTPException(status_code=500, detail=f"Failed to get upcoming expirations: {str(e)}")


@router.get("/health")
async def health_check(
    controller: WarrantyReminderController = Depends(get_reminder_controller)
) -> Dict[str, Any]:
    """
    Check the health of the warranty reminder service.
    
    Returns:
        Health status information
    """
    try:
        # Test Google Calendar agent initialization
        calendar_agent = controller.reminder_service.calendar_agent
        
        return {
            "success": True,
            "service": "warranty-reminders",
            "status": "healthy",
            "calendar_agent_ready": calendar_agent is not None,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        controller.log_error("health_check", e)
        return {
            "success": False,
            "service": "warranty-reminders",
            "status": "unhealthy",
            "error": str(e)
        }
