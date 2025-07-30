from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
import io
from datetime import date, datetime

from ..services.document_ai import DocumentAIService
from ..services.firestore_service import FirestoreService
from ..agents.graph_builder import graph_builder_agent
from ..models.receipt import Receipt, ReceiptSearchQuery, ReceiptSummary
from ..models.knowledge_graph import KnowledgeGraph, GraphAnalytics
from ..utils.logging import get_logger

# Create router
router = APIRouter()
logger = get_logger(__name__)

# Service instances - will be initialized lazily
document_ai_service = None
firestore_service = None


def get_document_ai_service():
    """Get or create Document AI service instance."""
    global document_ai_service
    if document_ai_service is None:
        document_ai_service = DocumentAIService()
    return document_ai_service


def get_firestore_service():
    """Get or create Firestore service instance."""
    global firestore_service
    if firestore_service is None:
        firestore_service = FirestoreService()
    return firestore_service


@router.post("/receipts/upload", response_model=Receipt)
async def upload_receipt(
    file: UploadFile = File(...),
    user_id: str = Form(...)
):
    """
    Upload and process a receipt image.
    
    Args:
        file: Receipt image file (JPEG, PNG, WebP, PDF)
        user_id: ID of the user uploading the receipt
        
    Returns:
        Processed receipt data
    """
    try:
        logger.info(f"Processing receipt upload for user: {user_id}")
        
        # Validate file type
        if file.content_type not in [
            "image/jpeg", "image/png", "image/webp", "application/pdf"
        ]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}"
            )
        
        # Validate file size (10MB limit)
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="File size too large. Maximum 10MB allowed."
            )
        
        # Process with Document AI
        receipt = await get_document_ai_service().process_receipt_image(
            content, file.content_type
        )
        
        # Set user ID
        receipt.user_id = user_id
        
        # Save to Firestore
        receipt_id = await get_firestore_service().save_receipt(receipt)
        
        logger.info(f"Receipt processed successfully: {receipt_id}")
        return receipt
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing receipt: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/receipts/upload-multiple", response_model=List[Receipt])
async def upload_multiple_receipts(
    files: List[UploadFile] = File(...),
    user_id: str = Form(...)
):
    """
    Upload and process multiple receipt images.
    
    Args:
        files: List of receipt image files
        user_id: ID of the user uploading the receipts
        
    Returns:
        List of processed receipt data
    """
    try:
        logger.info(f"Processing {len(files)} receipts for user: {user_id}")
        
        if len(files) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 files allowed per batch"
            )
        
        # Prepare image data
        images_data = []
        for file in files:
            # Validate file type
            if file.content_type not in [
                "image/jpeg", "image/png", "image/webp", "application/pdf"
            ]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file.content_type}"
                )
            
            content = await file.read()
            if len(content) > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} too large. Maximum 10MB allowed."
                )
            
            images_data.append((content, file.content_type))
        
        # Process all receipts
        receipts = await get_document_ai_service().process_multiple_receipts(images_data)
        
        # Set user ID and save to Firestore
        for receipt in receipts:
            receipt.user_id = user_id
            await get_firestore_service().save_receipt(receipt)
        
        logger.info(f"Processed {len(receipts)} receipts successfully")
        return receipts
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing multiple receipts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/receipts/{receipt_id}", response_model=Receipt)
async def get_receipt(receipt_id: str):
    """Get a specific receipt by ID."""
    try:
        receipt = await get_firestore_service().get_receipt(receipt_id)
        if not receipt:
            raise HTTPException(status_code=404, detail="Receipt not found")
        return receipt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting receipt {receipt_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/receipts", response_model=List[Receipt])
async def get_receipts(
    user_id: str = Query(...),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0)
):
    """Get receipts for a user with pagination."""
    try:
        receipts = await get_firestore_service().get_receipts_by_user(
            user_id, limit, offset
        )
        return receipts
    except Exception as e:
        logger.error(f"Error getting receipts for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/receipts/search", response_model=List[Receipt])
async def search_receipts(
    query: ReceiptSearchQuery,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0)
):
    """Search receipts based on criteria."""
    try:
        receipts = await get_firestore_service().search_receipts(query, limit, offset)
        return receipts
    except Exception as e:
        logger.error(f"Error searching receipts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/receipts/{receipt_id}", response_model=Receipt)
