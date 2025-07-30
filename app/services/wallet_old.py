"""
Google Wallet API service for handling wallet operations.
"""

import time
import json
import requests
from typing import Dict, Any
import jwt
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from ..utils.config import settings
from ..utils.logging import LoggerMixin


"""
Google Wallet API service for handling wallet operations.
"""

import time
import json
import requests
from typing import Dict, Any
import jwt
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from ..utils.config import settings
from ..utils.logging import LoggerMixin


class GoogleWalletService(LoggerMixin):
    """Service for Google Wallet API operations."""
    
    def __init__(self):
        self.issuer_id = settings.google_wallet_issuer_id
        
        # Get credentials path (base64 or file)
        credentials_path = settings.get_wallet_credentials_path()
        if not credentials_path:
            raise ValueError("No wallet credentials found")
        
        self.service_account_file = credentials_path
        self.base_url = "https://walletobjects.googleapis.com/walletobjects/v1"
        
        # Load service account credentials
        self.credentials = service_account.Credentials.from_service_account_file(
            self.service_account_file,
            scopes=['https://www.googleapis.com/auth/wallet_object.issuer']
        )
        
        # Load the private key separately for JWT signing
        with open(self.service_account_file, 'r') as f:
            self.service_account_info = json.load(f)
        self.private_key = self.service_account_info['private_key']
        self.service_account_email = self.service_account_info['client_email']
        
        # Pass class IDs
        self.receipt_class_id = f"{self.issuer_id}.receipt_pass"  
        self.warranty_class_id = f"{self.issuer_id}.warranty_pass"
        
        self.logger.info("Google Wallet Service initialized")
    
    def get_access_token(self) -> str:
        """Get fresh access token for Google Wallet API."""
        try:
            request = Request()
            self.credentials.refresh(request)
            return self.credentials.token
        except Exception as e:
            self.log_error("get_access_token", e)
            raise
    
    def create_receipt_pass_object(self, receipt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Google Wallet generic object for a receipt."""
        try:
            pass_id = f"receipt_{receipt_data['receipt_id']}"
            object_id = f"{self.issuer_id}.{pass_id}"
            
            # Create the generic object according to Google Wallet API spec
            generic_object = {
                "id": object_id,
                "classId": self.receipt_class_id,
                "genericType": "GENERIC_TYPE_UNSPECIFIED",
                "hexBackgroundColor": "#6C5DD3",  # Raseed brand color
                
                "logo": {
                    "sourceUri": {
                        "uri": "https://storage.googleapis.com/raseed-assets/raseed_logo.png"
                    },
                    "contentDescription": {
                        "defaultValue": {
                            "language": "en-US",
                            "value": "Raseed Logo"
                        }
                    }
                },
                
                "cardTitle": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": "Receipt"
                    }
                },
                
                "header": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": receipt_data.get('merchant_name', 'Unknown Merchant')
                    }
                },
                
                "subheader": {
                    "defaultValue": {
                        "language": "en-US", 
                        "value": f"{receipt_data.get('currency', 'USD')} {receipt_data.get('total_amount', 0.00):.2f}"
                    }
                },
                
                "textModulesData": [
                    {
                        "id": "text_module_1",
                        "header": "Receipt Details",
                        "body": f"{receipt_data.get('item_count', 0)} items • {receipt_data.get('transaction_date', 'Unknown date')}"
                    },
                    {
                        "id": "text_module_2", 
                        "header": "Receipt ID",
                        "body": receipt_data['receipt_id']
                    }
                ],
                
                "barcode": {
                    "type": "QR_CODE",
                    "value": f"raseed://receipt/{receipt_data['receipt_id']}"
                },
                
                "linksModuleData": {
                    "uris": [{
                        "uri": f"https://raseed-app.com/receipt/{receipt_data['receipt_id']}",
                        "description": "View in Raseed App"
                    }]
                }
            }
            
            self.logger.info(f"Created receipt pass object for receipt {receipt_data['receipt_id']}")
            return generic_object
            
        except Exception as e:
            self.log_error("create_receipt_pass_object", e)
            raise
    
    def create_warranty_pass_object(self, warranty_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Google Wallet generic object for a warranty."""
        try:
            pass_id = f"warranty_{warranty_data['receipt_id']}_{warranty_data['product_name'].replace(' ', '_').lower()}"
            object_id = f"{self.issuer_id}.{pass_id}"
            
            generic_object = {
                "id": object_id,
                "classId": self.warranty_class_id,
                "genericType": "GENERIC_TYPE_UNSPECIFIED",
                "hexBackgroundColor": "#FF6B35",  # Orange for warranties
                
                "logo": {
                    "sourceUri": {
                        "uri": "https://storage.googleapis.com/raseed-assets/warranty_logo.png"
                    },
                    "contentDescription": {
                        "defaultValue": {
                            "language": "en-US",
                            "value": "Warranty Logo"
                        }
                    }
                },
                
                "cardTitle": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": "Warranty"
                    }
                },
                
                "header": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": warranty_data.get('product_name', 'Unknown Product')
                    }
                },
                
                "subheader": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": warranty_data.get('brand', 'Unknown Brand')
                    }
                },
                
                "textModulesData": [
                    {
                        "id": "text_module_1",
                        "header": "Warranty Details",
                        "body": f"{warranty_data.get('warranty_period', 'Unknown')} • Expires: {warranty_data.get('expiry_date', 'Unknown')}"
                    },
                    {
                        "id": "text_module_2",
                        "header": "Product Info",
                        "body": f"Purchased: {warranty_data.get('purchase_date', 'Unknown')} • Receipt: {warranty_data.get('receipt_id', 'Unknown')}"
                    }
                ],
                
                "barcode": {
                    "type": "QR_CODE", 
                    "value": f"raseed://warranty/{warranty_data['receipt_id']}/{warranty_data['product_name']}"
                },
                
                "linksModuleData": {
                    "uris": [{
                        "uri": f"https://raseed-app.com/warranty/{warranty_data['receipt_id']}/{warranty_data['product_name']}",
                        "description": "View in Raseed App"
                    }]
                }
            }
            
            self.logger.info(f"Created warranty pass object for {warranty_data['product_name']}")
            return generic_object
            
        except Exception as e:
            self.log_error("create_warranty_pass_object", e)
            raise
    
    def insert_object_to_google_wallet(self, generic_object: Dict[str, Any]) -> bool:
        """Insert the generic object into Google Wallet via API."""
        try:
            access_token = self.get_access_token()
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/genericObject"
            
            response = requests.post(url, json=generic_object, headers=headers)
            
            if response.status_code == 200:
                self.logger.info(f"Successfully inserted object {generic_object['id']} to Google Wallet")
                return True
            elif response.status_code == 409:
                # Object already exists - try to update it
                self.logger.info(f"Object {generic_object['id']} already exists, attempting update")
                return self.update_object_in_google_wallet(generic_object)
            else:
                self.logger.error(f"Failed to insert object to Google Wallet: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_error("insert_object_to_google_wallet", e)
            return False
    
    def update_object_in_google_wallet(self, generic_object: Dict[str, Any]) -> bool:
        """Update an existing object in Google Wallet."""
        try:
            access_token = self.get_access_token()
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            object_id = generic_object['id']
            url = f"{self.base_url}/genericObject/{object_id}"
            
            response = requests.put(url, json=generic_object, headers=headers)
            
            if response.status_code == 200:
                self.logger.info(f"Successfully updated object {object_id} in Google Wallet")
                return True
            else:
                self.logger.error(f"Failed to update object in Google Wallet: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_error("update_object_in_google_wallet", e)
            return False
    
    def sign_jwt(self, generic_object: Dict[str, Any]) -> str:
        """Sign a JWT token for Google Wallet."""
        try:
            # Create JWT payload
            now = int(time.time())
            payload = {
                "iss": self.service_account_email,
                "aud": "google", 
                "typ": "savetowallet",
                "iat": now,
                "payload": {
                    "genericObjects": [generic_object]
                }
            }
            
            # Sign the JWT with the private key
            token = jwt.encode(
                payload,
                self.private_key,
                algorithm="RS256",
                headers={"alg": "RS256", "typ": "JWT"}
            )
            
            self.logger.info(f"Successfully signed JWT for pass {generic_object['id']}")
            return token
            
        except Exception as e:
            self.log_error("sign_jwt", e)
            raise
    
    def create_wallet_save_url(self, jwt_token: str) -> str:
        """Create the Google Wallet save URL."""
        return f"https://pay.google.com/gp/v/save/{jwt_token}"
    
    async def create_pass_classes_if_needed(self) -> bool:
        """Create pass classes if they don't exist."""
        try:
            # Classes should be created using the create_wallet_classes.py script
            self.logger.info("Pass classes should be created using create_wallet_classes.py script")
            return True
            
        except Exception as e:
            self.log_error("create_pass_classes_if_needed", e)
            return False


class GoogleWalletService(LoggerMixin):
    """Service for Google Wallet API operations."""
    
    def __init__(self):
        self.issuer_id = settings.google_wallet_issuer_id
        
        # Get credentials path (base64 or file)
        credentials_path = settings.get_wallet_credentials_path()
        if not credentials_path:
            raise ValueError("No wallet credentials found")
        
        self.service_account_file = credentials_path
        self.base_url = "https://walletobjects.googleapis.com/walletobjects/v1"
        
        # Load service account credentials
        self.credentials = service_account.Credentials.from_service_account_file(
            self.service_account_file,
            scopes=['https://www.googleapis.com/auth/wallet_object.issuer']
        )
        
        # Load the private key separately for JWT signing
        with open(self.service_account_file, 'r') as f:
            self.service_account_info = json.load(f)
        self.private_key = self.service_account_info['private_key']
        self.service_account_email = self.service_account_info['client_email']
        
        # Pass class IDs
        self.receipt_class_id = f"{self.issuer_id}.receipt_pass"  
        self.warranty_class_id = f"{self.issuer_id}.warranty_pass"
        
        self.logger.info("Google Wallet Service initialized")
    
    def get_access_token(self) -> str:
        """Get fresh access token for Google Wallet API."""
        try:
            request = Request()
            self.credentials.refresh(request)
            return self.credentials.token
        except Exception as e:
            self.log_error("get_access_token", e)
            raise
    
    def create_receipt_pass_object(self, receipt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Google Wallet generic object for a receipt."""
        try:
            pass_id = f"receipt_{receipt_data['receipt_id']}"
            object_id = f"{self.issuer_id}.{pass_id}"
            
            # Create the generic object according to Google Wallet API spec
            generic_object = {
                "id": object_id,
                "classId": self.receipt_class_id,
                "genericType": "GENERIC_TYPE_UNSPECIFIED",
                "hexBackgroundColor": "#6C5DD3",  # Raseed brand color
                
                "logo": {
                    "sourceUri": {
                        "uri": "https://storage.googleapis.com/raseed-assets/raseed_logo.png"
                    },
                    "contentDescription": {
                        "defaultValue": {
                            "language": "en-US",
                            "value": "Raseed Logo"
                        }
                    }
                },
                
                "cardTitle": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": "Receipt"
                    }
                },
                
                "header": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": receipt_data.get('merchant_name', 'Unknown Merchant')
                    }
                },
                
                "subheader": {
                    "defaultValue": {
                        "language": "en-US", 
                        "value": f"{receipt_data.get('currency', 'USD')} {receipt_data.get('total_amount', 0.00):.2f}"
                    }
                },
                
                "textModulesData": [
                    {
                        "id": "text_module_1",
                        "header": "Receipt Details",
                        "body": f"{receipt_data.get('item_count', 0)} items • {receipt_data.get('transaction_date', 'Unknown date')}"
                    },
                    {
                        "id": "text_module_2", 
                        "header": "Receipt ID",
                        "body": receipt_data['receipt_id']
                    }
                ],
                
                "barcode": {
                    "type": "QR_CODE",
                    "value": f"raseed://receipt/{receipt_data['receipt_id']}"
                },
                
                "linksModuleData": {
                    "uris": [{
                        "uri": f"https://raseed-app.com/receipt/{receipt_data['receipt_id']}",
                        "description": "View in Raseed App"
                    }]
                }
            }
            
            self.logger.info(f"Created receipt pass object for receipt {receipt_data['receipt_id']}")
            return generic_object
            
        except Exception as e:
            self.log_error("create_receipt_pass_object", e)
            raise
    
    def create_warranty_pass_object(self, warranty_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Google Wallet generic object for a warranty."""
        try:
            pass_id = f"warranty_{warranty_data['receipt_id']}_{warranty_data['product_name'].replace(' ', '_').lower()}"
            object_id = f"{self.issuer_id}.{pass_id}"
            
            generic_object = {
                "id": object_id,
                "classId": self.warranty_class_id,
                "genericType": "GENERIC_TYPE_UNSPECIFIED",
                "hexBackgroundColor": "#FF6B35",  # Orange for warranties
                
                "logo": {
                    "sourceUri": {
                        "uri": "https://storage.googleapis.com/raseed-assets/warranty_logo.png"
                    },
                    "contentDescription": {
                        "defaultValue": {
                            "language": "en-US",
                            "value": "Warranty Logo"
                        }
                    }
                },
                
                "cardTitle": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": "Warranty"
                    }
                },
                
                "header": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": warranty_data.get('product_name', 'Unknown Product')
                    }
                },
                
                "subheader": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": warranty_data.get('brand', 'Unknown Brand')
                    }
                },
                
                "textModulesData": [
                    {
                        "id": "text_module_1",
                        "header": "Warranty Details",
                        "body": f"{warranty_data.get('warranty_period', 'Unknown')} • Expires: {warranty_data.get('expiry_date', 'Unknown')}"
                    },
                    {
                        "id": "text_module_2",
                        "header": "Product Info",
                        "body": f"Purchased: {warranty_data.get('purchase_date', 'Unknown')} • Receipt: {warranty_data.get('receipt_id', 'Unknown')}"
                    }
                ],
                
                "barcode": {
                    "type": "QR_CODE", 
                    "value": f"raseed://warranty/{warranty_data['receipt_id']}/{warranty_data['product_name']}"
                },
                
                "linksModuleData": {
                    "uris": [{
                        "uri": f"https://raseed-app.com/warranty/{warranty_data['receipt_id']}/{warranty_data['product_name']}",
                        "description": "View in Raseed App"
                    }]
                }
            }
            
            self.logger.info(f"Created warranty pass object for {warranty_data['product_name']}")
            return generic_object
            
        except Exception as e:
            self.log_error("create_warranty_pass_object", e)
            raise
    
    def insert_object_to_google_wallet(self, generic_object: Dict[str, Any]) -> bool:
        """Insert the generic object into Google Wallet via API."""
        try:
            access_token = self.get_access_token()
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/genericObject"
            
            response = requests.post(url, json=generic_object, headers=headers)
            
            if response.status_code == 200:
                self.logger.info(f"Successfully inserted object {generic_object['id']} to Google Wallet")
                return True
            elif response.status_code == 409:
                # Object already exists - try to update it
                self.logger.info(f"Object {generic_object['id']} already exists, attempting update")
                return self.update_object_in_google_wallet(generic_object)
            else:
                self.logger.error(f"Failed to insert object to Google Wallet: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_error("insert_object_to_google_wallet", e)
            return False
    
    def update_object_in_google_wallet(self, generic_object: Dict[str, Any]) -> bool:
        """Update an existing object in Google Wallet."""
        try:
            access_token = self.get_access_token()
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            object_id = generic_object['id']
            url = f"{self.base_url}/genericObject/{object_id}"
            
            response = requests.put(url, json=generic_object, headers=headers)
            
            if response.status_code == 200:
                self.logger.info(f"Successfully updated object {object_id} in Google Wallet")
                return True
            else:
                self.logger.error(f"Failed to update object in Google Wallet: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_error("update_object_in_google_wallet", e)
            return False
    
    def sign_jwt(self, generic_object: Dict[str, Any]) -> str:
        """Sign a JWT token for Google Wallet."""
        try:
            # Create JWT payload
            now = int(time.time())
            payload = {
                "iss": self.service_account_email,
                "aud": "google", 
                "typ": "savetowallet",
                "iat": now,
                "payload": {
                    "genericObjects": [generic_object]
                }
            }
            
            # Sign the JWT with the private key
            token = jwt.encode(
                payload,
                self.private_key,
                algorithm="RS256",
                headers={"alg": "RS256", "typ": "JWT"}
            )
            
            self.logger.info(f"Successfully signed JWT for pass {generic_object['id']}")
            return token
            
        except Exception as e:
            self.log_error("sign_jwt", e)
            raise
    
    def create_wallet_save_url(self, jwt_token: str) -> str:
        """Create the Google Wallet save URL."""
        return f"https://pay.google.com/gp/v/save/{jwt_token}"
    
    async def create_pass_classes_if_needed(self) -> bool:
        """Create pass classes if they don't exist."""
        try:
            # Classes should be created using the create_wallet_classes.py script
            self.logger.info("Pass classes should be created using create_wallet_classes.py script")
            return True
            
        except Exception as e:
            self.log_error("create_pass_classes_if_needed", e)
            return False
