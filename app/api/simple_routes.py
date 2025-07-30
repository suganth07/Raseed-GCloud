"""
Simple API routes for Document AI text extraction.
Using Google ADK - just extracts text from images.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Dict, Any, List
from datetime import datetime, date
from ..services.simple_document_ai import simple_document_ai
from ..agents.graph_builder import graph_builder_agent
from ..models.receipt import Receipt, ReceiptItem
from ..utils.logging import get_logger

# Create router
router = APIRouter()
logger = get_logger(__name__)


def _detect_mime_type(content: bytes, filename: str, original_content_type: str) -> str:
    """
    Detect proper MIME type from file content and filename.
    """
    # Check file signature (magic numbers)
    if content.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    elif content.startswith(b'\x89PNG'):
        return "image/png"
    elif content.startswith(b'RIFF') and b'WEBP' in content[:12]:
        return "image/webp"
    elif content.startswith(b'%PDF'):
        return "application/pdf"
    
    # Check if content is text (contains only printable ASCII characters)
    try:
        content.decode('utf-8')
        # If it decodes as UTF-8, it's likely text
        if filename and filename.lower().endswith(('.txt', '.text')):
            return "text/plain"
    except UnicodeDecodeError:
        pass
    
    # Fallback to filename extension
    if filename:
        filename_lower = filename.lower()
        if filename_lower.endswith(('.jpg', '.jpeg')):
            return "image/jpeg"
        elif filename_lower.endswith('.png'):
            return "image/png"
        elif filename_lower.endswith('.webp'):
            return "image/webp"
        elif filename_lower.endswith('.pdf'):
            return "application/pdf"
        elif filename_lower.endswith(('.txt', '.text')):
            return "text/plain"
    
    # If original content type is valid, use it
    if original_content_type in ["image/jpeg", "image/png", "image/webp", "application/pdf", "text/plain"]:
        return original_content_type
    
    # Default to JPEG only for binary content
    return "image/jpeg"


@router.post("/upload")
async def upload_image_for_text_extraction(
    file: UploadFile = File(...),
    user_id: str = Form(...)
) -> Dict[str, Any]:
    """
    Upload image and extract text using Document AI.
    
    Args:
        file: Image file (JPEG, PNG, WebP, PDF)
        user_id: ID of the user uploading the image
        
    Returns:
        Extracted text and metadata
    """
    try:
        logger.info(f"Processing image upload for user: {user_id}")
        logger.info(f"File details - name: {file.filename}, content_type: {file.content_type}, size: {file.size}")
        
        # Validate file
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Read content first to check size
        content = await file.read()
        logger.info(f"Read {len(content)} bytes from uploaded file")
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Validate file type - be more flexible with content type detection
        content_type = file.content_type or ""
        
        # Detect proper MIME type based on file content and extension
        proper_mime_type = _detect_mime_type(content, file.filename, content_type)
        
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp", "application/pdf", "text/plain"]
        if proper_mime_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {proper_mime_type}. Allowed: {allowed_types}"
            )
        
        # Validate file size (10MB limit)  
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="File size too large. Maximum 10MB allowed."
            )
        
        logger.info(f"Using detected MIME type: {proper_mime_type}")
        
        # Extract text - handle text files differently than images
        if proper_mime_type == "text/plain":
            # For text files, just decode the content directly
            try:
                extracted_text = content.decode('utf-8')
                result = {
                    "extracted_text": extracted_text,
                    "success": True,
                    "confidence": 1.0,  # Text files have perfect confidence
                    "source": "direct_text_extraction"
                }
                logger.info(f"Extracted {len(extracted_text)} characters from text file")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Text file contains invalid UTF-8 characters"
                )
        else:
            # For images, use Document AI with error handling
            try:
                result = await simple_document_ai.extract_text_from_image(
                    content, proper_mime_type
                )
            except Exception as doc_ai_error:
                # If Document AI fails, try to extract as text if possible
                logger.warning(f"Document AI failed: {doc_ai_error}")
                try:
                    # Try to decode as text as fallback
                    extracted_text = content.decode('utf-8', errors='ignore')
                    if extracted_text.strip():
                        logger.info("Falling back to text extraction")
                        result = {
                            "extracted_text": extracted_text,
                            "success": True,
                            "confidence": 0.5,  # Lower confidence for fallback
                            "source": "fallback_text_extraction",
                            "warning": "Document AI failed, used text fallback"
                        }
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Document AI failed and content is not readable text: {str(doc_ai_error)}"
                        )
                except UnicodeDecodeError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Document AI failed and content is not valid text: {str(doc_ai_error)}"
                    )
        
        # Add user info to result
        result["user_id"] = user_id
        result["filename"] = file.filename
        result["detected_mime_type"] = proper_mime_type
        
        logger.info(f"Text extraction completed for user {user_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/receipts/upload")
async def upload_receipt(
    file: UploadFile = File(...),
    user_id: str = Form(...)
) -> Dict[str, Any]:
    """
    Legacy endpoint - redirects to simple text extraction.
    """
    return await upload_image_for_text_extraction(file, user_id)


@router.get("/health/document-ai")
async def health_document_ai():
    """Health check for Document AI service."""
    try:
        # Simple check - just verify service is initialized
        if simple_document_ai._client is None:
            # Try to initialize client
            simple_document_ai._get_client()
        return {"status": "healthy", "service": "document-ai"}
    except Exception as e:
        logger.error(f"Document AI health check failed: {str(e)}")
        return {"status": "unhealthy", "service": "document-ai", "error": str(e)}


@router.get("/health")
async def health_check():
    """General health check."""
    return {
        "status": "healthy",
        "service": "simple-document-ai",
        "endpoints": ["/upload", "/receipts/upload", "/upload-with-graph", "/health/document-ai"]
    }


@router.post("/upload-with-graph")
async def upload_image_and_build_graph(
    file: UploadFile = File(...),
    user_id: str = Form(...)
) -> Dict[str, Any]:
    """
    Upload image, extract text, create receipt, and build knowledge graph.
    Enhanced endpoint that creates structured data and graphs.
    """
    try:
        logger.info(f"Processing image upload with graph building for user: {user_id}")
        
        # First, do the basic text extraction
        upload_result = await upload_image_for_text_extraction(file, user_id)
        
        if not upload_result.get("success", True):
            return upload_result
        
        # Extract structured data from the text using Gemini
        extracted_text = upload_result.get("extracted_text", "")
        receipt_data = upload_result.get("receipt_data", {})
        
        # Ensure required fields have fallback values
        merchant_name = receipt_data.get("merchant_name", "Unknown Merchant")
        total_amount = receipt_data.get("total_amount", 0.0)
        
        # Handle case where total_amount might be a string
        try:
            if isinstance(total_amount, str):
                # Remove currency symbols and parse
                total_amount = float(total_amount.replace('$', '').replace(',', '').strip())
        except (ValueError, AttributeError):
            total_amount = 0.0
        
        logger.info(f"Creating receipt with merchant: {merchant_name}, total: {total_amount}")
        
        # Create a receipt object with extracted data
        try:
            receipt = Receipt(
                merchant_name=merchant_name,
                date=receipt_data.get("date", date.today()),
                total_amount=total_amount,
                user_id=user_id,
                raw_text=extracted_text,
                confidence_score=upload_result.get("confidence", 0.0),
                processing_status="completed"
            )
        except Exception as receipt_error:
            logger.error(f"Failed to create receipt object: {receipt_error}")
            logger.info(f"Receipt data: {receipt_data}")
            raise HTTPException(status_code=400, detail=f"Failed to create receipt: {str(receipt_error)}")
        
        # Add items if available
        if receipt_data.get("items"):
            receipt.items = receipt_data["items"]
        
        # Build knowledge graph using the Graph Builder Agent
        try:
            logger.info("Building knowledge graph with Graph Builder Agent...")
            graph = await graph_builder_agent.build_graph_from_receipt(receipt)
            
            # Convert graph to frontend-compatible format
            nodes = []
            edges = []
            
            # Convert entities to nodes
            for entity in graph.entities:
                node = {
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.type,
                    "category": entity.category,
                    "attributes": entity.attributes,
                    "confidence": entity.confidence
                }
                nodes.append(node)
            
            # Convert relations to edges
            for relation in graph.relations:
                edge = {
                    "id": relation.id,
                    "source": relation.source_entity_id,
                    "target": relation.target_entity_id,
                    "type": relation.relation_type,
                    "weight": relation.weight,
                    "attributes": relation.attributes
                }
                edges.append(edge)
            
            # Prepare the Flutter-compatible response format
            current_time = datetime.now()
            
            # Extract items from the graph entities (using Graph Builder Agent's extraction)
            items = []
            for entity in graph.entities:
                if entity.type == "product":
                    # Use enhanced price from Gemini analysis if available
                    enhanced_price = entity.attributes.get("unit_price", entity.attributes.get("price", 0.0))
                    
                    item_dict = {
                        "name": entity.name,
                        "unit_price": enhanced_price,
                        "total_price": entity.attributes.get("total_price", enhanced_price * entity.attributes.get("quantity", 1)),
                        "quantity": entity.attributes.get("quantity", 1),
                        "category": entity.category or entity.attributes.get("category", "General"),
                        "brand": entity.attributes.get("brand", ""),
                        # Use expiry_date instead of warranty_end_date for expiry information
                        "expiry_date": entity.attributes.get("expiry_date", None),
                        "has_expiry": entity.attributes.get("has_expiry", False),
                        "is_expiring_soon": entity.attributes.get("is_expiring_soon", False),
                        # Keep warranty info separate
                        "warranty_end_date": entity.attributes.get("warranty_expiry", None),
                        "has_warranty": entity.attributes.get("has_warranty", False),
                        # Add more enhanced fields
                        "product_type": entity.attributes.get("product_type", ""),
                        "is_food": entity.attributes.get("is_food", False),
                        "is_discounted": entity.attributes.get("is_discounted", False),
                        # Add price field for backward compatibility with test script
                        "price": enhanced_price
                    }
                    items.append(item_dict)
            
            # Create Flutter-compatible response
            result = {
                # Basic receipt information
                "receipt_id": receipt.id if hasattr(receipt, 'id') else f"receipt_{user_id}_{int(current_time.timestamp())}",
                "merchant_name": merchant_name,
                "business_category": receipt_data.get("business_category", "Retail"),
                "total_amount": total_amount,
                "currency": receipt_data.get("currency", "USD"),
                "date": receipt_data.get("date", current_time.date()).isoformat() if hasattr(receipt_data.get("date", current_time.date()), 'isoformat') else str(receipt_data.get("date", current_time.date())),
                "shopping_pattern": receipt_data.get("shopping_pattern", "Regular"),
                
                # Items array
                "items": items,
                "item_count": len(items),  # Add item count for test script
                
                # Location information
                "location": {
                    "city": receipt_data.get("location", {}).get("city", "Unknown"),
                    "state": receipt_data.get("location", {}).get("state", "Unknown"), 
                    "country": receipt_data.get("location", {}).get("country", "USA"),
                    "formatted_address": receipt_data.get("location", {}).get("formatted_address", "Unknown Location")
                },
                
                # Knowledge graph information
                "node_count": len(nodes),
                "edge_count": len(edges),
                "graph_entities": len(nodes),  # Add graph_entities for test script
                "processing_time": f"{(current_time - current_time).total_seconds():.2f}s",  # Placeholder timing
                "version": "1.0.0",
                
                # Alerts and warnings (can be enhanced)
                "alerts": [],  # No expiry alerts for now
                
                # Additional metadata
                "confidence_score": upload_result.get("confidence", 0.0),
                "raw_text": extracted_text,
                "status": "completed",
                
                # Legacy fields for backward compatibility
                "success": True,
                "message": "✅ Receipt processed and knowledge graph created successfully!",
                "ui_messages": {
                    "success_title": "Upload Successful! 🎉",
                    "success_message": f"Created knowledge graph with {len(nodes)} entities and {len(edges)} relationships",
                    "graph_summary": f"📊 Graph Analysis: {len(nodes)} products connected through {len(edges)} relationships",
                    "next_action": "You can now view your knowledge graph and spending insights!"
                },
                "receipt_created": True,
                "graph_created": True,
                "graph_id": graph.id,
                "knowledge_graph": {
                    "id": graph.id,
                    "nodes": nodes,
                    "edges": edges,
                    "summary": {
                        "total_nodes": len(nodes),
                        "total_edges": len(edges),
                        "entity_types": list(set(node["type"] for node in nodes)),
                        "relation_types": list(set(edge["type"] for edge in edges))
                    }
                },
                "entities": nodes,
                "relations": edges,
                "total_entities": len(nodes),
                "total_relations": len(edges),
            }
            
            logger.info(f"Successfully created knowledge graph with {len(nodes)} nodes and {len(edges)} edges")
            
        except Exception as graph_error:
            logger.warning(f"Graph creation failed: {graph_error}")
            # Return basic result without graph but with graceful fallback
            result = {
                **upload_result,
                "success": False,
                "status": "partial_success",
                "message": "⚠️ Receipt processed but graph creation failed",
                "ui_messages": {
                    "warning_title": "Partial Success ⚠️",
                    "warning_message": "Receipt text was extracted successfully, but knowledge graph creation failed",
                    "error_details": str(graph_error),
                    "next_action": "You can try uploading again or contact support if the issue persists"
                },
                "receipt_created": True,
                "receipt_id": receipt.id if hasattr(receipt, 'id') else f"receipt_{user_id}_{int(datetime.now().timestamp())}",
                "graph_created": False,
                "graph_id": None,  # No graph created
                "knowledge_graph": {
                    "id": None,  # No graph ID
                    "nodes": [],
                    "edges": [],
                    "summary": {"error": "Graph creation failed but receipt extraction successful"}
                },
                "entities": [],  # Empty arrays for Flutter compatibility
                "relations": [],  # Empty arrays for Flutter compatibility
                "total_entities": 0,  # Add explicit counts for Flutter
                "total_relations": 0,  # Add explicit counts for Flutter
                "graph_error": str(graph_error)
            }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing image with graph: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def _extract_basic_items_from_text(text: str, total_amount: float) -> List[ReceiptItem]:
    """
    Extract basic items from receipt text.
    This is a simplified version - you can enhance with more sophisticated parsing.
    """
    items = []
    
    # Simple heuristic: look for lines that might be items
    lines = text.split('\n')
    item_lines = []
    
    for line in lines:
        line = line.strip()
        # Look for lines with numbers (potential prices)
        if line and any(char.isdigit() for char in line) and len(line) > 3:
            # Skip lines that look like headers, totals, etc.
            skip_words = ['total', 'subtotal', 'tax', 'tip', 'change', 'receipt', 'thank', 'visit']
            if not any(skip in line.lower() for skip in skip_words):
                item_lines.append(line)
    
    # If we found potential item lines, create items
    if item_lines:
        avg_price = total_amount / len(item_lines) if item_lines else total_amount
        
        for i, line in enumerate(item_lines[:5]):  # Limit to 5 items max
            # Extract potential price from line
            import re
            price_match = re.search(r'\$?(\d+\.?\d*)', line)
            price = float(price_match.group(1)) if price_match else avg_price
            
            # Clean item name
            item_name = re.sub(r'\$?\d+\.?\d*', '', line).strip()
            item_name = item_name[:50] if item_name else f"Item {i+1}"
            
            item = ReceiptItem(
                name=item_name,
                unit_price=price,
                total_price=price,
                quantity=1
            )
            items.append(item)
    else:
        # Create a single generic item
        items.append(ReceiptItem(
            name="General Purchase",
            unit_price=total_amount,
            total_price=total_amount,
            quantity=1
        ))
    
    return items


@router.post("/test-ai-classification")
async def test_ai_classification():
    """Test AI classification directly for debugging."""
    try:
        # Test with simple items
        test_items = [
            {"name": "Orange Juice", "description": "", "price": 2.15, "quantity": 1},
            {"name": "Apples", "description": "", "price": 3.50, "quantity": 1}
        ]
        
        # Call AI classification
        classifications = await graph_builder_agent._classify_items_with_gemini(test_items)
        
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
