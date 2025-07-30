from typing import List, Optional, Dict, Any
from datetime import datetime, date
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import FieldFilter, Query

from ..models.receipt import Receipt, ReceiptSearchQuery, ReceiptSummary
from ..models.knowledge_graph import KnowledgeGraph, GraphEntity, GraphRelation
from ..utils.config import settings
from ..utils.logging import get_logger, LoggerMixin


class FirestoreService(LoggerMixin):
    """Service for managing Firestore operations including knowledge graphs."""
    
    def __init__(self):
        self.db = None
        self._initialize_firestore()
        
    def _initialize_firestore(self):
        """Initialize Firestore connection."""
        try:
            if not firebase_admin._apps:
                # Initialize Firebase Admin SDK
                # First try Firebase-specific credentials (base64)
                firebase_creds_dict = settings.get_firebase_credentials_dict()
                if firebase_creds_dict:
                    cred = credentials.Certificate(firebase_creds_dict)
                    project_id = settings.firebase_project_id or settings.google_cloud_project_id
                    firebase_admin.initialize_app(cred, {
                        'projectId': project_id,
                        'databaseURL': settings.firebase_database_url
                    })
                else:
                    # Fallback to Document AI credentials (base64)
                    doc_ai_creds_dict = settings.get_document_ai_credentials_dict()
                    if doc_ai_creds_dict:
                        cred = credentials.Certificate(doc_ai_creds_dict)
                        firebase_admin.initialize_app(cred, {
                            'projectId': settings.google_cloud_project_id,
                        })
                    else:
                        # Use default credentials (for Cloud Run, etc.)
                        firebase_admin.initialize_app()
            
            # Initialize Firestore client
            self.db = firestore.client()
            self.logger.info("Firestore service initialized")
            
        except Exception as e:
            self.log_error("firestore_initialization", e)
            raise
    
    async def save_receipt(self, receipt: Receipt) -> str:
        """Save a receipt to Firestore."""
        try:
            self.log_operation("save_receipt", receipt_id=receipt.id)
            
            # Convert receipt to dictionary
            receipt_data = receipt.to_dict()
            
            # Save to Firestore
            doc_ref = self.db.collection('receipts').document(receipt.id)
            doc_ref.set(receipt_data)
            
            self.log_operation("save_receipt_completed", receipt_id=receipt.id)
            return receipt.id
            
        except Exception as e:
            self.log_error("save_receipt", e, receipt_id=receipt.id)
            raise
    
    async def get_receipt(self, receipt_id: str) -> Optional[Receipt]:
        """Get a receipt by ID."""
        try:
            self.log_operation("get_receipt", receipt_id=receipt_id)
            
            doc_ref = self.db.collection('receipts').document(receipt_id)
            doc = doc_ref.get()
            
            if doc.exists:
                receipt = Receipt.from_dict(doc.to_dict())
                self.log_operation("get_receipt_found", receipt_id=receipt_id)
                return receipt
            else:
                self.log_operation("get_receipt_not_found", receipt_id=receipt_id)
                return None
                
        except Exception as e:
            self.log_error("get_receipt", e, receipt_id=receipt_id)
            raise
    
    async def get_receipts_by_user(
        self, 
        user_id: str, 
        limit: int = 50,
        offset: int = 0
    ) -> List[Receipt]:
        """Get receipts for a specific user."""
        try:
            self.log_operation("get_receipts_by_user", user_id=user_id, limit=limit)
            
            query = (
                self.db.collection('receipts')
                .where(filter=FieldFilter('user_id', '==', user_id))
                .order_by('created_at', direction=firestore.Query.DESCENDING)
                .limit(limit)
                .offset(offset)
            )
            
            docs = query.stream()
            receipts = [Receipt.from_dict(doc.to_dict()) for doc in docs]
            
            self.log_operation(
                "get_receipts_by_user_completed", 
                user_id=user_id, 
                count=len(receipts)
            )
            return receipts
            
        except Exception as e:
            self.log_error("get_receipts_by_user", e, user_id=user_id)
            raise
    
    async def search_receipts(
        self, 
        query: ReceiptSearchQuery,
        limit: int = 50,
        offset: int = 0
    ) -> List[Receipt]:
        """Search receipts based on query parameters."""
        try:
            self.log_operation("search_receipts", limit=limit)
            
            # Start with base collection
            firestore_query = self.db.collection('receipts')
            
            # Add filters based on search query
            if query.user_id:
                firestore_query = firestore_query.where(
                    filter=FieldFilter('user_id', '==', query.user_id)
                )
            
            if query.merchant_name:
                firestore_query = firestore_query.where(
                    filter=FieldFilter('merchant_name', '>=', query.merchant_name)
                ).where(
                    filter=FieldFilter('merchant_name', '<=', query.merchant_name + '\uf8ff')
                )
            
            if query.category:
                firestore_query = firestore_query.where(
                    filter=FieldFilter('category', '==', query.category)
                )
            
            if query.min_amount is not None:
                firestore_query = firestore_query.where(
                    filter=FieldFilter('total_amount', '>=', query.min_amount)
                )
            
            if query.max_amount is not None:
                firestore_query = firestore_query.where(
                    filter=FieldFilter('total_amount', '<=', query.max_amount)
                )
            
            if query.start_date:
                firestore_query = firestore_query.where(
                    filter=FieldFilter('date', '>=', query.start_date.isoformat())
                )
            
            if query.end_date:
                firestore_query = firestore_query.where(
                    filter=FieldFilter('date', '<=', query.end_date.isoformat())
                )
            
            if query.payment_method:
                firestore_query = firestore_query.where(
                    filter=FieldFilter('payment_method', '==', query.payment_method)
                )
            
            # Order and limit results
            firestore_query = (
                firestore_query
                .order_by('created_at', direction=firestore.Query.DESCENDING)
                .limit(limit)
                .offset(offset)
            )
            
            # Execute query
            docs = firestore_query.stream()
            receipts = [Receipt.from_dict(doc.to_dict()) for doc in docs]
            
            self.log_operation("search_receipts_completed", count=len(receipts))
            return receipts
            
        except Exception as e:
            self.log_error("search_receipts", e)
            raise
    
    async def update_receipt(self, receipt: Receipt) -> bool:
        """Update an existing receipt."""
        try:
            self.log_operation("update_receipt", receipt_id=receipt.id)
            
            # Update timestamp
            receipt.updated_at = datetime.utcnow()
            
            # Convert to dictionary
            receipt_data = receipt.to_dict()
            
            # Update in Firestore
            doc_ref = self.db.collection('receipts').document(receipt.id)
            doc_ref.set(receipt_data, merge=True)
            
            self.log_operation("update_receipt_completed", receipt_id=receipt.id)
            return True
            
        except Exception as e:
            self.log_error("update_receipt", e, receipt_id=receipt.id)
            raise
    
    async def delete_receipt(self, receipt_id: str) -> bool:
        """Delete a receipt."""
        try:
            self.log_operation("delete_receipt", receipt_id=receipt_id)
            
            doc_ref = self.db.collection('receipts').document(receipt_id)
            doc_ref.delete()
            
            self.log_operation("delete_receipt_completed", receipt_id=receipt_id)
            return True
            
        except Exception as e:
            self.log_error("delete_receipt", e, receipt_id=receipt_id)
            raise
    
    async def get_receipt_analytics(
        self, 
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> ReceiptSummary:
        """Get analytics summary for receipts."""
        try:
            self.log_operation("get_receipt_analytics", user_id=user_id)
            
            # Build query
            query = self.db.collection('receipts').where(
                filter=FieldFilter('user_id', '==', user_id)
            )
            
            if start_date:
                query = query.where(
                    filter=FieldFilter('date', '>=', start_date.isoformat())
                )
            
            if end_date:
                query = query.where(
                    filter=FieldFilter('date', '<=', end_date.isoformat())
                )
            
            # Get all matching receipts
            docs = query.stream()
            receipts = [Receipt.from_dict(doc.to_dict()) for doc in docs]
            
            # Calculate analytics
            if not receipts:
                return ReceiptSummary(
                    total_receipts=0,
                    total_amount=0.0,
                    average_amount=0.0,
                    currency="USD",
                    date_range={},
                    top_merchants=[],
                    category_breakdown={},
                    monthly_spending={}
                )
            
            total_amount = sum(r.total_amount for r in receipts)
            average_amount = total_amount / len(receipts)
            
            # Get date range
            dates = [r.date for r in receipts]
            date_range = {
                "start": min(dates),
                "end": max(dates)
            }
            
            # Top merchants
            merchant_totals = {}
            for receipt in receipts:
                merchant = receipt.merchant_name
                merchant_totals[merchant] = merchant_totals.get(merchant, 0) + receipt.total_amount
            
            top_merchants = [
                {"name": merchant, "total": total}
                for merchant, total in sorted(
                    merchant_totals.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:10]
            ]
            
            # Category breakdown
            category_totals = {}
            for receipt in receipts:
                category = receipt.category
                category_totals[category] = category_totals.get(category, 0) + receipt.total_amount
            
            # Monthly spending
            monthly_totals = {}
            for receipt in receipts:
                month_key = receipt.date.strftime("%Y-%m")
                monthly_totals[month_key] = monthly_totals.get(month_key, 0) + receipt.total_amount
            
            summary = ReceiptSummary(
                total_receipts=len(receipts),
                total_amount=total_amount,
                average_amount=average_amount,
                currency=receipts[0].currency if receipts else "USD",
                date_range=date_range,
                top_merchants=top_merchants,
                category_breakdown=category_totals,
                monthly_spending=monthly_totals
            )
            
            self.log_operation(
                "get_receipt_analytics_completed", 
                user_id=user_id,
                total_receipts=len(receipts)
            )
            return summary
            
        except Exception as e:
            self.log_error("get_receipt_analytics", e, user_id=user_id)
            raise
    
    async def bulk_update_receipts(self, receipts: List[Receipt]) -> int:
        """Bulk update multiple receipts."""
        try:
            self.log_operation("bulk_update_receipts", count=len(receipts))
            
            # Use batch writes for efficiency
            batch = self.db.batch()
            
            for receipt in receipts:
                receipt.updated_at = datetime.utcnow()
                doc_ref = self.db.collection('receipts').document(receipt.id)
                batch.set(doc_ref, receipt.to_dict(), merge=True)
            
            # Commit batch
            batch.commit()
            
            self.log_operation("bulk_update_receipts_completed", count=len(receipts))
            return len(receipts)
            
        except Exception as e:
            self.log_error("bulk_update_receipts", e, count=len(receipts))
    
    # ===== KNOWLEDGE GRAPH OPERATIONS =====
    
    # ===== ENHANCED KNOWLEDGE GRAPH METHODS =====
    
    async def save_comprehensive_knowledge_graph(self, comprehensive_data: Dict[str, Any]) -> str:
        """Save comprehensive knowledge graph with enhanced format and daily organization."""
        try:
            receipt_id = comprehensive_data.get("receipt_id", f"RCP-{datetime.utcnow().strftime('%Y%m%d')}-UNKNOWN")
            
            self.log_operation("save_comprehensive_knowledge_graph", receipt_id=receipt_id)
            
            # Add Firestore timestamp
            comprehensive_data["firestore_timestamp"] = self._get_firestore_timestamp(None)
            
            # Extract date from receipt for daily organization (use today's date as default)
            daily_date = datetime.utcnow().strftime("%Y-%m-%d")
            
            # Try to extract date from created_at if available
            created_at = comprehensive_data.get("created_at")
            if created_at:
                try:
                    if isinstance(created_at, str):
                        # Parse ISO format
                        parsed_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        daily_date = parsed_date.strftime("%Y-%m-%d")
                except Exception:
                    # Use today's date if parsing fails
                    daily_date = datetime.utcnow().strftime("%Y-%m-%d")
            
            # Save to daily_receipts collection as shown in screenshot: daily_receipts -> {date} -> {receipt_id}
            daily_receipt_ref = self.db.collection('daily_receipts').document(daily_date).collection('receipts').document(receipt_id)
            daily_receipt_ref.set(comprehensive_data)
            
            # Also save to main comprehensive receipts collection for backward compatibility
            receipts_ref = self.db.collection('comprehensive_receipts').document(receipt_id)
            receipts_ref.set(comprehensive_data)
            
            self.log_operation("save_comprehensive_knowledge_graph_completed", receipt_id=receipt_id)
            return receipt_id
            
        except Exception as e:
            self.log_error("save_comprehensive_knowledge_graph", e, receipt_id=receipt_id)
            raise
    
    async def get_comprehensive_receipt(self, receipt_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive receipt by ID."""
        try:
            self.log_operation("get_comprehensive_receipt", receipt_id=receipt_id)
            
            doc_ref = self.db.collection('comprehensive_receipts').document(receipt_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                self.log_operation("get_comprehensive_receipt_found", receipt_id=receipt_id)
                return data
            else:
                self.log_operation("get_comprehensive_receipt_not_found", receipt_id=receipt_id)
                return None
                
        except Exception as e:
            self.log_error("get_comprehensive_receipt", e, receipt_id=receipt_id)
            raise
    
    async def get_user_comprehensive_receipts(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all comprehensive receipts for a user."""
        try:
            self.log_operation("get_user_comprehensive_receipts", user_id=user_id, limit=limit)
            
            # Query comprehensive receipts collection
            docs = self.db.collection('comprehensive_receipts')\
                .where(filter=FieldFilter('metadata.user_id', '==', user_id))\
                .order_by('created_at', direction=firestore.Query.DESCENDING)\
                .limit(limit)\
                .stream()
            
            receipts = []
            for doc in docs:
                receipt_data = doc.to_dict()
                receipts.append(receipt_data)
            
            self.log_operation("get_user_comprehensive_receipts_completed", user_id=user_id, count=len(receipts))
            return receipts
            
        except Exception as e:
            self.log_error("get_user_comprehensive_receipts", e, user_id=user_id)
            raise
    
    async def get_user_daily_receipts(self, user_id: str, date: str) -> List[Dict[str, Any]]:
        """Get all receipts for a user on a specific date."""
        try:
            self.log_operation("get_user_daily_receipts", user_id=user_id, date=date)
            
            # Query user daily receipts collection
            docs = self.db.collection('user_daily_receipts').document(user_id).collection(date).stream()
            
            receipts = []
            for doc in docs:
                receipt_data = doc.to_dict()
                receipts.append(receipt_data)
            
            self.log_operation("get_user_daily_receipts_completed", user_id=user_id, date=date, count=len(receipts))
            return receipts
            
        except Exception as e:
            self.log_error("get_user_daily_receipts", e, user_id=user_id, date=date)
            raise
    
    async def get_daily_receipts(self, date: str) -> List[Dict[str, Any]]:
        """Get all receipts for a specific date across all users."""
        try:
            self.log_operation("get_daily_receipts", date=date)
            
            # Query daily receipts collection
            docs = self.db.collection('daily_receipts').document(date).collection('receipts').stream()
            
            receipts = []
            for doc in docs:
                receipt_data = doc.to_dict()
                receipts.append(receipt_data)
            
            self.log_operation("get_daily_receipts_completed", date=date, count=len(receipts))
            return receipts
            
        except Exception as e:
            self.log_error("get_daily_receipts", e, date=date)
            raise
    
    async def get_comprehensive_analytics(self, user_id: str, limit: int = 1000) -> Dict[str, Any]:
        """Get comprehensive analytics for a user."""
        try:
            self.log_operation("get_comprehensive_analytics", user_id=user_id)
            
            # Get all user's comprehensive receipts
            receipts = await self.get_user_comprehensive_receipts(user_id, limit=limit)
            
            if not receipts:
                return {
                    "total_receipts": 0,
                    "total_spending": 0.0,
                    "total_items": 0,
                    "total_warranties": 0,
                    "expiring_items": 0,
                    "business_categories": {},
                    "shopping_patterns": {},
                    "monthly_spending": {},
                    "alerts": [],
                    "top_merchants": [],
                    "brand_analysis": {}
                }
            
            # Calculate comprehensive analytics
            total_spending = sum(r.get("total_amount", 0) for r in receipts)
            total_items = sum(r.get("item_count", 0) for r in receipts)
            total_warranties = sum(r.get("warranty_count", 0) for r in receipts)
            expiring_items = sum(r.get("expiring_soon_count", 0) for r in receipts)
            
            # Business category breakdown
            business_categories = {}
            for receipt in receipts:
                category = receipt.get("business_category", "Unknown")
                business_categories[category] = business_categories.get(category, 0) + 1
            
            # Shopping pattern analysis
            shopping_patterns = {}
            for receipt in receipts:
                pattern = receipt.get("shopping_pattern", "unknown")
                shopping_patterns[pattern] = shopping_patterns.get(pattern, 0) + 1
            
            # Monthly spending
            monthly_spending = {}
            for receipt in receipts:
                try:
                    date_str = receipt.get("created_at", "")
                    if date_str:
                        month_key = date_str[:7]  # YYYY-MM
                        monthly_spending[month_key] = monthly_spending.get(month_key, 0) + receipt.get("total_amount", 0)
                except Exception:
                    continue
            
            # Collect all alerts
            all_alerts = []
            for receipt in receipts:
                all_alerts.extend(receipt.get("alerts", []))
            
            # Top merchants
            merchant_spending = {}
            for receipt in receipts:
                merchant = receipt.get("merchant_name", "Unknown")
                merchant_spending[merchant] = merchant_spending.get(merchant, 0) + receipt.get("total_amount", 0)
            
            top_merchants = [
                {"name": merchant, "total_spent": total}
                for merchant, total in sorted(merchant_spending.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            
            analytics = {
                "total_receipts": len(receipts),
                "total_spending": total_spending,
                "total_items": total_items,
                "total_warranties": total_warranties,
                "expiring_items": expiring_items,
                "business_categories": business_categories,
                "shopping_patterns": shopping_patterns,
                "monthly_spending": monthly_spending,
                "alerts": all_alerts[:20],  # Latest 20 alerts
                "top_merchants": top_merchants,
                "brand_analysis": {
                    "total_brands": sum(r.get("brand_count", 0) for r in receipts),
                    "avg_brands_per_receipt": sum(r.get("brand_count", 0) for r in receipts) / len(receipts) if receipts else 0
                },
                "average_receipt_value": total_spending / len(receipts) if receipts else 0,
                "average_items_per_receipt": total_items / len(receipts) if receipts else 0
            }
            
            self.log_operation("get_comprehensive_analytics_completed", user_id=user_id, total_receipts=len(receipts))
            return analytics
            
        except Exception as e:
            self.log_error("get_comprehensive_analytics", e, user_id=user_id)
            raise

    async def save_knowledge_graph(self, graph: 'KnowledgeGraph') -> str:
        """Save a knowledge graph to Firestore."""
        try:
            self.log_operation("save_knowledge_graph", graph_id=graph.id)
            
            # Prepare graph data for Firestore
            graph_data = {
                'id': graph.id,
                'name': graph.name,
                'description': graph.description,
                'user_id': graph.user_id,
                'created_at': graph.created_at,
                'updated_at': datetime.utcnow(),
                'receipt_ids': graph.receipt_ids,
                'total_entities': len(graph.entities),
                'total_relations': len(graph.relations),
                'entities': [self._entity_to_dict(entity) for entity in graph.entities],
                'relations': [self._relation_to_dict(relation) for relation in graph.relations],
                'metadata': {
                    'version': '1.0',
                    'source': 'graph_builder_agent'
                }
            }
            
            # Save to Firestore using graph name as document ID instead of UUID
            # This makes graphs discoverable by meaningful names like "2025-01-22_Company_Name"
            doc_ref = self.db.collection('knowledge_graphs').document(graph.name)
            doc_ref.set(graph_data)
            
            # Update user's graph count
            await self._update_user_graph_count(graph.user_id)
            
            self.logger.info(f"Knowledge graph {graph.name} (ID: {graph.id}) saved successfully with {len(graph.entities)} entities and {len(graph.relations)} relations")
            return graph.id
            
        except Exception as e:
            self.log_error("save_knowledge_graph", e, graph_id=graph.id)
            raise
    
    async def get_knowledge_graph(self, graph_id: str) -> Optional['KnowledgeGraph']:
        """Retrieve a knowledge graph from Firestore."""
        try:
            doc_ref = self.db.collection('knowledge_graphs').document(graph_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            graph_data = doc.to_dict()
            
            # Reconstruct KnowledgeGraph object
            from ..models.knowledge_graph import KnowledgeGraph
            graph = KnowledgeGraph(
                id=graph_data['id'],
                name=graph_data['name'],
                description=graph_data['description'],
                user_id=graph_data['user_id'],
                receipt_ids=graph_data.get('receipt_ids', [])
            )
            
            # Add entities
            for entity_data in graph_data.get('entities', []):
                entity = self._dict_to_entity(entity_data)
                graph.add_entity(entity)
            
            # Add relations
            for relation_data in graph_data.get('relations', []):
                relation = self._dict_to_relation(relation_data)
                graph.add_relation(relation)
            
            self.logger.info(f"Retrieved knowledge graph {graph_id}")
            return graph
            
        except Exception as e:
            self.log_error("get_knowledge_graph", e, graph_id=graph_id)
            return None
    
    async def get_user_graphs(self, user_id: str, limit: int = 50) -> List['KnowledgeGraph']:
        """Get all knowledge graphs for a user."""
        try:
            # Use the new filter syntax to avoid deprecation warning
            docs = self.db.collection('knowledge_graphs')\
                .where(filter=FieldFilter('user_id', '==', user_id))\
                .limit(limit)\
                .stream()
            
            graphs = []
            for doc in docs:
                graph_data = doc.to_dict()
                
                from ..models.knowledge_graph import KnowledgeGraph
                graph = KnowledgeGraph(
                    id=graph_data['id'],
                    name=graph_data['name'],
                    description=graph_data['description'],
                    user_id=graph_data['user_id'],
                    receipt_ids=graph_data.get('receipt_ids', [])
                )
                
                # Add entities and relations
                for entity_data in graph_data.get('entities', []):
                    entity = self._dict_to_entity(entity_data)
                    graph.add_entity(entity)
                
                for relation_data in graph_data.get('relations', []):
                    relation = self._dict_to_relation(relation_data)
                    graph.add_relation(relation)
                
                graphs.append(graph)
            
            self.logger.info(f"Retrieved {len(graphs)} graphs for user {user_id}")
            return graphs
            
        except Exception as e:
            self.log_error("get_user_graphs", e, user_id=user_id)
            return []
    
    async def delete_knowledge_graph(self, graph_id: str) -> bool:
        """Delete a knowledge graph from Firestore."""
        try:
            doc_ref = self.db.collection('knowledge_graphs').document(graph_id)
            doc_ref.delete()
            
            self.logger.info(f"Deleted knowledge graph {graph_id}")
            return True
            
        except Exception as e:
            self.log_error("delete_knowledge_graph", e, graph_id=graph_id)
            return False
    
    def _entity_to_dict(self, entity: 'GraphEntity') -> Dict[str, Any]:
        """Convert GraphEntity to dictionary for Firestore."""
        return {
            'id': entity.id,
            'name': entity.name,
            'type': entity.type,
            'category': entity.category,
            'attributes': entity.attributes,
            'confidence': entity.confidence,
            'created_at': entity.created_at
        }
    
    def _relation_to_dict(self, relation: 'GraphRelation') -> Dict[str, Any]:
        """Convert GraphRelation to dictionary for Firestore."""
        return {
            'id': relation.id,
            'source_entity_id': relation.source_entity_id,
            'target_entity_id': relation.target_entity_id,
            'relation_type': relation.relation_type,
            'weight': relation.weight,
            'attributes': relation.attributes,
            'receipt_id': relation.receipt_id,
            'transaction_date': relation.transaction_date,
            'created_at': relation.created_at
        }
    
    def _dict_to_entity(self, data: Dict[str, Any]) -> 'GraphEntity':
        """Convert dictionary to GraphEntity."""
        from ..models.knowledge_graph import GraphEntity
        return GraphEntity(
            id=data['id'],
            name=data['name'],
            type=data['type'],
            category=data.get('category'),
            attributes=data.get('attributes', {}),
            confidence=data.get('confidence', 0.0),
            created_at=data.get('created_at')
        )
    
    def _dict_to_relation(self, data: Dict[str, Any]) -> 'GraphRelation':
        """Convert dictionary to GraphRelation."""
        from ..models.knowledge_graph import GraphRelation
        return GraphRelation(
            id=data['id'],
            source_entity_id=data['source_entity_id'],
            target_entity_id=data['target_entity_id'],
            relation_type=data['relation_type'],
            weight=data.get('weight', 0.0),
            attributes=data.get('attributes', {}),
            receipt_id=data.get('receipt_id'),
            transaction_date=data.get('transaction_date'),
            created_at=data.get('created_at')
        )
    
    async def _update_user_graph_count(self, user_id: str):
        """Update user's graph count in their profile."""
        try:
            user_ref = self.db.collection('users').document(user_id)
            user_ref.update({
                'graph_count': firestore.Increment(1),
                'last_graph_created': datetime.utcnow()
            })
        except Exception:
            # User document might not exist, create it
            user_ref.set({
                'user_id': user_id,
                'graph_count': 1,
                'last_graph_created': datetime.utcnow(),
                'created_at': datetime.utcnow()
            }, merge=True)
            raise