"""
Graph API endpoints for Firebase storage and retrieval
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime

from ..services.firestore_service import FirestoreService
from ..models.knowledge_graph import KnowledgeGraph
from ..utils.logging import get_logger

router = APIRouter(prefix="/graphs", tags=["knowledge_graphs"])
logger = get_logger(__name__)

# Service instance
firestore_service = None

def get_firestore_service():
    """Get or create Firestore service instance."""
    global firestore_service
    if firestore_service is None:
        firestore_service = FirestoreService()
    return firestore_service

@router.get("/user/{user_id}")
async def get_user_graphs(
    user_id: str,
    limit: int = Query(default=50, le=100),
    firestore: FirestoreService = Depends(get_firestore_service)
):
    """Get all knowledge graphs for a user."""
    try:
        logger.info(f"Retrieving graphs for user {user_id}")
        
        graphs = await firestore.get_user_graphs(user_id, limit)
        
        # Convert to API response format
        response = []
        for graph in graphs:
            graph_data = {
                "id": graph.id,
                "name": graph.name,
                "description": graph.description,
                "user_id": graph.user_id,
                "created_at": graph.created_at,
                "updated_at": graph.updated_at,
                "receipt_ids": graph.receipt_ids,
                "total_entities": len(graph.entities),
                "total_relations": len(graph.relations),
                "entity_types": list(set(entity.type for entity in graph.entities)),
                "relation_types": list(set(relation.relation_type for relation in graph.relations))
            }
            response.append(graph_data)
        
        return {
            "success": True,
            "user_id": user_id,
            "total_graphs": len(response),
            "graphs": response
        }
        
    except Exception as e:
        logger.error(f"Error retrieving graphs for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{graph_id}")
async def get_knowledge_graph(
    graph_id: str,
    firestore: FirestoreService = Depends(get_firestore_service)
):
    """Get a specific knowledge graph with full details."""
    try:
        logger.info(f"Retrieving graph {graph_id}")
        
        graph = await firestore.get_knowledge_graph(graph_id)
        
        if not graph:
            raise HTTPException(status_code=404, detail="Knowledge graph not found")
        
        # Convert to detailed API response
        entities = []
        for entity in graph.entities:
            entity_data = {
                "id": entity.id,
                "name": entity.name,
                "type": entity.type,
                "category": entity.category,
                "attributes": entity.attributes,
                "confidence": entity.confidence,
                "created_at": entity.created_at
            }
            entities.append(entity_data)
        
        relations = []
        for relation in graph.relations:
            relation_data = {
                "id": relation.id,
                "source": relation.source_entity_id,
                "target": relation.target_entity_id,
                "type": relation.relation_type,
                "weight": relation.weight,
                "attributes": relation.attributes,
                "receipt_id": relation.receipt_id,
                "transaction_date": relation.transaction_date,
                "created_at": relation.created_at
            }
            relations.append(relation_data)
        
        return {
            "success": True,
            "graph": {
                "id": graph.id,
                "name": graph.name,
                "description": graph.description,
                "user_id": graph.user_id,
                "created_at": graph.created_at,
                "updated_at": graph.updated_at,
                "receipt_ids": graph.receipt_ids,
                "entities": entities,
                "relations": relations,
                "summary": {
                    "total_entities": len(entities),
                    "total_relations": len(relations),
                    "entity_types": list(set(entity["type"] for entity in entities)),
                    "relation_types": list(set(relation["type"] for relation in relations))
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving graph {graph_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{graph_id}")
async def delete_knowledge_graph(
    graph_id: str,
    firestore: FirestoreService = Depends(get_firestore_service)
):
    """Delete a knowledge graph."""
    try:
        logger.info(f"Deleting graph {graph_id}")
        
        success = await firestore.delete_knowledge_graph(graph_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Knowledge graph not found or could not be deleted")
        
        return {
            "success": True,
            "message": f"Knowledge graph {graph_id} deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting graph {graph_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/{user_id}")
async def get_user_analytics(
    user_id: str,
    firestore: FirestoreService = Depends(get_firestore_service)
):
    """Get analytics across all user graphs for Ecospend integration."""
    try:
        logger.info(f"Generating analytics for user {user_id}")
        
        graphs = await firestore.get_user_graphs(user_id, limit=100)
        
        if not graphs:
            return {
                "success": True,
                "user_id": user_id,
                "analytics": {
                    "total_graphs": 0,
                    "total_entities": 0,
                    "total_relations": 0,
                    "spending_by_category": {},
                    "frequent_merchants": [],
                    "top_products": []
                }
            }
        
        # Aggregate analytics
        total_entities = sum(len(graph.entities) for graph in graphs)
        total_relations = sum(len(graph.relations) for graph in graphs)
        
        # Category spending analysis
        spending_by_category = {}
        merchant_spending = {}
        product_frequency = {}
        
        for graph in graphs:
            for entity in graph.entities:
                if entity.type == "product":
                    category = entity.category or "other"
                    price = entity.attributes.get("price", 0)
                    
                    spending_by_category[category] = spending_by_category.get(category, 0) + price
                    product_frequency[entity.name] = product_frequency.get(entity.name, 0) + 1
                
                elif entity.type == "merchant":
                    merchant_name = entity.name
                    total_amount = entity.attributes.get("total_amount", 0)
                    merchant_spending[merchant_name] = merchant_spending.get(merchant_name, 0) + total_amount
        
        # Top merchants and products
        frequent_merchants = sorted(merchant_spending.items(), key=lambda x: x[1], reverse=True)[:10]
        top_products = sorted(product_frequency.items(), key=lambda x: x[1], reverse=True)[:10]
        
        analytics = {
            "total_graphs": len(graphs),
            "total_entities": total_entities,
            "total_relations": total_relations,
            "spending_by_category": spending_by_category,
            "frequent_merchants": [{"name": name, "total_spent": amount} for name, amount in frequent_merchants],
            "top_products": [{"name": name, "purchase_count": count} for name, count in top_products],
            "graph_ids": [graph.id for graph in graphs]
        }
        
        return {
            "success": True,
            "user_id": user_id,
            "analytics": analytics,
            "ready_for_ecospend": total_entities > 0,  # Flag for Ecospend integration
            "ready_for_gwallet": len(graphs) > 0  # Flag for Google Wallet integration
        }
        
    except Exception as e:
        logger.error(f"Error generating analytics for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
