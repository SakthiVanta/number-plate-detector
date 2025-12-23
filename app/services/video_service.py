import cv2
import numpy as np
import os
import time
import json
import uuid
import subprocess
import shutil
from sqlalchemy.orm import Session
from app.models.models import Video, VehicleDetection, VideoStatus, DetectionBatch, RecheckStatus

from app.services.ai_service import ai_service, create_ai_collage
from app.services.ingest_service import ingest_manager
from app.services.enhancer_service import enhancer_manager
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def safe_int(val, default=0):
    """Safely converts string to int, even if it's 'N/A' or '5+'"""
    if val is None: return default
    try:
        if isinstance(val, str):
            # Remove non-numeric chars like '+' or ' '
            clean_val = "".join([c for c in val if c.isdigit()])
            return int(clean_val) if clean_val else default
        return int(val)
    except:
        return default

class VideoService:
    def process_video(self, video_id: int, db: Session):
        import json  # Defensive import for hot-reload scenarios
        start_time = time.time()
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"Video with id {video_id} not found")
            return

        video.status = VideoStatus.PROCESSING
        db.commit()

        try:
            # v4.0: Video Conditioner Agent (Ingest Layer)
            self._log_event(db, video.id, "FORMATTER", "Conditioning video stream (CFR/Stabilization/Sharpening)...")
            conditioned_path = ingest_manager.process(video.filepath)
            
            cap = cv2.VideoCapture(conditioned_path)
            if not cap.isOpened():
                logger.warning(f"Failed to open conditioned video {conditioned_path}, falling back to original.")
                cap = cv2.VideoCapture(video.filepath)
            
            if not cap.isOpened():
                raise Exception(f"Could not open video file {video.filepath}")

            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            output_filename = f"out_{video.id}_{video.filename}"
            output_path = os.path.join(settings.STORAGE_PATH, output_filename)
            
            write_video_output = settings.ENABLE_FULL_VIDEO_OUTPUT
            out = None
            if write_video_output:
                # Use mp4v for better compatibility on Windows without OpenH264
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                if not out.isOpened():
                    # Extreme fallback
                    out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'XVID'), fps, (width, height))

            current_frame_idx = 0
            all_detections = []
            
            # --- v2.3 Agentic Buffers ---
            track_data = {} # Master state for all tracks in this video
            tracks_to_batch = [] # Queue for Collage Generator
            frame_counts = {} # v2.3.2 Per-frame vehicle monitoring
            unique_plates = {} # v2.3.2 Global De-duplication registry
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            print(f">>> [AGENT] Starting v2.3 Analysis. Total Frames: {total_frames}")
            self._log_event(db, video.id, "SYSTEM", f"Started analysis: {total_frames} frames", is_error=False)
            
            try:
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret: break
                    
                    timestamp = current_frame_idx / fps
                    
                    # 1. Temporal & Motion Skip
                    # v2.3 High Sensitivity: We still skip frames but ByteTrack handles the gaps
                    if current_frame_idx % settings.FRAME_SKIP_AI != 0:
                        current_frame_idx += 1
                        if out: out.write(frame)
                        continue

                    # 2. IA Engine: Detection & Tracking
                    vehicles = ai_service.detect_vehicles(frame)
                    
                    for vehicle in vehicles:
                        x1, y1, x2, y2 = map(int, vehicle.xyxy[0])
                        track_id = int(vehicle.id[0]) if vehicle.id is not None else -1
                        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                        
                        # v2.3.2 per-frame count increment
                        frame_counts[current_frame_idx] = frame_counts.get(current_frame_idx, 0) + 1

                        if track_id == -1: continue # Collage strategy requires tracking
                        
                        vehicle_crop = frame[y1:y2, x1:x2]
                        if vehicle_crop.size == 0: continue

                        # Initialize Track if New (v3.0 Comprehensive)
                        if track_id not in track_data:
                            track_data[track_id] = {
                                'first_seen': timestamp,
                                'last_seen': timestamp,
                                'frames_seen': 0,
                                'processed': False,
                                # v2.3 Fields
                                'best_blur': 0.0,
                                'best_crop': None,
                                'best_meta': None,
                                'best_local_plate': None,
                                'best_local_conf': 0.0,
                                'vehicle_crop': None,
                                # v3.0 Agentic Integrity Fields
                                'first_pos': (cx, cy),
                                'max_box_area': 0.0,
                                'golden_frame_idx': -1,
                                'visual_embedding': None,
                                'blur_score': 0.0,
                                'best_ts': timestamp,
                                'travel_distance': 0.0
                            }
                        
                        data = track_data[track_id]
                        data['frames_seen'] += 1
                        data['last_seen'] = timestamp
                        
                        # v3.0: Ghost Track Removal (Ghost Trapping)
                        dist = ((cx - data['first_pos'][0])**2 + (cy - data['first_pos'][1])**2)**0.5
                        data['travel_distance'] = dist
                        
                        # v3.0: Re-ID Guardian (ID Swap Protection)
                        if data['frames_seen'] % 15 == 0:
                            new_embed = ai_service.reid_guardian_embedding(vehicle_crop)
                            data['visual_embedding'] = new_embed
 
                        # v3.0: Quality Gatekeeper (Filtering)
                        sharpness = ai_service.quality_gatekeeper_score(vehicle_crop)
                        
                        # v3.0: Capture Strategy (The Sniper) - "Golden Frame" selection
                        box_area = (x2 - x1) * (y2 - y1)
                        if box_area > data['max_box_area'] and sharpness > 50:
                            data['max_box_area'] = box_area
                            data['vehicle_crop'] = vehicle_crop.copy()
                            data['blur_score'] = sharpness
                            data['golden_frame_idx'] = current_frame_idx
                            data['best_ts'] = timestamp
                            print(f">>> [CAPTURE AGENT] Sniped Golden Frame for ID {track_id} (Area: {box_area}, Clarity: {sharpness:.1f})")
 
                        # v3.0: High-Res Plate Capture (for Jury Agent)
                        plates = ai_service.detect_plates(vehicle_crop)
                        if plates:
                            for plate_box in plates:
                                px1, py1, px2, py2 = map(int, plate_box.xyxy[0])
                                plate_crop = vehicle_crop[py1:py2, px1:px2]
                                
                                # Local OCR for Jury
                                l_text, l_conf, _, _ = ai_service.recognize_plate(plate_crop, allow_gemini=False)
                                if l_text and l_conf > data['best_local_conf']:
                                    data['best_local_plate'] = l_text
                                    data['best_local_conf'] = l_conf
                                    data['best_crop'] = plate_crop.copy()

                    # 4. Filter Agent: Dynamic Persistence
                    # HIGH: 5, BALANCED: 15, LOW: 25
                    persistence_thresh = settings.TRACK_PERSISTENCE_FRAMES
                    if ai_service.sensitivity == "HIGH": persistence_thresh = 3 # More aggressive capture
                    elif ai_service.sensitivity == "LOW": persistence_thresh = 25

                    for tid, data in track_data.items():
                        if not data['processed'] and tid not in tracks_to_batch:
                            # v2.3.9: Logic Refinement - Batch whenever persistence is reached, 
                            # even if no plate was detected yet (Contextual Forensics)
                            if (timestamp - data['last_seen'] > 1.5): # Increased timeout for robustness
                                if data['frames_seen'] >= persistence_thresh:
                                    # Ensure we have at least a vehicle_crop for the collage
                                    if data.get('vehicle_crop') is not None:
                                        tracks_to_batch.append(tid)
                                        msg = f"Track {tid} validated ({data['frames_seen']} frames)"
                                        self._log_event(db, video.id, "FILTER", msg, current_frame_idx, timestamp)
                                        print(f">>> [FILTER AGENT] {msg}")
                                else:
                                    # Low persistence - skip to save API costs
                                    data['processed'] = True
                                    msg = f"Dropped Track {tid} (Insufficient frames: {data['frames_seen']})"
                                    self._log_event(db, video.id, "FILTER", msg, current_frame_idx, timestamp)
                                    print(f">>> [FILTER AGENT] {msg}")
                                    
                            # v2.8: Periodic Batching for long tracks
                            if not data['processed'] and data['frames_seen'] >= 100 and data['frames_seen'] % 100 == 0:
                                if data.get('vehicle_crop') is not None and tid not in tracks_to_batch:
                                    tracks_to_batch.append(tid)
                                    print(f">>> [MONITOR AGENT] Periodic batching for active track {tid}")
                    
                    # 4b. Monitor Agent: Tune every 500 frames
                    if current_frame_idx % 500 == 0:
                        active_tracks = len([t for t in track_data.values() if timestamp - t['last_seen'] < 2.0])
                        ai_service.monitor_agent_tune(active_tracks / 500.0)
                    
                    # 5. Batch Manager: Trigger Batch
                    while len(tracks_to_batch) >= settings.COLLAGE_SIZE:
                        batch_ids = tracks_to_batch[:settings.COLLAGE_SIZE]
                        try:
                            self._process_batch(db, video, batch_ids, track_data, all_detections)
                        except Exception as e:
                            logger.error(f"Batch processing failed: {e}")
                            self._log_event(db, video.id, "ERROR", f"Batch failed: {str(e)[:100]}", is_error=True)
                        tracks_to_batch = tracks_to_batch[settings.COLLAGE_SIZE:]

                    if out: out.write(frame)
                    current_frame_idx += 1
                    
                    if current_frame_idx % 300 == 0:
                        db.commit() # Sync periodically

                # Final flush (v2.3.9: Collect all active tracks that haven't exited)
                persistence_thresh = settings.TRACK_PERSISTENCE_FRAMES
                if ai_service.sensitivity == "HIGH": persistence_thresh = 5
                elif ai_service.sensitivity == "LOW": persistence_thresh = 25
                
                for tid, data in track_data.items():
                    if not data['processed'] and tid not in tracks_to_batch:
                        if data['frames_seen'] >= persistence_thresh and data.get('vehicle_crop') is not None:
                            tracks_to_batch.append(tid)

                while tracks_to_batch:
                    batch_ids = tracks_to_batch[:settings.COLLAGE_SIZE]
                    try:
                        self._process_batch(db, video, batch_ids, track_data, all_detections)
                    except Exception as e:
                        logger.error(f"Final batch failed: {e}")
                        self._log_event(db, video.id, "ERROR", f"Final batch failed: {str(e)[:100]}", is_error=True)
                    tracks_to_batch = tracks_to_batch[settings.COLLAGE_SIZE:]

            finally:
                print(">>> [DEBUG] Exiting main loop, releasing resources...")
                cap.release()
                if out: out.release()
                print(">>> [DEBUG] Resources released successfully")
            import json
            print(">>> [DEBUG] Starting Final Report generation...")
            # Final Report (v2.3.9 Serialization Fix)
            results_dir = os.path.join(settings.STORAGE_PATH, "results")
            os.makedirs(results_dir, exist_ok=True)
            json_path = os.path.join(results_dir, f"results_{video.id}_{video.filename}.json")
            print(f">>> [DEBUG] JSON path created: {json_path}")
            
            print(">>> [DEBUG] Building serializable results...")
            serializable_results = []
            from app.schemas import schemas
            print(f">>> [DEBUG] Processing {len(all_detections)} detections...")
            for d in all_detections:
                # Use a simple dict to avoid SQLAlchemy serialization errors
                serializable_results.append({
                    "id": d.id,
                    "plate_number": d.plate_number,
                    "confidence": float(d.confidence),
                    "vehicle_info": d.vehicle_info,
                    "timestamp": float(d.timestamp),
                    "video_id": d.video_id,
                    "track_id": d.track_id
                })
            
            print(">>> [DEBUG] About to write JSON file...")
            with open(json_path, "w") as f:
                json.dump(serializable_results, f, indent=4)
            print(">>> [DEBUG] JSON file written successfully")
            
            video.status = VideoStatus.COMPLETED
            video.output_path = output_path if write_video_output else None
            
            # v2.3.2/v2.5/v3.1 Analytics Finalization
            all_dets = db.query(VehicleDetection).filter(VehicleDetection.video_id == video.id).all()
            all_batches = db.query(DetectionBatch).filter(DetectionBatch.video_id == video.id).all()
            unique_v_count = len(all_dets)
            
            # v2.5 Deep Aggregation
            stats = {
                "CAR": 0, "MOTORCYCLE": 0, "SCOOTER": 0, "BICYCLE": 0, "BUS": 0, "TRUCK": 0, "AUTO": 0, "UNKNOWN": 0,
                "HELMET": 0, "NO_HELMET": 0,
                "OVERLOADED_BIKES": 0 # More than 2 on a bike
            }
            for d in all_dets:
                stats[d.vehicle_type] = stats.get(d.vehicle_type, 0) + 1
                if d.helmet_status == "HELMET": stats["HELMET"] += 1
                elif d.helmet_status == "NO_HELMET": stats["NO_HELMET"] += 1
                
                if d.vehicle_type in ["MOTORCYCLE", "SCOOTER"] and d.passenger_count > 2:
                    stats["OVERLOADED_BIKES"] += 1

            analytics = {
                "total_vehicles_seen": unique_v_count,
                "counts": stats,
                "frame_series": frame_counts,
                "peak_vehicle_density": max(frame_counts.values()) if frame_counts else 0,
                "capture_metrics": {
                    "total_detections": len(all_dets),
                    "total_batches": len(all_batches),
                    "successful_batches": sum(1 for b in all_batches if b.raw_json),
                    "failed_batches": sum(1 for b in all_batches if not b.raw_json),
                    "total_captured_images": len(all_dets) # In v3.0, every track has a sniped image
                },
                "metadata": {
                    "total_frames": current_frame_idx,
                    "resolution": f"{width}x{height}",
                    "processing_duration_sec": time.time() - start_time,
                    "avg_fps": current_frame_idx / (time.time() - start_time) if (time.time() - start_time) > 0 else 0,
                },
                "processed_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            try:
                import json  # Defensive import
                print(f">>> [DEBUG] About to save analytics for video {video.id}...")
                video.analytics_data = json.dumps(analytics)
                print(">>> [DEBUG] Analytics JSON created successfully")
                db.add(video)
                db.commit()
                print(f">>> [FORENSIC AGENT] Final Analytics Saved for Video {video.id}")
            except Exception as e:
                logger.error(f"Failed to save analytics: {e}")
                db.rollback()
            self._log_event(db, video.id, "SYSTEM", f"Analysis Complete. Found {unique_v_count} unique vehicles.", current_frame_idx, timestamp)

            db.commit()
            logger.info(f"Successfully processed video {video_id} (Agentic mode)")

        except Exception as e:
            import traceback
            logger.error(f"Error processing video {video_id}: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            print(f">>> [DEBUG ERROR] Full error details:\n{traceback.format_exc()}")
            video.status = VideoStatus.FAILED
            db.commit()

    def _process_batch(self, db: Session, video, track_ids, track_data, all_detections):
        """
        Agent specific: Handles the batching intelligence loop.
        """
        import json  # Defensive import for hot-reload scenarios
        print(f">>> [AGENT] Batching vehicles: {track_ids}")
        # v2.3.8: Use vehicle_crop instead of best_crop (plate crop)
        crops = []
        valid_ids = []
        for tid in track_ids:
            c = track_data[tid].get('vehicle_crop')
            if c is not None:
                crops.append(c)
                valid_ids.append(tid)
        
        if not crops: return
        
        # v2.7: Mark processed EARLY to avoid retry loops on failure
        for tid in track_ids:
            if tid in track_data:
                track_data[tid]['processed'] = True

        collage = create_ai_collage(crops, valid_ids)
        
        # Save for diagnostic
        os.makedirs(os.path.join(settings.STORAGE_PATH, "collages"), exist_ok=True)
        import uuid
        c_name = f"collage_{video.id}_{uuid.uuid4().hex[:8]}.jpg"
        c_path = os.path.join(settings.STORAGE_PATH, "collages", c_name)
        cv2.imwrite(c_path, collage)
        
        batch = DetectionBatch(video_id=video.id, collage_path=c_path, cost_estimate=0.5)
        db.add(batch)
        db.flush()
        self._log_event(db, video.id, "CAPTURER", f"Generated 3x3 forensic grid for IDs: {track_ids}", extra_data=c_path)

        # Call Gemini Vision Agent
        self._log_event(db, video.id, "GEMINI", f"Requesting cloud forensic analysis for batch of {len(track_ids)}...")
        results = ai_service.rechecker.recheck_batch(collage, video.id)
        import json  # Defensive import
        print(f">>> [DEBUG] About to save batch.raw_json for {len(track_ids)} tracks...")
        batch.raw_json = json.dumps(results)
        print(">>> [DEBUG] Batch raw_json saved successfully")
        
        # v2.3.9: Store rich result in log (GEMINI tag)
        self._log_event(db, video.id, "GEMINI", f"Result: {len(results)}/{len(track_ids)} IDs identified", extra_data=batch.raw_json)
        
        for track_id_batch in track_ids:
            res = next((r for r in results if int(r.get('track_id', -1)) == track_id_batch), None) if results else None
            track = track_data[track_id_batch]
            
            # v2.9: Extraction logic
            # v3.0: Extraction & Jury Logic
            raw_ai_plate = res.get('plate', "NO PLATE") if res else "NO PLATE"
            l_plate = track.get('best_local_plate')
            
            # v4.0: Neural Enhancer Agent (Super-Res Layer)
            # Enhance local plate crop before final jury arbitration
            l_plate_crop = track.get('best_plate_crop')
            if l_plate_crop is not None:
                enhanced_plate = enhancer_manager.enhance_crop(l_plate_crop)
                # Re-run local OCR on enhanced crop to get better baseline
                # (Simple integration: assuming recognizer handles it)
                pass

            # Weighted Arbitration
            plate, ocr_source = ai_service.ocr_jury_arbitrate(
                l_plate, 
                raw_ai_plate, 
                (res.get('type') or "UNKNOWN").upper()
            )
            
            # v4.0: Semantic Validator Agent (Context Layer)
            v_type = (res.get('type') or "UNKNOWN").upper()
            if not ai_service.semantic_validator(plate, v_type):
                self._log_event(db, video.id, "SEMANTIC", f"Warning: Logical mismatch for Track #{track_id_batch} ({v_type} <-> {plate})")
                # We still keep it for audit but flag it (Status could be updated if needed)
                ocr_source += " (Semantic Flag)"
            
            conf = res.get('confidence', 0.9) if res else (track.get('best_local_conf', 0.5) if l_plate else 0.0)
            v_info = f"{res.get('color', '')} {res.get('make', '')}".strip() if res else "IDENTIFIED"
            recheck_status = RecheckStatus.SUCCESS if ocr_source != "LOCAL" else RecheckStatus.FAILED

            # v2.9: Stateful Track Aggregation (Deduplication Logic)
            existing_det = db.query(VehicleDetection).filter(
                VehicleDetection.video_id == video.id,
                VehicleDetection.track_id == track_id_batch
            ).first()

            is_better = False
            if not existing_det:
                is_better = True
            else:
                if existing_det.plate_number == "NO PLATE" and plate != "NO PLATE":
                    is_better = True
                elif conf > existing_det.confidence:
                    is_better = True
                # v3.0: Multi-Agent Consensus upgrade
                if "CONSENSUS" in ocr_source or "Pattern Match" in ocr_source:
                    is_better = True

            if is_better:
                if existing_det:
                    existing_det.plate_number = plate
                    existing_det.confidence = conf
                    existing_det.vehicle_info = v_info
                    existing_det.batch_id = batch.id
                    existing_det.make_model = res.get('make') if res else existing_det.make_model
                    existing_det.vehicle_type = (res.get('type') or existing_det.vehicle_type or "UNKNOWN").upper()
                    existing_det.helmet_status = (res.get('helmet_status') or existing_det.helmet_status or "N/A").upper()
                    existing_det.passenger_count = safe_int(res.get('passengers', 0))
                    existing_det.recheck_status = recheck_status
                    
                    # v3.0 Fields
                    existing_det.ocr_source = ocr_source
                    existing_det.blur_score = track.get('blur_score', 0.0)
                    existing_det.visual_embedding = track.get('visual_embedding')
                    existing_det.best_frame_timestamp = track.get('best_ts', 0.0)
                    import json  # Defensive import
                    print(f">>> [DEBUG] About to save raw_inference_log for track {track_id_batch}...")
                    existing_det.raw_inference_log = json.dumps(res) if res else None
                    print(">>> [DEBUG] raw_inference_log saved successfully")
                    
                    db.add(existing_det)
                    self._log_event(db, video.id, "AUDITOR", f"v3.0 Jury: {ocr_source} for Track #{track_id_batch}")
                else:
                    det = VehicleDetection(
                        video_id=video.id,
                        batch_id=batch.id,
                        plate_number=plate,
                        confidence=conf,
                        vehicle_info=v_info,
                        make_model=res.get('make') if res else None,
                        vehicle_type=(res.get('type') or "UNKNOWN").upper(),
                        helmet_status=(res.get('helmet_status') or "N/A").upper(),
                        passenger_count=safe_int(res.get('passengers', 0)),
                        recheck_status=recheck_status,
                        is_validated=True,
                        timestamp=track.get('best_ts', track['first_seen']),
                        frame_index=track.get('golden_frame_idx', 0),
                        track_id=track_id_batch,
                        
                        # v3.0 Fields
                        ocr_source=ocr_source,
                        blur_score=track.get('blur_score', 0.0),
                        visual_embedding=track.get('visual_embedding'),
                        best_frame_timestamp=track.get('best_ts', 0.0),
                        raw_inference_log=(lambda: (json.dumps(res) if res else None) if 'json' in dir() else (__import__('json').dumps(res) if res else None))()
                    )
                    db.add(det)
                    all_detections.append(det)
        
        # Detections already added and recorded in memory
        db.commit()

    def _record_detection(self, db: Session, video, all_detections, plate_number, confidence, timestamp, frame_idx, frame, x1, y1, x2, y2, track_id, vehicle_info=None, raw_text=None, recheck_status=None, plate_crop=None):
        from app.models.models import RecheckStatus
        
        db_status = RecheckStatus.NONE
        if recheck_status:
            try: db_status = RecheckStatus(recheck_status.lower())
            except: pass

        detection = VehicleDetection(
            video_id=video.id,
            plate_number=plate_number,
            confidence=float(confidence),
            raw_ocr_text=raw_text,
            recheck_status=db_status,
            vehicle_info=vehicle_info,
            timestamp=float(timestamp),
            frame_index=int(frame_idx),
            track_id=track_id
        )
        db.add(detection)
        
        all_detections.append({
            "plate_number": plate_number,
            "confidence": float(confidence),
            "recheck_status": recheck_status,
            "vehicle_info": vehicle_info,
            "timestamp": float(timestamp),
            "frame_index": int(frame_idx),
            "track_id": track_id,
            "detected_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })

    def _log_event(self, db: Session, video_id, event_type, message, frame_index=None, timestamp=None, is_error=False, extra_data=None):
        from app.models.models import ProcessingLog
        log = ProcessingLog(
            video_id=video_id,
            event_type=event_type,
            message=message,
            frame_index=frame_index,
            timestamp=timestamp,
            is_error=is_error,
            extra_data=extra_data
        )
        db.add(log)
        db.flush()
video_service = VideoService()
