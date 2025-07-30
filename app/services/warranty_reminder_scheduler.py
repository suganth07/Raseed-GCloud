"""
Warranty Reminder Scheduler

This module provides scheduled tasks for automatically checking and creating warranty reminders.
"""

import asyncio
from typing import List
from .warranty_reminder_service import WarrantyReminderService
from .firestore_service import FirestoreService
from ..utils.logging import LoggerMixin


class WarrantyReminderScheduler(LoggerMixin):
    """Scheduler for automated warranty reminder creation."""
    
    def __init__(self):
        """Initialize the warranty reminder scheduler."""
        super().__init__()
        self.reminder_service = WarrantyReminderService()
        self.firestore_service = FirestoreService()
        self.is_running = False
    
    async def start_scheduler(self, check_interval_hours: int = 24):
        """
        Start the warranty reminder scheduler.
        
        Args:
            check_interval_hours: How often to check for new reminders (default 24 hours)
        """
        if self.is_running:
            self.logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self.logger.info(f"Starting warranty reminder scheduler with {check_interval_hours}h interval")
        
        while self.is_running:
            try:
                await self._check_all_users_warranties()
                
                # Wait for the next check
                await asyncio.sleep(check_interval_hours * 3600)  # Convert hours to seconds
                
            except Exception as e:
                self.log_error("start_scheduler", e)
                # Continue running even if an error occurs
                await asyncio.sleep(3600)  # Wait 1 hour before retrying
    
    def stop_scheduler(self):
        """Stop the warranty reminder scheduler."""
        self.is_running = False
        self.logger.info("Warranty reminder scheduler stopped")
    
    async def _check_all_users_warranties(self):
        """Check warranties for all users and create reminders."""
        try:
            self.logger.info("Starting automated warranty reminder check for all users")
            
            # Get all unique user IDs from knowledge graphs
            user_ids = await self._get_all_user_ids()
            
            if not user_ids:
                self.logger.info("No users found with knowledge graphs")
                return
            
            total_reminders_created = 0
            processed_users = 0
            
            for user_id in user_ids:
                try:
                    result = await self.reminder_service.check_and_create_warranty_reminders(user_id)
                    
                    if result["status"] == "success":
                        reminders_created = result.get("reminders_created", 0)
                        total_reminders_created += reminders_created
                        
                        if reminders_created > 0:
                            self.logger.info(f"Created {reminders_created} reminders for user {user_id}")
                    
                    processed_users += 1
                    
                    # Small delay between users to avoid overwhelming the system
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    self.log_error(f"_check_user_warranties_{user_id}", e)
                    continue
            
            self.logger.info(
                f"Automated warranty check completed. "
                f"Processed {processed_users} users, created {total_reminders_created} reminders"
            )
            
        except Exception as e:
            self.log_error("_check_all_users_warranties", e)
    
    async def _get_all_user_ids(self) -> List[str]:
        """
        Get all unique user IDs from knowledge graphs.
        
        Returns:
            List of user IDs
        """
        try:
            user_ids = set()
            
            # Query knowledge graphs collection
            graphs_collection = self.firestore_service.db.collection('knowledge_graphs')
            docs = graphs_collection.stream()
            
            for doc in docs:
                graph_data = doc.to_dict()
                user_id = graph_data.get('user_id')
                if user_id:
                    user_ids.add(user_id)
            
            return list(user_ids)
            
        except Exception as e:
            self.log_error("_get_all_user_ids", e)
            return []
    
    async def run_manual_check(self, user_id: str = None) -> dict:
        """
        Run a manual warranty check for a specific user or all users.
        
        Args:
            user_id: Optional user ID to check (if None, checks all users)
            
        Returns:
            Dictionary with check results
        """
        try:
            if user_id:
                self.logger.info(f"Running manual warranty check for user: {user_id}")
                result = await self.reminder_service.check_and_create_warranty_reminders(user_id)
                
                return {
                    "success": True,
                    "message": f"Manual check completed for user {user_id}",
                    "results": result
                }
            else:
                self.logger.info("Running manual warranty check for all users")
                await self._check_all_users_warranties()
                
                return {
                    "success": True,
                    "message": "Manual check completed for all users"
                }
                
        except Exception as e:
            self.log_error("run_manual_check", e)
            return {
                "success": False,
                "error": str(e)
            }


# Global scheduler instance
warranty_scheduler = WarrantyReminderScheduler()


async def start_warranty_reminder_scheduler():
    """Start the global warranty reminder scheduler."""
    await warranty_scheduler.start_scheduler()


def stop_warranty_reminder_scheduler():
    """Stop the global warranty reminder scheduler."""
    warranty_scheduler.stop_scheduler()
