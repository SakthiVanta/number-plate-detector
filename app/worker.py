from celery import Celery
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.video_service import video_service
from app.models.models import Video, VideoStatus
import logging
import os
import cv2

# Initialize Celery
celery_app = Celery("worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

logger = logging.getLogger(__name__)

@celery_app.task(name="process_video_task", acks_late=True)
def process_video_task(video_id: int):
    """
    Entry point for video processing. Handles both Celery-based and Sequential (No-Redis) processing.
    """
    mode = "CELERY" if settings.USE_CELERY else "LITE (Sequential)"
    logger.info(f"--- [TASK START] Processing video {video_id} in {mode} mode ---")
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"Video {video_id} not found")
            return

        if video.is_chunk:
            video_service.process_video(video_id, db)
            return

        # Parent video logic
        try:
            cap = cv2.VideoCapture(video.filepath)
            if not cap.isOpened():
                raise Exception("Cannot open video")
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration_sec = frame_count / fps
            cap.release()
            
            chunk_threshold_sec = settings.CHUNK_DURATION_MINUTES * 60
            
            if duration_sec > chunk_threshold_sec:
                logger.info(f"Video duration {duration_sec}s > {chunk_threshold_sec}s. Initiating CHUNKING.")
                
                # 1. Split Video
                chunk_paths = video_service.split_video(video.filepath, settings.CHUNK_DURATION_MINUTES)
                
                # 2. Create DB entries
                chunk_ids = []
                for i, path in enumerate(chunk_paths):
                    chunk_filename = os.path.basename(path)
                    chunk_video = Video(
                        filename=chunk_filename,
                        filepath=path,
                        owner_id=video.owner_id,
                        is_chunk=True,
                        parent_video_id=video.id,
                        status=VideoStatus.PENDING
                    )
                    db.add(chunk_video)
                    db.flush()
                    chunk_ids.append(chunk_video.id)
                db.commit()
                
                # 3. Mode-based fan-out
                if settings.USE_CELERY:
                    from celery import chord
                    logger.info(f"Dispatching {len(chunk_ids)} chunk tasks via Celery...")
                    header = [process_video_task.s(cid) for cid in chunk_ids]
                    callback = merge_results_task.s(video_id)
                    chord(header)(callback)
                else:
                    logger.info("Sequential processing chunks (LITE MODE)...")
                    for cid in chunk_ids:
                        process_video_task(cid)
                    video_service.merge_results(video_id, db)
                    logger.info(f"Sequential processing complete for parent {video_id}")
            else:
                video_service.process_video(video_id, db)
                
        except Exception as e:
            logger.error(f"Error processing video {video_id}: {e}")
            video.status = VideoStatus.FAILED
            db.commit()

    except Exception as e:
        logger.error(f"Outer task failure for video {video_id}: {e}")
    finally:
        db.close()

@celery_app.task(name="merge_results_task")
def merge_results_task(results, parent_video_id: int):
    """
    Callback after all chunks are processed.
    'results' argument is passed by Celery chord (list of return values from check tasks),
    but process_video returns None, so we ignore it.
    """
    logger.info(f"Merging results for parent video {parent_video_id}")
    db = SessionLocal()
    try:
        video_service.merge_results(parent_video_id, db)
    except Exception as e:
        logger.error(f"Merge failed for {parent_video_id}: {e}")
    finally:
        db.close()
