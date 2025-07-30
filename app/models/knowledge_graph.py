"""
Knowledge Graph models for entity-relation representation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class GraphEntity(BaseModel):
    """Represents an entity in the knowledge graph."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Entity name")
    type: str = Field(..., description="Entity type (product, merchant, category, location, etc.)")
    category: Optional[str] = Field(None, description="Entity category for products")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Additional entity attributes")
    confidence: float = Field(default=1.0, description="Confidence in entity classification")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GraphRelation(BaseModel):
    """Represents a relationship between entities in the knowledge graph."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_entity_id: str = Field(..., description="ID of the source entity")
    target_entity_id: str = Field(..., description="ID of the target entity")
    relation_type: str = Field(..., description="Type of relationship (purchased_at, belongs_to, similar_to, etc.)")
    weight: float = Field(default=1.0, description="Strength/weight of the relationship")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Additional relation attributes")
    
    # Context
    receipt_id: Optional[str] = Field(None, description="Receipt ID that created this relation")
    transaction_date: Optional[datetime] = Field(None, description="Date of transaction")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeGraph(BaseModel):
    """Represents a complete knowledge graph for a receipt or collection of receipts."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Graph name/identifier")
    description: Optional[str] = Field(None, description="Graph description")
    
    # Graph data
    entities: List[GraphEntity] = Field(default_factory=list, description="All entities in the graph")
    relations: List[GraphRelation] = Field(default_factory=list, description="All relations in the graph")
    
    # Context
    receipt_ids: List[str] = Field(default_factory=list, description="Receipt IDs that contributed to this graph")
    user_id: Optional[str] = Field(None, description="User who owns this graph")
    
    # Statistics
    total_entities: int = Field(default=0, description="Total number of entities")
    total_relations: int = Field(default=0, description="Total number of relations")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def add_entity(self, entity: GraphEntity) -> None:
        """Add an entity to the graph."""
        self.entities.append(entity)
        self.total_entities = len(self.entities)
        self.updated_at = datetime.utcnow()
    
    def add_relation(self, relation: GraphRelation) -> None:
        """Add a relation to the graph."""
        self.relations.append(relation)
        self.total_relations = len(self.relations)
        self.updated_at = datetime.utcnow()
    
    def get_entity_by_id(self, entity_id: str) -> Optional[GraphEntity]:
        """Get entity by ID."""
        return next((e for e in self.entities if e.id == entity_id), None)
    
    def get_entities_by_type(self, entity_type: str) -> List[GraphEntity]:
        """Get all entities of a specific type."""
        return [e for e in self.entities if e.type == entity_type]
    
    def get_relations_for_entity(self, entity_id: str) -> List[GraphRelation]:
        """Get all relations involving a specific entity."""
        return [r for r in self.relations if r.source_entity_id == entity_id or r.target_entity_id == entity_id]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Firestore storage."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "entities": [entity.dict() for entity in self.entities],
            "relations": [relation.dict() for relation in self.relations],
            "receipt_ids": self.receipt_ids,
            "user_id": self.user_id,
            "total_entities": self.total_entities,
            "total_relations": self.total_relations,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeGraph":
        """Create KnowledgeGraph from dictionary."""
        entities = [GraphEntity(**entity_data) for entity_data in data.get("entities", [])]
        relations = [GraphRelation(**relation_data) for relation_data in data.get("relations", [])]
        
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            entities=entities,
            relations=relations,
            receipt_ids=data.get("receipt_ids", []),
            user_id=data.get("user_id"),
            total_entities=data.get("total_entities", len(entities)),
            total_relations=data.get("total_relations", len(relations)),
            created_at=data["created_at"],
            updated_at=data["updated_at"]
        )


class GraphAnalytics(BaseModel):
    """Analytics data for knowledge graphs."""
    graph_id: str = Field(..., description="ID of the analyzed graph")
    
    # Node analytics
    most_frequent_products: List[Dict[str, Any]] = Field(default_factory=list)
    most_frequent_merchants: List[Dict[str, Any]] = Field(default_factory=list)
    category_distribution: Dict[str, int] = Field(default_factory=dict)
    
    # Relationship analytics
    strongest_relations: List[Dict[str, Any]] = Field(default_factory=list)
    relation_type_counts: Dict[str, int] = Field(default_factory=dict)
    
    # User behavior insights
    spending_patterns: Dict[str, Any] = Field(default_factory=dict)
    purchase_frequency: Dict[str, int] = Field(default_factory=dict)
    
    # Metadata
    analysis_date: datetime = Field(default_factory=datetime.utcnow)
    total_receipts_analyzed: int = Field(default=0)
