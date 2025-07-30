#!/usr/bin/env python3
"""
Google Calendar Agent - Integrated into Raseed Backend
This module provides Google Calendar integration for warranty reminders and other calendar operations.
"""

import os
import pickle
from datetime import datetime
from typing import Dict, Any
import json

# Third-party imports
from dotenv import load_dotenv

# Google Calendar API
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Google Generative AI
import google.generativeai as genai

from ..utils.logging import LoggerMixin
from ..utils.config import settings

# Configuration
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


class GoogleCalendarAgent(LoggerMixin):
    """Google Calendar Agent with Gemini AI integration for Raseed Backend."""
    
    def __init__(self):
        """Initialize the Google Calendar Agent with Gemini AI"""
        super().__init__()
        load_dotenv()
        
        # Initialize Gemini AI
        self.gemini_client = None
        gemini_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        
        if gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                
                generation_config = {
                    "temperature": 0.7,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 1024,
                }
                
                self.gemini_client = genai.GenerativeModel(
                    model_name='gemini-1.5-flash',
                    generation_config=generation_config
                )
                
                # Set system instruction through chat
                self.system_prompt = """You are an AI assistant helping with Google Calendar management for warranty reminders.
                You can create calendar events and check upcoming events based on requests.
                
                Current date and time context:
                - Today is July 25, 2025 (Friday)
                - Current timezone: Asia/Kolkata
                - Use 24-hour format for times
                
                For creating events:
                - Extract title, date, start time, end time from user input
                - If any information is missing, politely ask the user
                - Default duration is 1 hour if not specified
                - Be conversational and helpful
                
                When I provide function results, interpret them and give a friendly response.
                Always confirm successful actions and provide helpful details."""
                self.logger.info("✅ Gemini AI initialized successfully")
            except Exception as e:
                self.logger.warning(f"Could not initialize Gemini AI: {e}")
        
        self.conversation_history = []

    def get_calendar_service(self):
        """Authenticate and return Google Calendar service."""
        # Try to get credentials from base64 first
        credentials_dict = settings.get_calendar_credentials_dict()
        token_path = os.path.join(os.path.dirname(__file__), "..", "..", "token.json")
        
        if not credentials_dict:
            self.logger.error("❌ ERROR: No calendar credentials found!")
            self.logger.info("📋 Please set CREDENTIALS_JSON environment variable")
            self.logger.info("🔗 Get credentials from: https://console.cloud.google.com/")
            raise FileNotFoundError("Google Calendar credentials required")
            
        try:
            creds = None
            if os.path.exists(token_path):
                with open(token_path, "rb") as token:
                    creds = pickle.load(token)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    self.logger.info("🔄 Refreshing Google Calendar access...")
                    creds.refresh(Request())
                else:
                    self.logger.info("🔐 First time setup - opening browser for Google Calendar authorization...")
                    self.logger.info("✅ Grant calendar permissions in the browser window")
                    self.logger.warning("⚠️ If you see 'Access blocked' error:")
                    self.logger.info("1. Go to Google Cloud Console → OAuth consent screen")
                    self.logger.info("2. Add your email as a test user")
                    self.logger.info("3. Or change User Type to 'Internal' if personal use")
                    flow = InstalledAppFlow.from_client_config(credentials_dict, SCOPES)
                    creds = flow.run_local_server(port=0)
                    self.logger.info("✅ Authorization successful!")
                
                with open(token_path, "wb") as token:
                    pickle.dump(creds, token)
            
            service = build("calendar", "v3", credentials=creds)
            self.logger.info("🔗 Connected to your real Google Calendar!")
            return service
            
        except Exception as e:
            if "access_denied" in str(e).lower():
                self.logger.error("❌ Access Denied Error!")
                self.logger.warning("Fix: Add yourself as test user in Google Cloud Console")
                self.logger.info("1. Go to: https://console.cloud.google.com/apis/credentials/consent")
                self.logger.info("2. Scroll to 'Test users' section")
                self.logger.info("3. Add your email as test user")
                self.logger.info("4. Save and try again")
            self.log_error("get_calendar_service", e)
            raise

    def create_calendar_event(
        self,
        title: str,
        start_datetime: str,
        end_datetime: str,
        description: str = "",
        location: str = ""
    ) -> Dict[str, Any]:
        """Create a Google Calendar event."""
        try:
            # Validate datetime
            start_dt = datetime.fromisoformat(start_datetime)
            end_dt = datetime.fromisoformat(end_datetime)
            
            if end_dt <= start_dt:
                return {
                    "status": "error",
                    "error_message": "End time must be after start time."
                }
            
            self.logger.info(f"📅 Creating event '{title}' in Google Calendar...")
            service = self.get_calendar_service()
            
            event_body = {
                "summary": title,
                "start": {"dateTime": start_datetime, "timeZone": "Asia/Kolkata"},
                "end": {"dateTime": end_datetime, "timeZone": "Asia/Kolkata"},
                "description": description,
                "location": location,
            }
            
            created_event = service.events().insert(calendarId="primary", body=event_body).execute()
            
            self.logger.info("✅ Event created successfully in Google Calendar!")
            self.logger.info(f"🔗 Event link: {created_event.get('htmlLink', 'N/A')}")
            
            return {
                "status": "success",
                "message": f"✅ Calendar event '{title}' created from {start_datetime} to {end_datetime}!",
                "event_id": created_event["id"],
                "event_link": created_event.get("htmlLink", ""),
                "details": {
                    "title": title,
                    "start": start_datetime,
                    "end": end_datetime,
                    "description": description,
                    "location": location
                }
            }
            
        except ValueError as e:
            return {
                "status": "error", 
                "error_message": f"Invalid datetime format. Use YYYY-MM-DDTHH:MM:SS format. Error: {e}"
            }
        except Exception as e:
            self.log_error("create_calendar_event", e)
            return {
                "status": "error",
                "error_message": f"Failed to create event: {str(e)}"
            }

    def get_upcoming_events(self, max_results: int = 10) -> Dict[str, Any]:
        """Get upcoming calendar events."""
        try:
            self.logger.info("📅 Fetching calendar events...")
            service = self.get_calendar_service()
            
            now = datetime.utcnow().isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                return {
                    "status": "success",
                    "message": "📅 No upcoming events found in Google Calendar.",
                    "events": []
                }
            
            event_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                event_list.append({
                    "title": event.get('summary', 'No title'),
                    "start": start,
                    "id": event['id'],
                    "location": event.get('location', ''),
                    "description": event.get('description', '')
                })
            
            self.logger.info(f"✅ Found {len(event_list)} events in Google Calendar!")
            
            return {
                "status": "success",
                "message": f"📅 Found {len(event_list)} upcoming events in Google Calendar:",
                "events": event_list
            }
            
        except Exception as e:
            self.log_error("get_upcoming_events", e)
            return {
                "status": "error",
                "error_message": f"Failed to fetch events: {str(e)}"
            }

    def parse_user_intent(self, user_message: str) -> Dict[str, Any]:
        """Parse user intent and extract calendar information using Gemini AI"""
        if not self.gemini_client:
            return {"action": "error", "message": "AI not available"}
        
        try:
            # Create a prompt to extract calendar information
            prompt = f"""
            {self.system_prompt}
            
            Analyze this user message and extract calendar information: "{user_message}"
            
            Today is July 25, 2025 (Friday). Current time is around 12:00 PM IST.
            
            Respond with a JSON object containing:
            {{
                "action": "create_event" | "view_events" | "chat",
                "title": "event title if creating",
                "date": "YYYY-MM-DD format if specified",
                "start_time": "HH:MM format if specified", 
                "end_time": "HH:MM format if specified",
                "duration_hours": number if duration specified,
                "description": "any additional details",
                "location": "location if mentioned",
                "missing_info": ["list of missing required information"],
                "response": "conversational response to user"
            }}
            
            For date parsing:
            - "tomorrow" = July 26, 2025
            - "next Monday" = July 28, 2025
            - "Monday" = July 28, 2025 (next Monday)
            - "next week" = week of July 28, 2025
            
            If creating an event but missing critical info, set action to "chat" and ask for missing details.
            If just viewing events, set action to "view_events".
            """
            
            response = self.gemini_client.generate_content(prompt)
            
            # Try to parse JSON from response
            try:
                # Extract JSON from response text
                response_text = response.text.strip()
                if response_text.startswith('```json'):
                    response_text = response_text.split('```json')[1].split('```')[0]
                elif response_text.startswith('```'):
                    response_text = response_text.split('```')[1].split('```')[0]
                
                return json.loads(response_text)
            except json.JSONDecodeError:
                # Fallback to simple text response
                return {
                    "action": "chat",
                    "response": response.text
                }
                
        except Exception as e:
            self.log_error("parse_user_intent", e)
            return {
                "action": "error",
                "message": f"Error parsing intent: {str(e)}"
            }

    async def process_message(self, user_message: str) -> str:
        """Process user message and perform appropriate action"""
        # Add to conversation history
        self.conversation_history.append(f"User: {user_message}")
        
        # Parse user intent
        intent = self.parse_user_intent(user_message)
        
        if intent["action"] == "create_event":
            # Check if we have all required information
            if intent.get("missing_info"):
                response = intent.get("response", "I need more information to create the event.")
                self.conversation_history.append(f"Assistant: {response}")
                return response
            
            # Create the event
            start_datetime = self._build_datetime(intent.get("date"), intent.get("start_time", "12:00"))
            end_datetime = self._build_datetime(
                intent.get("date"), 
                intent.get("end_time") or self._add_duration(intent.get("start_time", "12:00"), intent.get("duration_hours", 1))
            )
            
            result = self.create_calendar_event(
                title=intent.get("title", "New Event"),
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                description=intent.get("description", ""),
                location=intent.get("location", "")
            )
            
            if result["status"] == "success":
                response = f"✅ Perfect! I've created your event '{result['details']['title']}' on {result['details']['start']}. {result['message']}"
            else:
                response = f"❌ I encountered an issue: {result['error_message']}"
        
        elif intent["action"] == "view_events":
            result = self.get_upcoming_events()
            if result["status"] == "success" and result["events"]:
                response = "📅 Here are your upcoming events:\n\n"
                for i, event in enumerate(result["events"][:5], 1):
                    start_time = event["start"]
                    if "T" in start_time:
                        # Format datetime
                        dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%B %d, %Y at %I:%M %p")
                    else:
                        formatted_time = event["start"]
                    
                    response += f"{i}. **{event['title']}**\n   📅 {formatted_time}\n"
                    if event.get('location'):
                        response += f"   📍 {event['location']}\n"
                    response += "\n"
            else:
                response = result.get("message", "No upcoming events found.")
        
        else:
            response = intent.get("response", "I'm here to help with your calendar. You can ask me to create events or view your schedule!")
        
        self.conversation_history.append(f"Assistant: {response}")
        return response
    
    def _build_datetime(self, date: str, time: str) -> str:
        """Build ISO datetime string"""
        try:
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
            if not time:
                time = "12:00"
            
            return f"{date}T{time}:00"
        except Exception:
            return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    def _add_duration(self, start_time: str, duration_hours: float) -> str:
        """Add duration to start time"""
        try:
            hour, minute = map(int, start_time.split(':'))
            end_hour = hour + int(duration_hours)
            end_minute = minute + int((duration_hours % 1) * 60)
            
            if end_minute >= 60:
                end_hour += 1
                end_minute -= 60
            
            return f"{end_hour:02d}:{end_minute:02d}"
        except Exception:
            return start_time

    async def send_message(self, message: str) -> str:
        """Send message to agent and get response."""
        return await self.process_message(message)


def check_environment():
    """Check if environment is properly configured."""
    errors = []
    
    # Check for API key
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        errors.append("Missing GOOGLE_API_KEY or GEMINI_API_KEY in environment variables")
    
    # Check for credentials (base64)
    from ..utils.config import settings
    credentials_dict = settings.get_calendar_credentials_dict()
    if not credentials_dict:
        errors.append("Missing calendar credentials - set CREDENTIALS_JSON environment variable")
    
    if errors:
        print("❌ Setup Required for Google Calendar:")
        for error in errors:
            print(f"  • {error}")
        print("\n📋 Setup Instructions:")
        print("1. ✅ Get Gemini API key: https://aistudio.google.com/app/apikey")
        print("2. ✅ Set GEMINI_API_KEY in Backend/.env file")
        print("3. 🚨 Get Google Calendar OAuth credentials from Google Cloud Console")
        print("4. 🚨 Set CREDENTIALS_JSON environment variable")
        return False
        
    print("✅ Environment ready for Google Calendar!")
    return True
