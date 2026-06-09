"""Task manager wrapping APScheduler for periodic job management.

Provides lifecycle management (start/stop), dynamic job addition/removal,
and configuration of all scheduled monitoring tasks.
"""

from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)


class TaskManager:
    """Manages the APScheduler AsyncIOScheduler and all scheduled jobs.

    Wraps the scheduler with methods for initialization, lifecycle
    control, and dynamic job management.
    """

    def __init__(self) -> None:
        """Initialize the TaskManager with scheduler and settings."""
        self._settings = get_settings()
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._is_running: bool = False

    @property
    def scheduler(self) -> AsyncIOScheduler:
        """Get or create the AsyncIOScheduler instance.

        Returns:
            AsyncIOScheduler: The scheduler instance.
        """
        if self._scheduler is None:
            self._scheduler = AsyncIOScheduler(
                job_defaults={
                    "coalesce": True,
                    "max_instances": 1,
                    "misfire_grace_time": 60,
                }
            )
        return self._scheduler

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is currently running.

        Returns:
            bool: True if the scheduler is active.
        """
        return self._is_running

    def init_scheduler(self) -> None:
        """Configure all scheduled jobs based on application settings.

        Registers all monitoring tasks with their configured intervals.
        Must be called before start().
        """
        from scheduler.tasks import register_all_tasks
        register_all_tasks(self)
        logger.info("Scheduler initialized with all tasks")

    def start(self) -> None:
        """Start the scheduler and begin executing jobs.

        Initializes the scheduler if not already done, then starts it.
        """
        if self._is_running:
            logger.warning("Scheduler already running")
            return

        self.scheduler.start()
        self._is_running = True
        logger.info("Scheduler started")

    def stop(self) -> None:
        """Stop the scheduler gracefully.

        Shuts down the scheduler without waiting for pending jobs.
        """
        if not self._is_running:
            return

        self.scheduler.shutdown(wait=False)
        self._is_running = False
        logger.info("Scheduler stopped")

    def add_job(
        self,
        func: Callable,
        trigger: str,
        job_id: str,
        **kwargs,
    ) -> None:
        """Add a new job to the scheduler.

        Args:
            func: The async callable to execute.
            trigger: Trigger type ('interval' or 'cron').
            job_id: Unique identifier for the job.
            **kwargs: Additional trigger arguments (seconds, minutes,
                hours, day_of_week, hour, minute, etc.).
        """
        if trigger == "interval":
            trigger_obj = IntervalTrigger(
                seconds=kwargs.get("seconds", 0),
                minutes=kwargs.get("minutes", 0),
                hours=kwargs.get("hours", 0),
            )
        elif trigger == "cron":
            trigger_obj = CronTrigger(
                day_of_week=kwargs.get("day_of_week", "*"),
                hour=kwargs.get("hour", 0),
                minute=kwargs.get("minute", 0),
            )
        else:
            logger.error(f"Unknown trigger type: {trigger}")
            return

        self.scheduler.add_job(
            func,
            trigger=trigger_obj,
            id=job_id,
            replace_existing=True,
        )
        logger.debug(f"Job added: {job_id} ({trigger})")

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the scheduler by ID.

        Args:
            job_id: The unique identifier of the job to remove.

        Returns:
            bool: True if the job was found and removed.
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.debug(f"Job removed: {job_id}")
            return True
        except Exception as e:
            logger.debug(f"Job removal failed for {job_id}: {e}")
            return False

    def get_jobs(self) -> list[dict]:
        """Get information about all scheduled jobs.

        Returns:
            list[dict]: List of job info dictionaries with id,
                name, next_run_time, and trigger fields.
        """
        jobs = self.scheduler.get_jobs()
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": (
                    job.next_run_time.isoformat()
                    if job.next_run_time
                    else None
                ),
                "trigger": str(job.trigger),
            }
            for job in jobs
        ]

    def pause_job(self, job_id: str) -> bool:
        """Pause a specific job.

        Args:
            job_id: The job identifier to pause.

        Returns:
            bool: True if the job was paused successfully.
        """
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"Job paused: {job_id}")
            return True
        except Exception as e:
            logger.debug(f"Job pause failed for {job_id}: {e}")
            return False

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job.

        Args:
            job_id: The job identifier to resume.

        Returns:
            bool: True if the job was resumed successfully.
        """
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"Job resumed: {job_id}")
            return True
        except Exception as e:
            logger.debug(f"Job resume failed for {job_id}: {e}")
            return False
