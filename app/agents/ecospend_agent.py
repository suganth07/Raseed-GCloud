"""
Ecospend Agent for financial data integration
Based on the architecture diagram - connects Firebase graphs with bank data
"""
import asyncio
import httpx
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from ..services.firestore_service import FirestoreService
from ..utils.config import settings
from ..utils.logging import LoggerMixin


class EcospendAgent(LoggerMixin):
    """
    Agent for integrating with Ecospend API to:
    1. Fetch bank transaction data
    2. Match transactions with receipt data from Firebase
    3. Provide real-time spending insights
    4. Enable automated categorization
    """
    
    def __init__(self):
        self.firestore = FirestoreService()
        self.base_url = "https://api.ecospend.com"  # Ecospend API base URL
        self.api_key = getattr(settings, 'ecospend_api_key', None)
        self.client_id = getattr(settings, 'ecospend_client_id', None)
        self.client_secret = getattr(settings, 'ecospend_client_secret', None)
        
        if not all([self.api_key, self.client_id, self.client_secret]):
            self.logger.warning("Ecospend credentials not configured. Agent will run in mock mode.")
    
    async def authenticate(self) -> Optional[str]:
        """Authenticate with Ecospend and get access token."""
        try:
            auth_data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/oauth/token",
                    data=auth_data
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    access_token = token_data.get("access_token")
                    self.logger.info("Successfully authenticated with Ecospend")
                    return access_token
                else:
                    self.logger.error(f"Ecospend authentication failed: {response.status_code}")
                    return None
                    
        except Exception as e:
            self.log_error("ecospend_auth", e)
            return None
    
    async def get_user_accounts(self, user_id: str, access_token: str) -> List[Dict[str, Any]]:
        """Get user's bank accounts from Ecospend."""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/accounts",
                    headers=headers,
                    params={"user_id": user_id}
                )
                
                if response.status_code == 200:
                    accounts = response.json()
                    self.logger.info(f"Retrieved {len(accounts)} accounts for user {user_id}")
                    return accounts
                else:
                    self.logger.error(f"Failed to get accounts: {response.status_code}")
                    return []
                    
        except Exception as e:
            self.log_error("get_user_accounts", e, user_id=user_id)
            return []
    
    async def get_transactions(
        self, 
        account_id: str, 
        access_token: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get transactions for a specific account."""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "account_id": account_id,
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat()
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/transactions",
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 200:
                    transactions = response.json()
                    self.logger.info(f"Retrieved {len(transactions)} transactions for account {account_id}")
                    return transactions
                else:
                    self.logger.error(f"Failed to get transactions: {response.status_code}")
                    return []
                    
        except Exception as e:
            self.log_error("get_transactions", e, account_id=account_id)
            return []
    
    async def match_transactions_with_receipts(
        self, 
        user_id: str, 
        transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Match bank transactions with receipt data from Firebase."""
        try:
            self.logger.info(f"Matching {len(transactions)} transactions with receipts for user {user_id}")
            
            # Get user's knowledge graphs from Firebase
            user_graphs = await self.firestore.get_user_graphs(user_id)
            
            # Extract receipt data from graphs
            receipt_data = []
            for graph in user_graphs:
                for entity in graph.entities:
                    if entity.type == "merchant":
                        receipt_info = {
                            "merchant_name": entity.name,
                            "amount": entity.attributes.get("total_amount", 0),
                            "graph_id": graph.id,
                            "receipt_ids": graph.receipt_ids
                        }
                        receipt_data.append(receipt_info)
            
            # Match transactions with receipts
            matches = []
            unmatched_transactions = []
            unmatched_receipts = list(receipt_data)
            
            for transaction in transactions:
                transaction_amount = abs(float(transaction.get("amount", 0)))
                transaction_merchant = transaction.get("merchant_name", "").lower()
                transaction_date = transaction.get("date")
                
                best_match = None
                best_score = 0
                
                for i, receipt in enumerate(unmatched_receipts):
                    receipt_amount = abs(float(receipt["amount"]))
                    receipt_merchant = receipt["merchant_name"].lower()
                    
                    # Calculate match score
                    score = 0
                    
                    # Amount matching (within 5% tolerance)
                    if abs(transaction_amount - receipt_amount) / max(transaction_amount, receipt_amount) < 0.05:
                        score += 50
                    
                    # Merchant name matching
                    if transaction_merchant in receipt_merchant or receipt_merchant in transaction_merchant:
                        score += 30
                    
                    # Exact merchant match
                    if transaction_merchant == receipt_merchant:
                        score += 20
                    
                    if score > best_score and score >= 50:  # Minimum 50% confidence
                        best_score = score
                        best_match = (i, receipt)
                
                if best_match:
                    match_index, matched_receipt = best_match
                    matches.append({
                        "transaction": transaction,
                        "receipt": matched_receipt,
                        "confidence": best_score,
                        "match_type": "automatic"
                    })
                    unmatched_receipts.pop(match_index)
                else:
                    unmatched_transactions.append(transaction)
            
            result = {
                "user_id": user_id,
                "total_transactions": len(transactions),
                "total_receipts": len(receipt_data),
                "matches": matches,
                "unmatched_transactions": unmatched_transactions,
                "unmatched_receipts": unmatched_receipts,
                "match_rate": len(matches) / len(transactions) if transactions else 0
            }
            
            self.logger.info(f"Transaction matching completed: {len(matches)} matches, {len(unmatched_transactions)} unmatched")
            return result
            
        except Exception as e:
            self.log_error("match_transactions_with_receipts", e, user_id=user_id)
            return {"error": str(e)}
    
    async def get_spending_insights(self, user_id: str) -> Dict[str, Any]:
        """Generate spending insights using Firebase graph data and Ecospend transactions."""
        try:
            self.logger.info(f"Generating spending insights for user {user_id}")
            
            # Mock Ecospend authentication and data for demo
            if not self.api_key:
                return await self._generate_mock_insights(user_id)
            
            # Real Ecospend integration
            access_token = await self.authenticate()
            if not access_token:
                return {"error": "Failed to authenticate with Ecospend"}
            
            # Get user accounts
            accounts = await self.get_user_accounts(user_id, access_token)
            
            # Get transactions for the last 30 days
            from_date = datetime.now() - timedelta(days=30)
            to_date = datetime.now()
            
            all_transactions = []
            for account in accounts:
                transactions = await self.get_transactions(
                    account["account_id"], 
                    access_token, 
                    from_date, 
                    to_date
                )
                all_transactions.extend(transactions)
            
            # Match with receipt data
            matching_result = await self.match_transactions_with_receipts(user_id, all_transactions)
            
            # Generate insights
            insights = {
                "period": f"{from_date.date()} to {to_date.date()}",
                "total_spent": sum(abs(float(t.get("amount", 0))) for t in all_transactions),
                "transaction_count": len(all_transactions),
                "receipt_match_rate": matching_result["match_rate"],
                "verified_spending": sum(
                    abs(float(match["transaction"].get("amount", 0))) 
                    for match in matching_result["matches"]
                ),
                "categories": await self._categorize_spending(user_id, matching_result["matches"]),
                "recommendations": await self._generate_recommendations(user_id, matching_result)
            }
            
            return insights
            
        except Exception as e:
            self.log_error("get_spending_insights", e, user_id=user_id)
            return {"error": str(e)}
    
    async def _generate_mock_insights(self, user_id: str) -> Dict[str, Any]:
        """Generate mock insights for demo purposes."""
        try:
            # Get user's graph data from Firebase
            user_graphs = await self.firestore.get_user_graphs(user_id)
            
            if not user_graphs:
                return {
                    "message": "No receipt data found. Upload some receipts first!",
                    "total_spent": 0,
                    "transaction_count": 0,
                    "categories": {}
                }
            
            # Calculate insights from graph data
            total_spent = 0
            categories = {}
            
            for graph in user_graphs:
                for entity in graph.entities:
                    if entity.type == "product":
                        category = entity.category or "other"
                        price = entity.attributes.get("price", 0)
                        categories[category] = categories.get(category, 0) + price
                        total_spent += price
            
            return {
                "source": "firebase_graphs_only",
                "period": "Based on uploaded receipts",
                "total_spent": total_spent,
                "graph_count": len(user_graphs),
                "categories": categories,
                "recommendations": [
                    "Connect your bank account for real-time insights",
                    "Upload more receipts to improve accuracy",
                    f"You have {len(user_graphs)} knowledge graphs ready for bank integration"
                ],
                "ready_for_ecospend": True
            }
            
        except Exception as e:
            self.log_error("generate_mock_insights", e, user_id=user_id)
            return {"error": str(e)}
    
    async def _categorize_spending(self, user_id: str, matches: List[Dict]) -> Dict[str, float]:
        """Categorize spending using graph entity data."""
        categories = {}
        
        for match in matches:
            receipt = match["receipt"]
            amount = abs(float(match["transaction"].get("amount", 0)))
            
            # Get category from graph data
            graph_id = receipt["graph_id"]
            graph = await self.firestore.get_knowledge_graph(graph_id)
            
            if graph:
                for entity in graph.entities:
                    if entity.type == "product":
                        category = entity.category or "other"
                        categories[category] = categories.get(category, 0) + amount
                        break
        
        return categories
    
    async def _generate_recommendations(self, user_id: str, matching_result: Dict) -> List[str]:
        """Generate spending recommendations."""
        recommendations = []
        
        match_rate = matching_result["match_rate"]
        
        if match_rate < 0.5:
            recommendations.append("Upload more receipts to improve transaction matching")
        
        if len(matching_result["unmatched_transactions"]) > 0:
            recommendations.append(f"You have {len(matching_result['unmatched_transactions'])} unmatched transactions")
        
        recommendations.append("Consider setting spending limits for frequent categories")
        recommendations.append("Review unmatched transactions for potential savings")
        
        return recommendations


# Global instance
ecospend_agent = EcospendAgent()