async def update_receipt(receipt_id: str, receipt: Receipt):
    """Update an existing receipt."""
    try:
        # Ensure the receipt ID matches
        receipt.id = receipt_id
        
        success = await get_firestore_service().update_receipt(receipt)
        if not success:
            raise HTTPException(status_code=404, detail="Receipt not found")
        
        return receipt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating receipt {receipt_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/receipts/{receipt_id}")
async def delete_receipt(receipt_id: str):
    """Delete a receipt."""
    try:
        success = await get_firestore_service().delete_receipt(receipt_id)
        if not success:
            raise HTTPException(status_code=404, detail="Receipt not found")
        
        return {"message": "Receipt deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting receipt {receipt_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/analytics/{user_id}", response_model=ReceiptSummary)
async def get_analytics(
    user_id: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None)
):
    """Get analytics summary for a user's receipts."""
    try:
        analytics = await get_firestore_service().get_receipt_analytics(
            user_id, start_date, end_date
        )
        return analytics
    except Exception as e:
        logger.error(f"Error getting analytics for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/categories")
async def get_categories():
    """Get list of available receipt categories."""
    return {
        "categories": [
            "grocery",
            "restaurant",
            "fuel",
            "shopping",
            "pharmacy",
            "healthcare",
            "entertainment",
            "transportation",
            "utilities",
            "education",
            "business",
            "other"
        ]
    }


