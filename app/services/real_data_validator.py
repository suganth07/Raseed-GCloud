"""
Real Data Validation Service

This service ensures that all Firebase and API services are using real credentials
and real data, never mock or sample data.
"""

import os
import logging
from typing import Dict, Any
from ..utils.config import settings
from ..services.firestore_service import FirestoreService

logger = logging.getLogger(__name__)


class RealDataValidator:
    """
    Validates that all services are configured with real credentials
    and accessing real data from Firebase/Firestore.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.validation_errors = []
    
    def validate_all_services(self) -> Dict[str, Any]:
        """
        Comprehensive validation of all services to ensure real data usage.
        
        Returns:
            Dict with validation results and any errors found
        """
        self.logger.info("🔍 Starting Real Data Validation...")
        
        validation_results = {
            "all_valid": True,
            "services": {},
            "errors": [],
            "warnings": []
        }
        
        # Validate Firebase/Firestore credentials
        firebase_validation = self._validate_firebase_credentials()
        validation_results["services"]["firebase"] = firebase_validation
        
        # Validate Gemini API credentials
        gemini_validation = self._validate_gemini_credentials()
        validation_results["services"]["gemini"] = gemini_validation
        
        # Validate Document AI credentials
        document_ai_validation = self._validate_document_ai_credentials()
        validation_results["services"]["document_ai"] = document_ai_validation
        
        # Check for any validation failures
        all_services_valid = all(
            result["valid"] for result in validation_results["services"].values()
        )
        
        validation_results["all_valid"] = all_services_valid
        
        if not all_services_valid:
            validation_results["errors"].append(
                "❌ One or more services are not properly configured with real credentials"
            )
        
        self._log_validation_results(validation_results)
        return validation_results
    
    def _validate_firebase_credentials(self) -> Dict[str, Any]:
        """Validate Firebase/Firestore real credentials."""
        try:
            # Check for real Firebase credentials
            has_firebase_key = bool(settings.raseed_firebase_key)
            has_credentials_json = bool(settings.credentials_json)
            has_google_app_credentials = bool(settings.google_application_credentials)
            
            # Test actual Firestore connection
            firestore_connection_valid = False
            try:
                firestore = FirestoreService()
                # Try to access a collection to verify real connection
                test_collection = firestore.db.collection('users').limit(1)
                list(test_collection.stream())  # This will fail if credentials are invalid
                firestore_connection_valid = True
                self.logger.info("✅ Firestore connection verified with real credentials")
            except Exception as e:
                self.logger.error(f"❌ Firestore connection failed: {e}")
            
            return {
                "valid": firestore_connection_valid and (has_firebase_key or has_credentials_json or has_google_app_credentials),
                "has_credentials": has_firebase_key or has_credentials_json or has_google_app_credentials,
                "connection_tested": firestore_connection_valid,
                "credential_sources": {
                    "firebase_key": has_firebase_key,
                    "credentials_json": has_credentials_json,
                    "google_app_credentials": has_google_app_credentials
                }
            }
            
        except Exception as e:
            self.logger.error(f"❌ Firebase validation error: {e}")
            return {
                "valid": False,
                "error": str(e),
                "has_credentials": False,
                "connection_tested": False
            }
    
    def _validate_gemini_credentials(self) -> Dict[str, Any]:
        """Validate Gemini API real credentials."""
        try:
            gemini_key = settings.gemini_api_key
            
            # Check if it's a real API key (not placeholder)
            is_real_key = (
                gemini_key and 
                gemini_key != "placeholder_key" and 
                gemini_key != "your_api_key_here" and
                len(gemini_key) > 10  # Real API keys are much longer
            )
            
            if not is_real_key:
                self.logger.error("❌ Gemini API key is missing or appears to be a placeholder")
                return {
                    "valid": False,
                    "error": "Gemini API key is missing or placeholder",
                    "has_real_key": False
                }
            
            # TODO: Test actual API call to verify key works
            self.logger.info("✅ Gemini API key appears to be real")
            return {
                "valid": True,
                "has_real_key": True,
                "key_length": len(gemini_key)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Gemini validation error: {e}")
            return {
                "valid": False,
                "error": str(e),
                "has_real_key": False
            }
    
    def _validate_document_ai_credentials(self) -> Dict[str, Any]:
        """Validate Document AI real credentials."""
        try:
            has_document_ai_key = bool(settings.raseed_document_ai_key)
            has_processor_id = bool(settings.document_ai_processor_id)
            has_project_id = bool(settings.google_cloud_project_id)
            
            return {
                "valid": has_document_ai_key and has_processor_id and has_project_id,
                "has_credentials": has_document_ai_key,
                "has_processor_id": has_processor_id,
                "has_project_id": has_project_id
            }
            
        except Exception as e:
            self.logger.error(f"❌ Document AI validation error: {e}")
            return {
                "valid": False,
                "error": str(e)
            }
    
    def _log_validation_results(self, results: Dict[str, Any]):
        """Log validation results in a readable format."""
        self.logger.info("🔍 Real Data Validation Results:")
        self.logger.info("=" * 50)
        
        for service_name, service_result in results["services"].items():
            status = "✅ VALID" if service_result["valid"] else "❌ INVALID"
            self.logger.info(f"{service_name.upper()}: {status}")
            
            if not service_result["valid"] and "error" in service_result:
                self.logger.error(f"  Error: {service_result['error']}")
        
        overall_status = "✅ ALL SERVICES VALID" if results["all_valid"] else "❌ VALIDATION FAILED"
        self.logger.info(f"\nOverall Status: {overall_status}")
        
        if not results["all_valid"]:
            self.logger.error("⚠️  CRITICAL: Application is not properly configured for production use!")
            self.logger.error("⚠️  Ensure all services have real credentials before deployment!")
    
    async def validate_user_data_access(self, user_id: str) -> Dict[str, Any]:
        """
        Validate that we can access real user data from Firebase.
        
        Args:
            user_id: User ID to test data access for
            
        Returns:
            Validation result showing if real user data is accessible
        """
        try:
            firestore = FirestoreService()
            
            # Check if user exists in Firebase
            user_doc = firestore.db.collection('users').document(user_id).get()
            user_exists = user_doc.exists
            
            # Check if user has real knowledge graph data
            kg_collection = firestore.db.collection('users').document(user_id).collection('knowledge_graphs')
            kg_docs = list(kg_collection.limit(5).stream())
            has_kg_data = len(kg_docs) > 0
            
            # Validate data structure of knowledge graphs
            real_data_count = 0
            for doc in kg_docs:
                if doc.exists:
                    doc_data = doc.to_dict()
                    if (doc_data and 'data' in doc_data and 
                        doc_data['data'].get('total_amount', 0) > 0):
                        real_data_count += 1
            
            result = {
                "user_exists": user_exists,
                "has_knowledge_graphs": has_kg_data,
                "knowledge_graph_count": len(kg_docs),
                "real_transaction_count": real_data_count,
                "is_real_data": real_data_count > 0,
                "validation_passed": user_exists and real_data_count > 0
            }
            
            self.logger.info(f"📊 User {user_id} data validation: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error validating user data for {user_id}: {e}")
            return {
                "user_exists": False,
                "has_knowledge_graphs": False,
                "knowledge_graph_count": 0,
                "real_transaction_count": 0,
                "is_real_data": False,
                "validation_passed": False,
                "error": str(e)
            }
    
    def ensure_no_mock_data_usage(self) -> bool:
        """
        Verify that no mock data patterns are being used in the application.
        
        Returns:
            True if no mock data usage detected, False otherwise
        """
        mock_indicators = [
            "placeholder_key",
            "your_api_key_here", 
            "sample_data",
            "mock_response",
            "fake_data",
            "dummy_data"
        ]
        
        # Check environment variables
        for key, value in os.environ.items():
            if value and any(indicator in str(value).lower() for indicator in mock_indicators):
                self.logger.error(f"❌ Mock data indicator found in environment variable {key}")
                return False
        
        # Check configuration
        for attr_name in dir(settings):
            if not attr_name.startswith('_'):
                attr_value = getattr(settings, attr_name, None)
                if attr_value and any(indicator in str(attr_value).lower() for indicator in mock_indicators):
                    self.logger.error(f"❌ Mock data indicator found in setting {attr_name}")
                    return False
        
        self.logger.info("✅ No mock data indicators found in configuration")
        return True


# Global validator instance
real_data_validator = RealDataValidator()
