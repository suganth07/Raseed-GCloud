"""
Enhanced API endpoints for Flutter frontend with better UI messages
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..services.firestore_service import FirestoreService
from ..utils.logging import get_logger

# Create router
router = APIRouter(prefix="/ui", tags=["Flutter UI"])
logger = get_logger(__name__)

# Service instance
firestore_service = None

def get_firestore_service():
    """Get or create Firestore service instance."""
    global firestore_service
    if firestore_service is None:
        firestore_service = FirestoreService()
    return firestore_service

@router.get("/dashboard/{user_id}")
async def get_user_dashboard(user_id: str) -> Dict[str, Any]:
    """
    Get comprehensive dashboard data for Flutter frontend
    """
    try:
        service = get_firestore_service()
        
        # Get user's graphs
        graphs = await service.get_user_graphs(user_id, limit=10)
        
        # Calculate analytics from graphs
        total_spending = 0.0
        for graph in graphs:
            for entity in (graph.entities or []):
                if entity.type == "product" and entity.attributes:
                    price = entity.attributes.get("price", 0.0)
                    total_spending += price
        
        # Prepare dashboard response with UI-friendly messages
        if not graphs:
            return {
                "success": True,
                "user_id": user_id,
                "has_data": False,
                "ui_state": "empty",
                "welcome_message": {
                    "title": "Welcome to Raseed! 👋",
                    "subtitle": "Start by uploading your first receipt",
                    "action_text": "Upload Receipt",
                    "empty_state_message": "No receipts uploaded yet. Upload a receipt to see your spending insights and knowledge graphs!"
                },
                "stats": {
                    "total_graphs": 0,
                    "total_entities": 0,
                    "total_relations": 0,
                    "total_spending": 0.0
                },
                "recent_graphs": [],
                "spending_insights": []
            }
        
        # Calculate summary stats
        total_entities = sum(g.total_entities for g in graphs if hasattr(g, 'total_entities'))
        total_relations = sum(g.total_relations for g in graphs if hasattr(g, 'total_relations'))
        
        # Get recent graphs for display
        recent_graphs = []
        for graph in graphs[:5]:  # Get latest 5 graphs
            recent_graphs.append({
                "id": graph.id,
                "name": graph.name.replace("receipt_graph_", "Receipt ") if graph.name.startswith("receipt_graph_") else graph.name,
                "created_at": graph.created_at.isoformat() if graph.created_at else datetime.now().isoformat(),
                "entity_count": getattr(graph, 'total_entities', len(graph.entities) if graph.entities else 0),
                "relation_count": getattr(graph, 'total_relations', len(graph.relations) if graph.relations else 0),
                "summary": f"{getattr(graph, 'total_entities', 0)} items analyzed"
            })
        
        return {
            "success": True,
            "user_id": user_id,
            "has_data": True,
            "ui_state": "loaded",
            "welcome_message": {
                "title": f"Dashboard Overview 📊",
                "subtitle": f"You have {len(graphs)} receipt{'s' if len(graphs) != 1 else ''} analyzed",
                "stats_summary": f"{total_entities} products tracked across {len(graphs)} receipts"
            },
            "stats": {
                "total_graphs": len(graphs),
                "total_entities": total_entities,
                "total_relations": total_relations,
                "total_spending": total_spending
            },
            "recent_graphs": recent_graphs,
            "spending_summary": {
                "total_spent": total_spending,
                "average_per_receipt": total_spending / len(graphs) if graphs else 0.0,
                "receipt_count": len(graphs)
            },
            "actions": {
                "can_upload": True,
                "can_view_graphs": len(graphs) > 0,
                "can_view_insights": len(graphs) > 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard for user {user_id}: {e}")
        return {
            "success": False,
            "user_id": user_id,
            "has_data": False,
            "ui_state": "error",
            "error_message": {
                "title": "Unable to Load Dashboard 😞",
                "subtitle": "There was an issue loading your data",
                "details": "Please try again or contact support if the issue persists",
                "retry_action": "Retry"
            },
            "stats": {
                "total_graphs": 0,
                "total_entities": 0,
                "total_relations": 0,
                "total_spending": 0.0
            }
        }

@router.get("/graphs/{user_id}")
async def get_user_graphs_ui(
    user_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=50, description="Items per page")
) -> Dict[str, Any]:
    """
    Get user's knowledge graphs with pagination and UI-friendly format
    """
    try:
        service = get_firestore_service()
        graphs = await service.get_user_graphs(user_id, limit=limit)
        
        if not graphs:
            return {
                "success": True,
                "user_id": user_id,
                "total_graphs": 0,
                "graphs": [],
                "ui_message": {
                    "title": "No Knowledge Graphs Yet 📝",
                    "message": "Upload receipts to create knowledge graphs and track your spending patterns",
                    "action_text": "Upload First Receipt",
                    "empty_icon": "📊"
                },
                "pagination": {
                    "current_page": page,
                    "total_pages": 0,
                    "total_items": 0
                }
            }
        
        # Format graphs for UI
        formatted_graphs = []
        for graph in graphs:
            formatted_graphs.append({
                "id": graph.id,
                "name": graph.name.replace("receipt_graph_", "Shopping Trip ") if graph.name.startswith("receipt_graph_") else graph.name,
                "description": graph.description,
                "created_at": graph.created_at.isoformat() if graph.created_at else datetime.now().isoformat(),
                "entity_count": getattr(graph, 'total_entities', len(graph.entities) if graph.entities else 0),
                "relation_count": getattr(graph, 'total_relations', len(graph.relations) if graph.relations else 0),
                "preview": {
                    "products": [e.name for e in (graph.entities or []) if e.type == "product"][:3],
                    "merchant": next((e.name for e in (graph.entities or []) if e.type == "merchant"), "Unknown Store"),
                    "categories": list(set(e.category for e in (graph.entities or []) if e.category))[:2]
                },
                "ui_summary": f"{getattr(graph, 'total_entities', 0)} items from {next((e.name for e in (graph.entities or []) if e.type == 'merchant'), 'Unknown Store')}"
            })
        
        return {
            "success": True,
            "user_id": user_id,
            "total_graphs": len(graphs),
            "graphs": formatted_graphs,
            "ui_message": {
                "title": f"Knowledge Graphs ({len(graphs)}) 🧠",
                "message": f"Your spending patterns analyzed across {len(graphs)} receipt{'s' if len(graphs) != 1 else ''}",
                "summary": f"Total items tracked: {sum(g['entity_count'] for g in formatted_graphs)}"
            },
            "pagination": {
                "current_page": page,
                "total_pages": (len(graphs) + limit - 1) // limit,
                "total_items": len(graphs)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting graphs for user {user_id}: {e}")
        return {
            "success": False,
            "user_id": user_id,
            "total_graphs": 0,
            "graphs": [],
            "ui_message": {
                "title": "Error Loading Graphs 😞",
                "message": "Unable to load your knowledge graphs at this time",
                "error_details": str(e),
                "action_text": "Try Again"
            }
        }

@router.get("/graph/{graph_id}/details")
async def get_graph_details_ui(graph_id: str) -> Dict[str, Any]:
    """
    Get detailed view of a specific knowledge graph for Flutter UI
    """
    try:
        service = get_firestore_service()
        graph = await service.get_knowledge_graph(graph_id)
        
        if not graph:
            return {
                "success": False,
                "error": "Graph not found",
                "ui_message": {
                    "title": "Graph Not Found 🔍",
                    "message": "The requested knowledge graph could not be found",
                    "action_text": "Go Back"
                }
            }
        
        # Analyze graph for insights
        products = [e for e in graph.entities if e.type == "product"]
        categories = [e for e in graph.entities if e.type == "category"]
        merchants = [e for e in graph.entities if e.type == "merchant"]
        
        # Calculate spending by category
        category_spending = {}
        for product in products:
            price = product.attributes.get("price", 0.0) if product.attributes else 0.0
            category = product.category or "Other"
            category_spending[category] = category_spending.get(category, 0.0) + price
        
        return {
            "success": True,
            "graph": {
                "id": graph.id,
                "name": graph.name.replace("receipt_graph_", "Shopping Trip ") if graph.name.startswith("receipt_graph_") else graph.name,
                "description": graph.description,
                "created_at": graph.created_at.isoformat() if graph.created_at else datetime.now().isoformat(),
                "summary": {
                    "total_entities": len(graph.entities),
                    "total_relations": len(graph.relations),
                    "product_count": len(products),
                    "category_count": len(categories),
                    "merchant_count": len(merchants)
                }
            },
            "insights": {
                "spending_by_category": category_spending,
                "total_spending": sum(category_spending.values()),
                "top_categories": sorted(category_spending.items(), key=lambda x: x[1], reverse=True)[:3],
                "product_diversity": len(set(p.category for p in products if p.category))
            },
            "ui_display": {
                "title": f"Receipt Analysis 📊",
                "subtitle": f"{len(products)} products analyzed",
                "merchant_info": merchants[0].name if merchants else "Unknown Store",
                "spending_summary": f"${sum(category_spending.values()):.2f} total spent",
                "key_insights": [
                    f"{len(products)} different products purchased",
                    f"{len(categories)} product categories",
                    f"Top category: {max(category_spending.items(), key=lambda x: x[1])[0] if category_spending else 'N/A'}"
                ]
            },
            "entities": [
                {
                    "id": e.id,
                    "name": e.name,
                    "type": e.type,
                    "category": e.category,
                    "attributes": e.attributes,
                    "confidence": e.confidence
                } for e in graph.entities
            ],
            "relations": [
                {
                    "id": r.id,
                    "source": r.source_entity_id,
                    "target": r.target_entity_id,
                    "type": r.relation_type,
                    "weight": r.weight,
                    "attributes": r.attributes
                } for r in graph.relations
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting graph details for {graph_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "ui_message": {
                "title": "Error Loading Graph Details 😞",
                "message": "Unable to load the graph details at this time",
                "error_details": str(e),
                "action_text": "Try Again"
            }
        }