@router.get("/merchants/{user_id}")
async def get_merchants(user_id: str):
    """Get list of merchants for a user."""
    try:
        # Get recent receipts to extract merchants
        receipts = await get_firestore_service().get_receipts_by_user(user_id, limit=1000)
        
        # Extract unique merchants
        merchants = list(set(receipt.merchant_name for receipt in receipts))
        merchants.sort()
        
        return {"merchants": merchants}
    except Exception as e:
        logger.error(f"Error getting merchants for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Health check endpoints for individual services
@router.get("/health/document-ai")
async def health_document_ai():
    """Health check for Document AI service."""
    try:
        # Simple check - just verify service is initialized
        service = get_document_ai_service()
        if service.client:
            return {"status": "healthy", "service": "document-ai"}
        else:
            return {"status": "unhealthy", "service": "document-ai"}
    except Exception as e:
        logger.error(f"Document AI health check failed: {str(e)}")
        return {"status": "unhealthy", "service": "document-ai", "error": str(e)}


@router.get("/health/firestore")
async def health_firestore():
    """Health check for Firestore service."""
    try:
        # Simple check - verify database connection
        service = get_firestore_service()
        if service.db:
            return {"status": "healthy", "service": "firestore"}
        else:
            return {"status": "unhealthy", "service": "firestore"}
    except Exception as e:
        logger.error(f"Firestore health check failed: {str(e)}")
        return {"status": "unhealthy", "service": "firestore", "error": str(e)}


# Knowledge Graph Routes

@router.post("/receipts/{receipt_id}/build-graph")
async def build_graph_from_receipt(receipt_id: str):
    """Build a knowledge graph from a specific receipt."""
    try:
        firestore = get_firestore_service()
        
        # Get receipt from Firestore
        receipt_doc = firestore.db.collection('receipts').document(receipt_id).get()
        if not receipt_doc.exists:
            raise HTTPException(status_code=404, detail="Receipt not found")
        
        receipt_data = receipt_doc.to_dict()
        receipt = Receipt(**receipt_data)
        
        # Build graph using Graph Builder Agent
        graph = await graph_builder_agent.build_graph_from_receipt(receipt)
        
        return {
            "success": True,
            "graph_id": graph.id,
            "entities_count": graph.total_entities,
            "relations_count": graph.total_relations,
            "receipt_id": receipt_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building graph from receipt {receipt_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to build knowledge graph")


@router.get("/graphs/user/{user_id}")
async def get_user_knowledge_graph(user_id: str):
    """Get the latest knowledge graph for a user."""
    try:
        graph = await graph_builder_agent.get_user_graph(user_id)
        
        if not graph:
            raise HTTPException(status_code=404, detail="No knowledge graph found for user")
        
        return {
            "success": True,
            "graph": graph.dict(),
            "summary": {
                "total_entities": graph.total_entities,
                "total_relations": graph.total_relations,
                "receipt_count": len(graph.receipt_ids),
                "created_at": graph.created_at,
                "updated_at": graph.updated_at
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving graph for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve knowledge graph")


@router.post("/graphs/merge")
async def merge_knowledge_graphs(graph_ids: List[str], user_id: str = Query(...)):
    """Merge multiple knowledge graphs into one."""
    try:
        if len(graph_ids) < 2:
            raise HTTPException(status_code=400, detail="At least 2 graph IDs required for merging")
        
        merged_graph = await graph_builder_agent.merge_graphs(graph_ids, user_id)
        
        return {
            "success": True,
            "merged_graph_id": merged_graph.id,
            "source_graphs": graph_ids,
            "entities_count": merged_graph.total_entities,
            "relations_count": merged_graph.total_relations,
            "receipts_included": len(merged_graph.receipt_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error merging graphs {graph_ids}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to merge knowledge graphs")


@router.get("/graphs/{graph_id}/analytics")
async def get_graph_analytics(graph_id: str):
    """Get analytics and insights for a knowledge graph."""
    try:
        analytics = await graph_builder_agent.analyze_graph(graph_id)
        
        return {
            "success": True,
            "analytics": analytics.dict(),
            "insights": {
                "top_product": analytics.most_frequent_products[0] if analytics.most_frequent_products else None,
                "top_merchant": analytics.most_frequent_merchants[0] if analytics.most_frequent_merchants else None,
                "dominant_category": max(analytics.category_distribution.items(), key=lambda x: x[1]) if analytics.category_distribution else None,
                "total_receipts": analytics.total_receipts_analyzed
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing graph {graph_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to analyze knowledge graph")


@router.get("/graphs/{graph_id}")
async def get_knowledge_graph(graph_id: str):
    """Get a specific knowledge graph by ID."""
    try:
        firestore = get_firestore_service()
        
        # Get graph from Firestore
        graph_doc = firestore.db.collection('knowledge_graphs').document(graph_id).get()
        if not graph_doc.exists:
            raise HTTPException(status_code=404, detail="Knowledge graph not found")
        
        graph_data = graph_doc.to_dict()
        graph = KnowledgeGraph.from_dict(graph_data)
        
        return {
            "success": True,
            "graph": graph.dict(),
            "nodes": [{"id": e.id, "name": e.name, "type": e.type, "category": e.category} for e in graph.entities],
            "edges": [{"source": r.source_entity_id, "target": r.target_entity_id, "type": r.relation_type, "weight": r.weight} for r in graph.relations]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving graph {graph_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve knowledge graph")


@router.get("/comprehensive-analytics/{user_id}")
async def get_comprehensive_analytics(
    user_id: str,
    limit: int = Query(10, description="Number of records to retrieve"),
    firestore: FirestoreService = Depends(get_firestore_service)
):
    """
    Get comprehensive analytics for a user.
    
    Args:
        user_id: User ID to get analytics for
        limit: Maximum number of records to return
        
    Returns:
        Comprehensive analytics data
    """
    try:
        analytics = await firestore.get_comprehensive_analytics(user_id, limit)
        return {
            "success": True,
            "user_id": user_id,
            "analytics": analytics
        }
        
    except Exception as e:
        logger.error(f"Error retrieving comprehensive analytics for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve comprehensive analytics")


@router.post("/test-ai-classification")
async def test_ai_classification():
    """Test AI classification directly for debugging."""
    try:
        from ..agents.graph_builder import graph_builder_agent
        
        # Test with simple items
        test_items = [
            {"name": "Orange Juice", "description": "", "price": 2.15, "quantity": 1},
            {"name": "Apples", "description": "", "price": 3.50, "quantity": 1}
        ]
        
        # Call AI classification
        classifications = await graph_builder_agent.classify_items_with_gemini(test_items)
        
        # Get comprehensive analysis if available
        comprehensive_analysis = getattr(graph_builder_agent, 'comprehensive_analysis', {})
        
        return {
            "success": True,
            "test_items": test_items,
            "classifications": classifications,
            "comprehensive_analysis": comprehensive_analysis,
            "has_comprehensive_data": bool(comprehensive_analysis)
        }
        
    except Exception as e:
        logger.error(f"Error in AI classification test: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "test_items": test_items,
            "classifications": []
        }